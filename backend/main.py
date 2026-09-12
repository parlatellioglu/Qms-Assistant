import json
import os
import time
from contextlib import asynccontextmanager
import tempfile
# Load config.yaml into the environment BEFORE importing service modules, whose
# module-level os.getenv(...) constants must see the file's values. Real env
# vars (run.sh, per-instance overrides) still take precedence. See config.py.
import config  # noqa: F401  (imported for its load-on-import side effect)
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from services.embedding import (
    start_embedding_service_background,
    get_embedding_service,
    is_embedding_service_ready,
    get_embedding_service_error,
)
from services.llm import (
    generate_answer_with_meta,
    prepare_answer,
    stream_answer_tokens,
    summarize_conversation,
    DEFAULT_MODEL,
    NUM_CTX,
    HISTORY_RAW_CAP,
    SUMMARY_EVERY_TURNS,
    SUMMARY_MIN_TURNS,
)
from services import rules_store
from services import history_store
from services.compliance import (
    check_document,
    checkable_documents,
    load_rules,
    rules_for,
)
from services.doc_extract import (
    SUPPORTED_EXTENSIONS,
    UnsupportedFileType,
    extract_file,
)
from services.compliance_judge import COMPLIANCE_MODEL

# Number of chunked sources retrieved per query (env-overridable). Fewer sources
# = shorter prompt = faster generation on CPU. Default 5: with 3, documents whose
# relevance is split across chunks (e.g. the SAT/UAT test plans for a "test
# strategy" query) ranked just below the cutoff and never reached the model.
CHAT_TOP_K = int(os.getenv("CHAT_TOP_K", "5"))

# How many recent prior USER turns to prepend to a follow-up's retrieval query,
# so references like "those tests" keep the earlier constraints (e.g. a date)
# instead of retrieving over the bare follow-up. Generation-side history is
# selected separately in llm.py (asymmetric user/assistant + char budget).
RETRIEVAL_CONTEXT_TURNS = int(os.getenv("CHAT_RETRIEVAL_CONTEXT_TURNS", "2"))


def _contextualized_query(query: str, history: list | None) -> str:
    """Prepend recent prior user questions to the current one for retrieval only.

    A follow-up such as "what were the results of those tests" retrieves over all
    tests unless the earlier "...on <date>" constraint is carried along. We keep
    this to the last few USER turns (assistant answers would add noise) and only
    use it to search — the displayed query and the answer stay the current one.
    """
    if not history or RETRIEVAL_CONTEXT_TURNS <= 0:
        return query
    prior_users = [
        " ".join((h.get("content") or "").split())
        for h in history
        if h.get("role") == "user" and (h.get("content") or "").strip()
    ]
    if not prior_users:
        return query
    return "\n".join(prior_users[-RETRIEVAL_CONTEXT_TURNS:] + [query])


def _format_sources(results):
    """Shape chunked search hits into the source objects the frontend consumes."""
    return [
        {
            "id": res["document"]["id"],
            "title": res["document"]["title"],
            "department": res["document"].get("department"),
            "document_type": res["document"].get("document_type"),
            "status": res["document"].get("status"),
            "version": res["document"].get("version"),
            "author": res["document"].get("author"),
            "language": res["document"].get("language"),
            "tags": res["document"].get("tags", []),
            "similarity_score": res["score"],
            # parent chunk (LLM context / drawer body) + matched child (excerpt)
            "content": res["document"].get("content"),
            "excerpt": res.get("matched_child"),
        }
        for res in results
    ]


def _sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start loading the embedding model in the background so the API comes up at once.
    start_embedding_service_background()
    yield

app = FastAPI(
    title="QMS Assistant API",
    description="AI-assisted API for a quality management system",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    role: str          # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    query: str
    # Recent turns of the current conversation, oldest first (excludes this query).
    # Enables follow-up questions: used to contextualize retrieval and given to the
    # model so it can resolve references like "those tests".
    history: list[ChatMessage] | None = None
    # Rolling summary of older turns (round-tripped from the frontend, since the
    # backend keeps no session). Carries far context that fell out of the window.
    summary: str | None = None


class SummarizeRequest(BaseModel):
    history: list[ChatMessage] | None = None
    previous_summary: str | None = None


class ConversationBody(BaseModel):
    # Stored whole per conversation. messages/docsById are passed through as-is
    # (arbitrary UI shapes), so they're loosely typed.
    title: str | None = None
    messages: list[dict] = []
    docsById: dict = {}
    summary: str | None = ""
    summarizedCount: int | None = 0
    updatedAt: int | None = None

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")

@app.get("/health")
def health_check():
    status = "ready" if is_embedding_service_ready() else "loading"
    response = {"status": status}
    error = get_embedding_service_error()
    if error is not None:
        response["error"] = str(error)
        response["status"] = "error"
    return response

@app.get("/config")
def config():
    """Runtime config the frontend shows in its process panel (which model, etc.)."""
    return {
        "model": DEFAULT_MODEL,
        # Model the Compliance Checker's content tier (LLM-as-judge) uses; only
        # runs when the content tier is enabled. Shown in the checker UI.
        "compliance_model": COMPLIANCE_MODEL,
        "top_k": CHAT_TOP_K,
        "num_ctx": NUM_CTX,
        # How many raw recent messages the frontend should send. The backend then
        # selects asymmetrically (many user turns, few assistant answers) under a
        # character budget — see format_history in llm.py.
        "history_raw_cap": HISTORY_RAW_CAP,
        # Rolling-summary cadence: the frontend regenerates the summary every
        # summary_every_turns user turns, but only once the chat passes
        # summary_min_turns messages (short chats don't need one).
        "summary_every_turns": SUMMARY_EVERY_TURNS,
        "summary_min_turns": SUMMARY_MIN_TURNS,
        "retrieval": "chunked (late-chunking, dense + sparse RRF)",
    }

# --------------------------------------------------------------------------- #
#  Compliance rules editor API (CRUD over backend/rules/*.yaml).
#  Read side of the rule set the Compliance Checker consumes; lets QA staff
#  author/edit rules from the UI without touching YAML by hand.
# --------------------------------------------------------------------------- #
@app.get("/rules")
def rules_list():
    return {"rules": rules_store.list_rules(), "meta": rules_store.schema_meta()}


@app.post("/rules")
def rules_create(rule: dict = Body(...)):
    try:
        return rules_store.create_rule(rule)
    except rules_store.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/rules/{rule_id}")
def rules_update(rule_id: str, rule: dict = Body(...)):
    try:
        return rules_store.update_rule(rule_id, rule)
    except rules_store.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except rules_store.NotFoundError:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")


@app.delete("/rules/{rule_id}")
def rules_delete(rule_id: str):
    try:
        rules_store.delete_rule(rule_id)
        return {"deleted": rule_id}
    except rules_store.NotFoundError:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")


# --------------------------------------------------------------------------- #
#  Compliance Checker API — run the authored rule set against a document.
#  GET  /compliance/documents  lists the documents that can be checked (the
#       published corpus + the incomplete drafts), each annotated with how many
#       rules apply to it. POST /compliance/check runs the check and returns the
#       structured report (verdict, score, per-rule findings).
# --------------------------------------------------------------------------- #
class ComplianceRequest(BaseModel):
    doc_id: str | None = None          # id of a checkable document (corpus or draft)
    document: dict | None = None       # or an ad-hoc document object to check directly
    content_tier: bool = False         # run the LLM-as-judge content tier (slower)


def _doc_summary(doc: dict, rule_count: int) -> dict:
    return {
        "id": doc.get("id"),
        "title": doc.get("title"),
        "doc_kind": doc.get("doc_kind"),
        "version": doc.get("version"),
        "status": doc.get("status"),
        "department": doc.get("department"),
        "is_draft": bool(doc.get("is_draft")),
        "applicable_rules": rule_count,
    }


@app.get("/compliance/documents")
def compliance_documents():
    """List documents the checker can run against, with how many rules apply."""
    rules = load_rules()
    docs = checkable_documents()
    return {"documents": [_doc_summary(d, len(rules_for(d, rules))) for d in docs]}


@app.post("/compliance/check")
def compliance_check(request: ComplianceRequest):
    """Run the applicable rule set against a document and return the report.

    Resolve the document from ``doc_id`` (a checkable corpus/draft document) or
    take an ad-hoc ``document`` object. The content tier (LLM-as-judge) only runs
    when ``content_tier`` is set — it needs the analysis model and is slower; the
    deterministic structure + traceability tiers always run and need no LLM.
    """
    if request.document is not None:
        doc = request.document
    elif request.doc_id:
        doc = next((d for d in checkable_documents() if d.get("id") == request.doc_id), None)
        if doc is None:
            raise HTTPException(status_code=404, detail=f"Document '{request.doc_id}' not found.")
    else:
        raise HTTPException(status_code=400, detail="Provide 'doc_id' or 'document'.")

    judge = None
    if request.content_tier:
        try:
            from services.compliance_judge import make_ollama_judge
            judge = make_ollama_judge()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Content tier unavailable: {exc}")

    t0 = time.perf_counter()
    report = check_document(doc, judge=judge)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    result = report.to_dict()
    result["document"] = {
        "id": doc.get("id"),
        "title": doc.get("title"),
        "doc_kind": doc.get("doc_kind"),
        "version": doc.get("version"),
        "status": doc.get("status"),
        "is_draft": bool(doc.get("is_draft")),
    }
    result["content_tier"] = request.content_tier
    result["elapsed_ms"] = elapsed_ms
    return result


# Reject oversized uploads before reading them fully into memory / to disk.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))  # 10 MB


@app.get("/compliance/doc-kinds")
def compliance_doc_kinds():
    """Document kinds the checker has a rule set for — the upload form's targets."""
    return {"doc_kinds": rules_store.doc_kinds()}


# --------------------------------------------------------------------------- #
#  Process map — the project lifecycle extracted from the loaded documents by
#  scripts/corpus/build_process_map.py. Read-only here: the map is a build
#  artifact, regenerated when the corpus changes, never edited at runtime.
# --------------------------------------------------------------------------- #
PROCESS_MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "data", "process_map.json")


@app.get("/process-map")
def process_map():
    """The extracted lifecycles: one per process-defining document.

    A corpus can describe several distinct processes (an SDLC, a maintenance
    procedure, a department's own), so they are kept separate rather than merged
    into a lifecycle nobody actually follows.

    Returns an empty list when no map has been built, so the UI can say the loaded
    documents don't define a lifecycle rather than showing a broken view. A phase
    with no details means the documents name it but never describe it — that
    distinction is the point, so it is preserved rather than filtered out.
    """
    try:
        with open(PROCESS_MAP_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {"processes": [], "built": False}
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"process map unreadable: {exc}")

    return {
        "processes": data.get("processes", []),
        "model": data.get("model"),
        "built": True,
    }


@app.post("/compliance/check-upload")
async def compliance_check_upload(
    file: UploadFile = File(...),
    doc_kind: str = Form(...),
    version: str = Form("1.0"),
    status: str = Form("uploaded"),
    content_tier: bool = Form(False),
):
    """Upload a document file and run the applicable rule set against it.

    The file is flattened to text with the same extractor the corpus build uses
    (so it reads like an indexed document), tagged with the caller-supplied
    ``doc_kind`` (which rule set to check against), then handed to the same
    ``check_document`` path as the built-in documents. The file is only read to a
    temp location for extraction and deleted immediately after — nothing is
    persisted or indexed.
    """
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext or '?'}'. "
                   f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (maximum {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        content = extract_file(tmp_path, filename=filename)
    except UnsupportedFileType as exc:
        raise HTTPException(status_code=415, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read the file: {exc}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not content.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from the file (empty content).")

    doc = {
        "id": os.path.splitext(filename)[0],
        "title": filename,
        "doc_kind": doc_kind,
        "version": version,
        "status": status,
        "content": content,
    }

    judge = None
    if content_tier:
        try:
            from services.compliance_judge import make_ollama_judge
            judge = make_ollama_judge()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Content tier unavailable: {exc}")

    t0 = time.perf_counter()
    report = check_document(doc, judge=judge)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    result = report.to_dict()
    result["document"] = {
        "id": doc["id"],
        "title": doc["title"],
        "doc_kind": doc["doc_kind"],
        "version": doc["version"],
        "status": doc["status"],
        "is_draft": False,
        "uploaded": True,
    }
    result["content_tier"] = content_tier
    result["elapsed_ms"] = elapsed_ms
    return result


@app.get("/chat")
def chat_page():
    return {
        "status": "ok",
        "message": "Use POST /chat with JSON body {\"query\": \"...\"}."
    }

@app.post("/chat")
def chat(request: ChatRequest):
    fallback_response = {
        "query": request.query,
        "results": [],
        "answer": "Could not generate an answer.",
        "meta": None,
    }

    history = [h.model_dump() for h in request.history] if request.history else None
    try:
        print(f"[chat] Soru alındı: {request.query!r}", flush=True)
        service = get_embedding_service()
        print(f"[chat] Dokümanlar aranıyor (chunked: parent/child hybrid, top_k={CHAT_TOP_K})...", flush=True)
        # Mirror `ask_cmmi --chunked --answer`: chunked retrieval returns the parent
        # chunk as `content` and the matched child as `matched_child`, which feed
        # the source cards and preview drawer in the UI.
        retrieval_query = _contextualized_query(request.query, history)
        t0 = time.perf_counter()
        results = service.search_chunked(retrieval_query, top_k=CHAT_TOP_K)
        t1 = time.perf_counter()
        print(f"[chat] {len(results)} aday doküman bulundu: "
              f"{[r['document']['id'] for r in results]}", flush=True)

        if not results:
            print("[chat] Uygun doküman bulunamadı.", flush=True)
            return {
                "query": request.query,
                "results": [],
                "answer": "No relevant document found.",
                "meta": {"mode": "chunked", "top_k": CHAT_TOP_K, "num_sources": 0,
                         "retrieval_ms": int((t1 - t0) * 1000)},
            }

        answer, llm_meta = generate_answer_with_meta(
            request.query, results, history=history, summary=request.summary or "")
        t2 = time.perf_counter()

        meta = {
            **llm_meta,
            "mode": "chunked",
            "top_k": CHAT_TOP_K,
            "source_ids": [r["document"]["id"] for r in results],
            "retrieval_ms": int((t1 - t0) * 1000),
            "generation_ms": int((t2 - t1) * 1000),
            "total_ms": int((t2 - t0) * 1000),
        }
        print(f"[chat] Yanıt üretildi (model={meta.get('model')}, "
              f"retrieval={meta['retrieval_ms']}ms, generation={meta['generation_ms']}ms).", flush=True)

        return {
            "query": request.query,
            "results": _format_sources(results),
            "answer": answer,
            "meta": meta,
        }
    except Exception as exc:
        print(f"Chat endpoint failed: {exc}")
        return fallback_response


@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    """Streaming variant of /chat (Server-Sent Events).

    Emits, in order: a `meta` event (retrieval params + source cards), then many
    `token` events as the answer generates, then a `done` event (timings). Lets
    the UI show sources immediately and render the answer progressively so a slow
    model feels responsive.
    """
    history = [h.model_dump() for h in request.history] if request.history else None

    def gen():
        try:
            print(f"[chat-stream] Soru: {request.query!r}", flush=True)
            service = get_embedding_service()
            retrieval_query = _contextualized_query(request.query, history)
            t0 = time.perf_counter()
            results = service.search_chunked(retrieval_query, top_k=CHAT_TOP_K)
            t1 = time.perf_counter()
            print(f"[chat-stream] {len(results)} aday: {[r['document']['id'] for r in results]}", flush=True)
            if not results:
                yield _sse("error", {"message": "No relevant document found."})
                return

            model_name, llm_meta, prompt = prepare_answer(
                request.query, results, history=history, summary=request.summary or "")
            meta = {
                **llm_meta,
                "mode": "chunked",
                "top_k": CHAT_TOP_K,
                "source_ids": [r["document"]["id"] for r in results],
                "retrieval_ms": int((t1 - t0) * 1000),
            }
            yield _sse("meta", {"results": _format_sources(results), "meta": meta})

            for piece in stream_answer_tokens(prompt, model_name):
                yield _sse("token", {"text": piece})

            t2 = time.perf_counter()
            yield _sse("done", {"generation_ms": int((t2 - t1) * 1000),
                                "total_ms": int((t2 - t0) * 1000)})
            print(f"[chat-stream] tamamlandı (generation={int((t2 - t1) * 1000)}ms)", flush=True)
        except Exception as exc:
            print(f"[chat-stream] hata: {exc}", flush=True)
            yield _sse("error", {"message": "Could not generate an answer (service error)."})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/summarize")
def summarize(request: SummarizeRequest):
    """Roll the conversation into a short "what this chat is about" summary.

    The frontend calls this in the background every few turns (see
    summary_every_turns / summary_min_turns in /config) and round-trips the result
    back on the next /chat request. Best-effort: returns the previous summary
    unchanged on any failure, so it never blocks the chat.
    """
    history = [h.model_dump() for h in request.history] if request.history else None
    previous = request.previous_summary or ""
    try:
        summary = summarize_conversation(history, previous_summary=previous)
    except Exception as exc:
        print(f"[summarize] hata: {exc}", flush=True)
        summary = previous
    return {"summary": summary}


# --- Chat history (Phase 2: local SQLite) ---------------------------------- #
# Mirrors the frontend's history.js interface. Stays on-device (a sqlite file in
# backend/data/); nothing here calls out to any external service.

@app.get("/conversations")
def conversations_list():
    """The sidebar list: [{id, title, updated_at}], newest first."""
    return {"conversations": history_store.list_conversations()}


@app.get("/conversations/{cid}")
def conversation_get(cid: str):
    """Full thread (messages, cited docs, rolling summary) for reopening a chat."""
    convo = history_store.get_conversation(cid)
    if convo is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return convo


@app.put("/conversations/{cid}")
def conversation_save(cid: str, body: ConversationBody):
    """Upsert a conversation. Called after each completed turn."""
    updated_at = history_store.save_conversation(cid, body.model_dump())
    return {"id": cid, "updated_at": updated_at}


@app.delete("/conversations/{cid}")
def conversation_delete(cid: str):
    history_store.delete_conversation(cid)
    return {"deleted": cid}


class _NoCacheStaticFiles(StaticFiles):
    """StaticFiles that always revalidates.

    The frontend has no build step: `.jsx` files are fetched and transpiled in the
    browser at load time, so an edited file must reach the browser on the next
    reload. Starlette sends `etag`/`last-modified` but no `Cache-Control`, and
    browsers then apply *heuristic* caching — they may reuse a cached copy without
    asking the server at all. The result is editing a file, reloading, and still
    seeing the old UI, which is the single most confusing failure mode here.

    `no-cache` does not mean "don't cache": it means "revalidate before reusing".
    Combined with the ETag that Starlette already sends, an unchanged file still
    costs only a 304, while a changed one is always picked up.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


# Serve the QMS Assistant SPA. Mounted last so the API routes above
# (/health, /chat, /favicon.ico) take precedence over this catch-all mount.
_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/", _NoCacheStaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
