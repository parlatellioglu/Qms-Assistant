# QMS Assistant

A **local, private, Turkish-language AI system** over an organisation's
quality-management documents (CMMI / SDLC procedures, specifications, test plans).
It answers questions from *only* those documents — always with citations and an
honest "I don't have this" fallback — checks documents against an authored rule set,
and derives the project lifecycle from the documents themselves.

Everything runs **on your own machine**: Qdrant for vectors, Ollama for generation,
BGE-M3 embeddings in-process. No external AI APIs, no document or question leaving
the host. That was a hard constraint, not a preference — it aligns with KVKK,
Turkish data-protection law.

> The product is **Turkish-facing**: the UI chrome, the prompts and the corpus are
> Turkish. **Answers follow the language of the question** — ask in English and the
> answer, including the "I couldn't find this" notice, comes back in English. The
> documentation is English for readability.

> **The bundled corpus is synthetic.** It was written for this project — a fictional
> organisation, project, people and identifiers — so the system has a realistic
> quality corpus to work against. No real company documents are included. See
> [`data/README.md`](data/README.md).

---

## What it does

**1. Knowledge Assistant (RAG)** — *built*
Ask in natural language; the assistant retrieves the relevant passages and answers
with source cards you can open and verify. Grounded and deterministic (temperature 0,
fixed seed) — it cites documents and never fabricates. If the documents don't cover
something, it says so instead of guessing. Follow-ups keep context ("what were the
results of those tests?" resolves against the earlier question) via an asymmetric
memory window plus a rolling summary for long chats. Threads persist locally and
reopen from the sidebar.

**2. Compliance Checker** — *built*
Check a document — built-in or uploaded — against a rule set authored per document
type. Returns a structured report: compliant parts, violations, missing items,
suggested fixes and a severity-weighted score. Structure and traceability rules are
deterministic; content-quality rules use a local model as a judge. Rules are editable
from the UI in plain language.

**3. Process guidance** — *built*
The project lifecycle as a ladder of phases — deliverables, entry/exit criteria and
gates — **extracted from the loaded documents, not hand-authored**. Every claim is
citation-checked against the source text or dropped. A role lens highlights the items
that concern the viewer.

**4. Agentic quality layer** — *not started*
Watch a platform (Redmine / Teams / Slack), retrieve the relevant rule, check
compliance, notify with a citation — reusing the same grounded engine, still local.

---

## How retrieval works

- **Hybrid search** — dense (BGE-M3) + sparse vectors in Qdrant, merged with
  Reciprocal Rank Fusion, so exact-term and semantic matches both count.
- **Parent/child chunking** — search small child chunks (~500 chars), but hand the
  larger parent chunk (~2000 chars) to the model as context.
- **Late chunking** — each parent is encoded **once** and every child's dense vector
  is mean-pooled from that parent's token span, so children carry surrounding
  context. `LATE_CHUNKING=0` reproduces naive per-child encoding for an A/B run.
- **Per-document scoring blend** — `best_child + 0.5·(sum − best)`, so a long
  document whose relevance is spread across chunks can surface without burying a
  short, densely on-topic one. One entry per document.

The reasoning behind each of these — and the retrieval bug that motivated the
scoring blend — is in [`PROCESS_LOG.md`](PROCESS_LOG.md).

---

## Stack

| Layer | Choice | Port |
|---|---|---|
| Backend / API | **FastAPI** (Python) — also serves the frontend SPA | `8013` |
| Vector DB | **Qdrant** (Docker) — dense + sparse vectors + metadata | `6333` |
| Embeddings | **BGE-M3** via `FlagEmbedding` (multilingual, in-process) | — |
| LLM runtime | **Ollama** (native) — local models | `11434` |
| Frontend | **React 18 via Babel Standalone, in the browser — no build step** | — |

The backend serves **both** the API and the SPA, so there is one server to run.
`.jsx` files are transpiled in the browser at load time — no bundler, no
`npm install`.

---

## Quickstart

**Prerequisites**

- **Docker** (for Qdrant)
- **[Ollama](https://ollama.com)** running locally, with the answer model pulled:
  ```bash
  ollama pull gemma4:e4b        # or whatever models.chat you set in config.yaml
  ```
- **Python 3.11+**

**1. Install**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # backend runtime + tests + scripts
```

**2. Index the corpus**

The Qdrant index is a build artifact and is **not** in the repository, so it has to
be built once before the assistant can answer. Start Qdrant, then:

```bash
docker compose up -d qdrant
QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/query/index_cmmi_chunked.py
```

This loads BGE-M3 (a few GB on first run) and embeds the corpus. It takes a few
minutes on CPU and only needs repeating when the documents change.

**3. Run**

```bash
./run.sh
```

Starts Qdrant, checks that Qdrant and Ollama are reachable, then runs the backend
(which also serves the UI). Wait for `Application startup complete`, then open:

```
http://127.0.0.1:8013
```

`Ctrl-C` stops it. Retrieval works without Ollama, but answers will show an error
until Ollama is running.

---

## Using your own documents

The bundled corpus is a demo. To point the system at a real one:

```bash
# see what would be picked up; write nothing
.venv/bin/python scripts/ingest.py /path/to/your/documents --dry-run

# build a corpus module and index it
QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/ingest.py \
    /path/to/your/documents --out backend/data/my_docs.py \
    --index --collection my_docs
```

Then set **both** of these in `config.yaml` and restart — they control two
different things, and the script prints them for you when it finishes:

| Setting | Value | What it switches |
|---|---|---|
| `retrieval.collection` | `my_docs` | the Qdrant collection the **assistant** searches |
| `corpus.module` | `data.my_docs` | the documents the **Compliance Checker** checks, and that traceability rules resolve references against |

**Adding documents later** doesn't mean rebuilding everything:

```bash
.venv/bin/python scripts/ingest.py /path/to/new-docs --out backend/data/my_docs.py \
    --index --append --collection my_docs
```

`--append` re-embeds only the documents you give it and replaces only their own
points, so adding one file to a large corpus costs one file's worth of encoding.
Re-running it on an unchanged document is harmless, and a document that got
shorter doesn't leave stale chunks behind.

`.docx`, `.xlsx`, `.pptx`, `.md` and `.txt` are supported, using the same
extractor the Compliance Checker uses for uploads. Documents carrying YAML
frontmatter have their declared `title`, `id`, `department`, `document_type`,
`tags` and so on honoured rather than guessed; anything unknown is left empty
rather than invented. `--kind` / `--kind-map` set the `doc_kind` that compliance
rules bind to.

**Two things that do not follow automatically.** The compliance **rules** in
`backend/rules/*.yaml` are written against the CMMI document templates — your own
document types need their own rules, which you can author from the UI. And
`backend/data/process_map.json` is a build artifact of the demo documents;
rebuild it from yours with `scripts/corpus/build_process_map.py`.

> **Uploading through the UI is a different thing.** The Compliance Checker's
> upload extracts the file, checks it, and deletes it — it is never stored or
> indexed, and the UI says so. That transience is deliberate. Ingestion is the
> explicit, administrative path above.

---

## Configuration

Every day-to-day knob lives in one commented file, **`config.yaml`** — edit, then
restart. Precedence is **real environment variable → `config.yaml` → built-in
default**, so a single run can be overridden without touching the file
(`LLM_MODEL=other-model ./run.sh`).

| Setting | Default | What it does |
|---|---|---|
| `models.chat` | `gemma4:e4b` | Answer model (Ollama tag). |
| `models.compliance` | `gemma4:e4b` | Model used by the compliance content tier. |
| `retrieval.top_k` | `5` | Documents retrieved per question. |
| `retrieval.relevance_threshold` | `0.5` | Below this, the honest fallback fires. |
| `retrieval.collection` | `kurumsal_kalite_cmmi_chunked` | Qdrant collection queried. |
| `retrieval.late_chunking` | `true` | `false` = naive per-child encoding. |
| `services.qdrant_url` / `ollama_url` | localhost | Service endpoints. |

The memory window and rolling summary have their own `history.*` / `summary.*` knobs.
The frontend reads live values from `GET /config`, so one setting moves both the
browser and the prompt. Full mapping in `backend/config.py`.

---

## Project structure

```
config.yaml               central settings — edit here
backend/
  config.py               loads config.yaml into the environment at startup
  main.py                 FastAPI app: /chat, /chat/stream, /compliance/*, /rules, ...
  services/               embedding, chunking, late_chunking, llm, compliance,
                          compliance_judge, rules_store, history_store, doc_extract
  data/                   the corpus modules + the extracted process map
  rules/                  compliance rule sets (YAML, per document type)
  eval/                   compliance evaluation cases (the answer key)
frontend/
  index.html              loads React + Babel + the .jsx views (no build step)
  app/*.jsx               App, Sidebar, ChatThread, ComplianceChecker,
                          RulesManager, ProjectStart
  _ds_bundle.js           design-system primitives
scripts/
  ingest.py               point at any folder of documents → corpus module (+ index)
  corpus/                 build the corpus and process map from documents
  query/                  index, ask, run compliance from the CLI
data/                     the synthetic demo documents (see data/README.md)
docs/                     architecture, requirements, evaluation, question sets
tests/                    pytest suite
rag_eval/                 promptfoo setup to compare models through the RAG pipeline
run.sh                    one-command local run
```

---

## Testing and evaluation

```bash
.venv/bin/python -m pytest -q
```

Pure-logic tests (chunking, memory window, summary, process-map extraction,
history store, compliance engine) run standalone. Retrieval and end-to-end API tests
need the stack up — start `./run.sh` first, or expect connection-refused.

Beyond unit tests there are two accuracy harnesses — a labelled compliance answer key
scored as a confusion matrix, and a capability-grouped retrieval question set with an
answer key giving the expected answer and, where one exists, *the source document it
comes from*.

```bash
.venv/bin/python scripts/query/eval_compliance.py     # compliance precision/recall
python3 send_test_questions.py --url http://localhost:8013   # batch the question set
```

**Comparing two models yourself** is set up and ready: run the backend twice on
different ports with different `models.chat` values, then either grade automatically
(`cd rag_eval && npx promptfoo@latest eval` — assertions derived from the answer key,
shown side by side) or read the transcripts from the batch runner against the answer
key by hand. Both routes, an honest account of how the original automated comparison
went wrong, and what to change if you swap in your own corpus are in
[`docs/EVALUATION.md`](docs/EVALUATION.md).

---

## Documentation

| Document | What it is |
|---|---|
| [`PROCESS_LOG.md`](PROCESS_LOG.md) | A dated engineering journal — what was decided, and why. The most current record of how the implementation evolved. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How it is built: retrieval pipeline, compliance tiers, memory, API, gotchas. |
| [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) | The FR/NFR requirements, with status verified against the code. |
| [`docs/EVALUATION.md`](docs/EVALUATION.md) | How accuracy was measured — and where the measurement itself failed. |
| [`docs/TEST-QUESTIONS.md`](docs/TEST-QUESTIONS.md) | The 20-question retrieval set, grouped by the capability each probes. |
| [`docs/ANSWER-KEY.md`](docs/ANSWER-KEY.md) | Expected answers and their source documents. |
| [`docs/DEPARTMENT-QUESTIONS.md`](docs/DEPARTMENT-QUESTIONS.md) | Example questions per department, and the abbreviation glossary. |
| [`data/README.md`](data/README.md) | What the demo corpus is, and how to replace it. |

---

## Status and roadmap

**Built:** hybrid + late-chunked retrieval over a 14-document CMMI lifecycle corpus;
grounded streaming answers with citations and an honest fallback; conversation memory
with a rolling summary; local SQLite chat history; the Compliance Checker (three
tiers, rules editor, document upload, evaluation harness); and process guidance
extracted from the documents with citation checking.

**Next:**

- Two-tier model routing wired end-to-end (lean model for Q&A, larger for analysis)
- Filling the lifecycle phases the source deck names but never details
- An audit log — who asked what, which documents were used
- Metadata filtering in search (department / document type)
- The agentic layer: watch a platform → retrieve rule → check → notify with citation

---

## License

[MIT](LICENSE) — free to read, use, modify and redistribute, with attribution and
without warranty.

The bundled demo corpus under `data/` is synthetic and covered by the same licence;
it contains no third-party material. CMMI is a framework published by ISACA — the
documents here are modelled on the *structure* of such a document set, not copied
from it.

---

## Design principles

- **Local and private.** No documents, questions or answers leave the machine; no
  external AI APIs. *One caveat:* the frontend loads React and Babel from a public
  CDN, so the browser fetches those libraries. No project data is involved, but the
  app is not fully offline-capable as shipped — vendoring three files would close it.
- **Grounded and deterministic.** Answers cite documents and never fabricate;
  temperature 0, fixed seed.
- **Extracted, not authored.** The process map is derived from the real documents and
  cited, rather than written by hand — and a claim that can't be cited is dropped.
- **Measured, not eyeballed.** Retrieval and compliance both have evaluation sets.
- **CPU-friendly.** Runs on ordinary hardware (developed on a 16 GB Mac).
