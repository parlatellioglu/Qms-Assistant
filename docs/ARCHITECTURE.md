# Architecture

A detailed description of how the system is built, so you can understand it without
reading all the code first. It reflects the **current implementation**, verified
against the source — where something is partial or unbuilt, it says so.

Companion documents:
- [`../PROCESS_LOG.md`](../PROCESS_LOG.md) — a dated engineering journal of decisions and why they were made.
- [`REQUIREMENTS.md`](REQUIREMENTS.md) — the FR/NFR requirements and their status.
- [`EVALUATION.md`](EVALUATION.md) — how retrieval and compliance accuracy were measured.

---

## 1. What this is

A **local, private, Turkish-language AI system over an organisation's
quality-management documents** (CMMI / SDLC procedures, specifications, test plans).
Not just a chatbot — four product pillars:

1. **Knowledge Assistant (RAG)** — answers questions using *only* the loaded
   documents, with source citations and an honest "I don't have this" fallback.
   **Built.**
2. **Compliance Checker** — checks a document against an authored rule set and
   returns a structured report (compliant / violation / missing / score). **Built.**
3. **Process guidance** — the project lifecycle as a ladder of phases, *extracted
   from the documents rather than hand-authored*, with a role lens. **Built.**
4. **Agentic quality layer** — watch a platform (Redmine / Teams / Slack), retrieve
   the relevant rule, check compliance, notify with a citation. **Not started.**

**Hard constraints that shape every decision:**

- **100% local / privacy-first.** No document, question or answer leaves the machine;
  no external AI APIs. Every infrastructure choice is judged against "stays
  in-house." (Aligns with KVKK, Turkish data-protection law.) One caveat: the
  frontend loads React and Babel from a public CDN, so the browser fetches those
  libraries — no project data is involved, but it isn't offline-capable as shipped.
- **Turkish-facing, but answers follow the question.** The UI chrome, the prompts
  and the corpus are Turkish; the answer is written in whatever language the user
  asked in (see §4.2). The documents may be Turkish while the question is English —
  that does not change the answer's language.
- **Deterministic and grounded.** Temperature 0, fixed seed; answers cite documents
  and never fabricate.
- **CPU-friendly.** Runs on ordinary hardware (developed on a 16 GB Mac; a 32 GB
  machine was used to trial larger models), which drives small context windows and
  lean models.

---

## 2. Technology stack

| Layer | Choice | Notes |
|---|---|---|
| Backend / API | **FastAPI** (Python), port **8013** | Also serves the frontend SPA as static files — one server for both. |
| Vector DB | **Qdrant** (Docker), port **6333** | Dense + sparse vectors + payload metadata. |
| Embeddings | **BGE-M3** via `FlagEmbedding` | Multilingual; produces dense and sparse vectors. Loaded in-process on a background thread at startup. |
| LLM runtime | **Ollama** (native, not Docker), port **11434** | Local models, called over its HTTP API. |
| Chat model | `models.chat`, default `gemma4:e4b` | Configurable; a lighter model trades quality for speed. |
| Compliance judge | `models.compliance`, default `gemma4:e4b` | Only used by the compliance content tier. |
| Frontend | **React 18 via Babel Standalone, in the browser** | **No build step** — see §7. |
| Container | Python 3.11-slim, CPU-only torch | `backend/Dockerfile`; `docker-compose.yml` for Qdrant + backend. |

**Runtime topology:** Browser → FastAPI (`:8013`, API + SPA) → Qdrant (`:6333`,
retrieval) + Ollama (`:11434`, generation). All on localhost.

---

## 3. Repository layout

```
config.yaml                  central settings — the one file to edit
backend/
  config.py                  loads config.yaml into the environment at startup
  main.py                    FastAPI app: every endpoint + serves the SPA
  data/
    cmmi_docs.py             THE CORPUS — 14 synthetic CMMI documents
    cmmi_drafts.py           3 deliberately incomplete drafts (compliance test material)
    small_docs.py            17 short sample documents
    process_map.json         the extracted lifecycle (a build artifact)
  services/
    embedding.py             BGE-M3 + Qdrant: index and search (hybrid, chunked)
    chunking.py              parent/child splitting
    late_chunking.py         context-aware child embeddings (one parent pass)
    llm.py                   prompt building, Ollama calls, memory window, rolling summary
    compliance.py            compliance engine: runs rules, builds the report
    compliance_judge.py      LLM-as-judge for the content tier
    rules_store.py           CRUD over rules/*.yaml (round-trip YAML)
    history_store.py         conversation persistence (SQLite)
    doc_extract.py           flatten docx/xlsx/pptx/txt/md to text
  rules/
    srs.yaml                 14 SRS rules (7 structure, 2 traceability, 5 content)
    bur.yaml                 2 BUR rules (content)
  eval/compliance_cases.yaml 9 labelled compliance cases (the answer key)
frontend/
  index.html                 loads Babel, the design system, config, then the views
  _ds_bundle.js              design-system primitives (window.QMSDesignSystem)
  app/
    config.js                window.QMS_CONFIG: suggestions, ROLES, ROLE_MATCH, API_BASE
    history.js               window.QMS_History: conversation CRUD against the backend
    App.jsx                  orchestrator: chat state, streaming, role, view switching
    Sidebar.jsx              nav, conversation history, role selector
    EmptyState.jsx           welcome screen + role-aware starter questions
    ChatThread.jsx           message list, streaming answer, source cards
    ComplianceChecker.jsx    upload → check → structured report
    RulesManager.jsx         rules editor (plain-language CRUD)
    ProjectStart.jsx         "Yeni Proje" — the extracted lifecycle ladder
scripts/
  ingest.py                  point at ANY folder of documents → corpus module (+ index)
  corpus/                    build the corpus and process map from documents
  query/                     index, ask, run compliance from the CLI
data/                        the synthetic source documents (see data/README.md)
tests/                       pytest suite
rag_eval/                    promptfoo setup for model comparison
docs/                        requirements, architecture, evaluation, question sets
```

---

## 4. Knowledge Assistant (RAG)

### 4.1 Retrieval pipeline (`backend/services/embedding.py`)

1. **Hybrid search.** BGE-M3 produces a **dense** vector (cosine) and a **sparse**
   vector. Both are searched in Qdrant and merged with **Reciprocal Rank Fusion**, so
   a document ranking well in *both* lists beats one appearing in only one. Scores are
   rank-based (~1.0 best), **not** cosine similarity — which is why the relevance
   threshold is a heuristic gate rather than a similarity cutoff.
2. **Parent/child chunking** (`chunking.py`). Documents split into ~2000-char
   **parent** chunks, each into ~500-char overlapping **child** chunks. Search runs
   over children (precise); the **parent** is returned as LLM context (enough
   surrounding detail).
3. **Late chunking** (`late_chunking.py`, on by default). Rather than embedding each
   child in isolation, the **whole parent** goes through the transformer in one
   forward pass and each child's dense vector is **mean-pooled from that parent's
   token span** — so every child embedding carries its surroundings. The query is
   encoded natively; a short query needs no parent context. `LATE_CHUNKING=0`
   reproduces naive per-child encoding for an A/B comparison.
4. **Per-document scoring blend** (`PARENT_AGG_LAMBDA = 0.5`). Each document scores
   `best_child + 0.5·(sum_children − best_child)`. λ=0 favours one strong short
   document; λ=1 favours long multi-chunk ones; 0.5 balances. One entry per document,
   so a single file can't flood every slot.
5. **Top-K** (`retrieval.top_k`, **default 5**) documents feed the answer. It was 3
   until documents whose relevance was split across chunks began ranking just below
   the cutoff and never reaching the model — see `PROCESS_LOG.md`, 14-08.

### 4.2 Grounded generation and honest fallback (`backend/services/llm.py`)

- If the top score ≥ `retrieval.relevance_threshold` (0.5), the **grounded prompt**
  is used: answer only from the provided documents, cite the source title, combine
  sources, match the answer's specificity to the question's, and **answer in the
  question's language**.
- Below threshold (or nothing retrieved), a **general-answer prompt** runs and the
  answer is prefixed with a **fallback notice** stating it isn't grounded in the
  documents. If the model omits the notice, the backend prepends it.
- Generation is Ollama with `temperature 0`, `seed 42`, model kept resident
  (`keep_alive`), hidden "thinking" pass off by default.
- Every prompt sent to the model is appended to a local debug log
  (`logging.log_prompts`), never shown in the UI.

**Answer language.** The answer follows the **question**, not the corpus: a Turkish
question gets a Turkish answer, an English one gets English, even though the
documents are Turkish either way. `detect_language()` decides per question — Turkish
diacritics weigh heavily, with function-word overlap deciding the rest, so Turkish
typed without diacritics ("kabul kriterleri nelerdir") is still recognised.
Undecidable input (empty, acronyms only) falls back to Turkish, the product's default
audience. The result is recorded as `meta.language`.

This matters beyond the prompt line, because the **fallback notice is written by the
backend, not the model** — it is prepended when the model omits it. A single
hard-coded string would put a Turkish preamble on an English answer, so there is one
notice per language (`FALLBACK_NOTICES`) and the enforcement check accepts either
(`has_fallback_notice`). Adding a language means adding a notice, not just a prompt
line. The rolling summary follows the conversation's language for the same reason.

### 4.3 Conversation memory

Three mechanisms, deliberately separate:

- **Retrieval contextualization** (`main.py _contextualized_query`): the last
  `retrieval.context_turns` (default 2) prior **user** questions are prepended to the
  current one **for the search only**, so an earlier constraint isn't lost. The
  displayed question and the answer stay the current one.
- **Asymmetric prompt window** (`llm.py format_history`): keeps the last **10 user
  turns** but only **2 assistant answers**, then trims oldest-first to a **2400-char
  budget**, never dropping the newest user turn. User questions are short and carry
  the thread's intent; assistant answers are long and re-derivable from retrieval, so
  the same budget reaches much further back than a symmetric window would.
- **Rolling summary** (`POST /summarize`): every 4 user turns past a 12-message
  floor, older turns are folded into a short "what this chat is about" paragraph,
  regenerated in the background and round-tripped through the frontend (the backend
  keeps no session). Best-effort — a failure returns the previous summary and never
  blocks the chat.

Conversations are **persisted** to local SQLite (`backend/services/history_store.py`), listed
in the sidebar and reopened with their summary intact.

### 4.4 Streaming

`POST /chat/stream` uses **Server-Sent Events**: a `meta` frame (retrieval params +
source cards), then many `token` frames, then `done` (timings). The UI shows sources
immediately and renders the answer progressively.

---

## 5. Compliance Checker

Checks a document against an **authored rule set** — the rules stay primary; the
model never decides freely what "compliant" means.

### 5.1 Rules (`backend/rules/*.yaml`)

One file per `doc_kind`. Currently **14 SRS rules** and **2 BUR rules**; other kinds
are unwritten. Each rule has `id`, `applies_to.doc_kind`, `tier`, `severity`,
`statement` (plain Turkish) and a `check` block.

| Tier | Executors | Needs a model? |
|---|---|---|
| `structure` | `section_present`, `revision_history`, `signature_block`, `metadata_regex` | No |
| `traceability` | `refs_resolve`, `id_trace` | No |
| `content` | `llm_judge` | Yes |

### 5.2 Engine (`compliance.py check_document`)

Selects rules matching the document's `doc_kind`, sorts by tier
(structure → traceability → content), and runs each one, producing a `Finding` per
rule. A rule that throws is caught as an error rather than sinking the run.

The deterministic tiers run fully offline. The content tier calls the judge **once
per content rule**, each call sending one criterion plus the document text and
parsing a strict JSON verdict — so N content rules means N model calls, which is why
that tier is slower and opt-in.

The report carries a `verdict` (`compliant` / `partially_compliant` /
`non_compliant`), a severity-weighted `score`, and findings bucketed as
`passed / violations / missing / skipped / errors`. A failed `blocker` forces
`non_compliant` regardless of score. Skipped and errored rules are excluded from the
score denominator, so an un-wired content tier doesn't drag the score down.

### 5.3 Document upload

`POST /compliance/check-upload` (multipart) accepts **docx / xlsx / pptx / txt / md**,
takes a `doc_kind`, and runs the check. `doc_extract.py` flattens the file with the
**same extractor the corpus build uses**, so an uploaded document reads like an
indexed one. The file is written to a temp path only for extraction and deleted
immediately — **nothing is stored or indexed**. Max 10 MB; unknown types return 415.

The `ComplianceChecker` view is **upload-only**. Built-in corpus documents remain
checkable through `POST /compliance/check` with a `doc_id`, used by tests and CLI.

### 5.4 Rules editor

`RulesManager.jsx` + `/rules` CRUD + `rules_store.py` let quality staff author rules
in plain language without touching YAML. `rules_store.py` uses **round-trip YAML**
(`ruamel.yaml`) so edits preserve the hand-authored comments in the rule files, and
it auto-assigns rule ids.

---

## 6. Process guidance

The project lifecycle rendered as a ladder of phases — deliverables, entry/exit
criteria and gate per phase — in the "Yeni Proje" view (`ProjectStart.jsx`), served
read-only from `GET /process-map`.

The map is **extracted, not authored**: `scripts/corpus/build_process_map.py` derives
it from the loaded documents. Nothing about CMMI or any phase vocabulary is baked in
— point it at a different corpus and it produces that lifecycle. Every claim must
carry a citation that survives an evidence check against the source text, or it is
dropped; `tests/test_process_map.py` verifies that invented phases, paraphrased
values and fabricated quotes are rejected.

A phase the documents *name* but never *describe* renders as an explicit "no detail
in the loaded documents" note rather than an empty card — the distinction is the
point. In the bundled corpus, 11 phases are named but only the first five are
detailed.

A **role lens** highlights the items mentioning the viewer's role, matched through
`ROLE_MATCH` in `config.js`. It's a lens, never a filter: nothing is hidden.

---

## 7. Frontend architecture (no build step)

`index.html` loads Babel Standalone, the design-system bundle (`_ds_bundle.js` →
`window.QMSDesignSystem`), `config.js` and `history.js`, then each view as
`<script type="text/babel" src="app/*.jsx">`. **Babel transpiles the JSX in the
browser at load time** — no webpack, no vite, no `npm install`.

**Consequence:** editing a `.jsx` file takes effect on the next reload. The backend
serves these files with `Cache-Control: no-cache, must-revalidate`
(`_NoCacheStaticFiles` in `main.py`) precisely so an edit is always picked up —
without it, browsers apply heuristic caching and silently reuse the old file, which
was the most common source of "my change didn't work." The ETag is still honoured,
so an unchanged file costs a 304 rather than a re-download.

Four views, switched by `App.jsx` state: **chat** (default), **project**,
**compliance**, **rules**. Runtime config comes from `GET /config` and is displayed
in the UI, so one setting moves both the browser and the prompt.

---

## 8. Backend API (`backend/main.py`)

| Method & path | What it does |
|---|---|
| `GET /health` | Readiness — the embedding model loads in the background at startup. |
| `GET /config` | Runtime config the UI reads: `model`, `compliance_model`, `top_k`, `num_ctx`, `history_raw_cap`, summary cadence, retrieval description. |
| `POST /chat` | Non-streaming RAG answer. Body `{ query, history?, summary? }`. |
| `POST /chat/stream` | Streaming RAG answer (SSE: `meta` → `token`… → `done`). |
| `POST /summarize` | Fold recent turns into the rolling conversation summary. |
| `GET/PUT/DELETE /conversations[/{id}]` | Conversation history CRUD (local SQLite). |
| `GET /rules`, `POST /rules`, `PUT /rules/{id}`, `DELETE /rules/{id}` | Rules editor CRUD. |
| `GET /compliance/documents` | Built-in checkable documents + how many rules apply. |
| `GET /compliance/doc-kinds` | Document kinds that have a rule set (upload targets). |
| `POST /compliance/check` | Check a built-in doc (`doc_id`) or an ad-hoc `document`; `content_tier` toggles the LLM tier. |
| `POST /compliance/check-upload` | Multipart upload → extract → check → report; file deleted after. |
| `GET /process-map` | The extracted lifecycle phases. |

---

## 9. The corpus

`backend/data/cmmi_docs.py` holds **14 synthetic CMMI/SDLC lifecycle documents** for
one fictional project — TRF, Tech Reco, PMP, BUR, SRS, DSAD, SAT/UAT Plans, SAT/UAT
Cases, SAT/UAT Certificates, Close-out Report, and an SDLC process deck (the richest
single document: phases, review gates, roles, configuration management). It is
generated from the source files in `data/` by `scripts/corpus/build_cmmi_corpus.py`.

**Everything in it is synthetic** — invented organisation, project, people and
identifiers. See [`../data/README.md`](../data/README.md).

**Department metadata is thin:** 13 documents are `Mühendislik`, 1 is `Kalite`. This
matters — you can't meaningfully filter the corpus by the user's department, which is
why role-based views are personalization rather than filtering.

`cmmi_drafts.py` holds 3 deliberately incomplete SRS drafts as compliance test
material. They are **never indexed** into Qdrant.

To use your own documents instead, see `scripts/ingest.py` and `data/README.md`.

---

## 10. Configuration

Everything lives in one commented **`config.yaml`** at the repo root, loaded at
startup by `backend/config.py`, which copies values into the process environment
before any service module reads them.

Precedence: **real environment variable → `config.yaml` → built-in default.** A
variable already set in the environment always wins, so a single run can be
overridden without touching the file — `LLM_MODEL=other-model ./run.sh`, or two
backends on different ports for a model comparison.

| Setting | Env var | Default |
|---|---|---|
| `models.chat` | `LLM_MODEL` | `gemma4:e4b` |
| `models.compliance` | `COMPLIANCE_MODEL` | `gemma4:e4b` |
| `retrieval.top_k` | `CHAT_TOP_K` | `5` |
| `retrieval.relevance_threshold` | `RAG_RELEVANCE_THRESHOLD` | `0.5` |
| `retrieval.context_turns` | `CHAT_RETRIEVAL_CONTEXT_TURNS` | `2` |
| `retrieval.late_chunking` | `LATE_CHUNKING` | `true` |
| `retrieval.collection` | `CHAT_COLLECTION` | `kurumsal_kalite_cmmi_chunked` |
| `generation.num_ctx` | `LLM_NUM_CTX` | `8192` |
| `history.raw_cap` | `CHAT_HISTORY_RAW_CAP` | `40` |
| `history.user_turns` | `CHAT_HISTORY_USER_TURNS` | `10` |
| `history.assistant_turns` | `CHAT_HISTORY_ASSISTANT_TURNS` | `2` |
| `history.char_budget` | `CHAT_HISTORY_CHAR_BUDGET` | `2400` |
| `summary.every_turns` / `min_turns` | `CHAT_SUMMARY_*` | `4` / `12` |
| `services.qdrant_url` / `ollama_url` | `QDRANT_URL` / `OLLAMA_URL` | localhost |

The full mapping is in `backend/config.py`.

---

## 11. Running it

```bash
./run.sh          # then open http://127.0.0.1:8013
```

`run.sh` starts Qdrant in Docker, stops any containerised backend so the local one
owns `:8013`, checks Qdrant and Ollama, then runs FastAPI (serving API + SPA). The
embedding model loads on first start — wait for "Application startup complete."

**The Qdrant index is not in the repository** (it's a build artifact). A fresh clone
must index the corpus once before the assistant can answer:

```bash
QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/query/index_cmmi_chunked.py
```

**Re-indexing:** `index_chunked(recreate=True)` — the default, used by the corpus
build scripts — drops and rebuilds the whole collection. `recreate=False` adds to
an existing one instead, re-embedding only the documents given and replacing only
their own points (`scripts/ingest.py --append`). Chunk point ids are deterministic
(`uuid5` over `doc:parent:child`), so re-indexing a document overwrites its chunks;
a document's stale points are deleted first, so a document that *shrank* doesn't
leave orphaned chunks behind.

---

## 12. Testing

The `tests/` suite splits in two:

- **Standalone** (no services needed): chunking, memory window, rolling summary,
  process-map extraction, history store, compliance engine, compliance eval gate.
- **Needs the stack up** (Qdrant, and Ollama for generation): retrieval accuracy
  (`test_cmmi_chunked`, `test_cmmi_docs`, `test_sparse_search`, `test_table_and_csv`)
  and the end-to-end chat API (`test_chat_api`).

See [`EVALUATION.md`](EVALUATION.md) for the accuracy measurement beyond unit tests.

---

## 13. Gotchas

1. **The frontend has no build step.** Edit `.jsx` → reload. Static responses carry
   `Cache-Control: no-cache`, so the browser revalidates every time. If you ever
   remove that header, a plain reload starts serving stale files again — and a
   browser that cached a file *before* the header existed still needs one hard
   refresh (`Cmd+Shift+R`) to let go of it.
2. **A full re-index wipes the collection.** That is the default and is correct when
   the corpus is rebuilt wholesale; use `--append` to add documents instead.
3. **Uploaded documents are not added to the RAG — deliberately.** The Compliance
   Checker extracts, checks and deletes, and says so in the UI; that transience is
   a privacy property, not a missing feature. Adding documents to the searchable
   corpus is a separate, explicit step (`scripts/ingest.py`).
4. **The rule set and the corpus are different things.** Rules define what a *good*
   document must contain; the corpus is what the assistant *retrieves* from. Don't
   answer retrieval questions from rule thresholds.
5. **RRF scores are rank-based, not similarity.** The 0.5 relevance threshold is a
   heuristic gate; don't read it as a cosine score.
6. **Determinism is intentional.** Temperature 0 and a fixed seed keep answers stable
   and reduce cross-source conflation; changing them reduces consistency.
7. **The compliance content tier costs one model call per rule.** That's why it is
   opt-in and why the deterministic tiers run first.
8. **Turkish in the chrome, not necessarily in the answer.** UI strings, prompts
   and the corpus are Turkish, but the answer language is chosen per question by
   `detect_language()` in `llm.py`, and the fallback notice has one variant per
   language. Adding a language means adding a notice, not just a prompt line.

---

## 14. Glossary

**CMMI** — Capability Maturity Model Integration, a process-maturity framework.
**SDLC** — Solutions Delivery Life Cycle, the lifecycle procedure the corpus
describes. **RAG** — Retrieval-Augmented Generation. **RRF** — Reciprocal Rank
Fusion. **BGE-M3** — the multilingual embedding model. **KVKK** — Turkish
data-protection law.

**Document types in the corpus:** **TRF** (Technical Requirements Form), **Tech Reco**
(Technical Recommendation), **BUR** (Business Unit Requirements), **SRS** (Software
Requirements Specification), **DSAD** (Detailed System & Architecture Design), **PMP**
(Project Management Plan), **SAT** / **UAT** (System / User Acceptance Test),
**Close-out Report**. **MPR / G1–G6** — management review gates. **DAR** — Decision
Analysis & Resolution.
