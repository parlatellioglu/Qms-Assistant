# Requirements — QMS Assistant

The functional and non-functional requirements the system was built against.

Originally authored in Turkish alongside the product (which is Turkish-facing);
translated here for readability. Status is stated against the **current code**, not
against the original plan — several items that were planned at authoring time have
since shipped, and a few turned out to be partial rather than done.

| Status | Meaning |
|---|---|
| ✅ | Implemented and working |
| ◐ | Partially implemented — see the note |
| ○ | Planned, not built |

---

## 1. Functional requirements

### Knowledge assistant (Q&A)

| # | Requirement | Status |
|---|---|---|
| FR-1 | Questions can be asked in Turkish or English in everyday language. Answers are grounded **only** in the organisation's own documents, and each answer shows which document it came from. | ✅ |
| FR-2 | If no relevant document is found, the assistant says so explicitly and falls back to a general answer. It never fabricates. | ✅ |
| FR-3 | The assistant shows how the answer was produced — how many documents it consulted, how long it took. | ✅ |
| FR-4 | The assistant remembers earlier messages in the same conversation, so follow-up questions build on previous ones. | ✅ |

### Adding documents

| # | Requirement | Status |
|---|---|---|
| FR-5 | Word, Excel, PowerPoint and similar formats can be added; the assistant reads all of them. | ✅ |
| FR-6 | Each document carries metadata — department, type, version, status, author, language, tags. | ✅ |
| FR-7 | Long documents are automatically restructured in the background so the assistant can reach the right passage quickly. | ✅ |
| FR-8 | Users can upload documents directly from the interface. | ◐ **By design, split in two.** Upload-and-check works in the UI, and the file is deleted afterwards — that transience is a privacy property. Adding documents to the searchable corpus is a separate administrative step (`scripts/ingest.py`, with `--append` for one document at a time). A UI for ingestion is on the roadmap. |

### Search

| # | Requirement | Status |
|---|---|---|
| FR-9 | Searches on both the words used and the meaning of the question. | ✅ Hybrid dense + sparse, fused with RRF. |
| FR-10 | Selects the most relevant documents and grounds the answer in the appropriate sections of them. | ✅ Parent/child chunking with per-document best-child scoring. |
| FR-11 | Searches can be narrowed by criteria such as department or document type. | ○ Metadata is stored and displayed, but not used as a search filter. |

### Answer generation

| # | Requirement | Status |
|---|---|---|
| FR-12 | Combines what it finds and writes the answer, streamed as it is produced. | ✅ Extended beyond the original wording: the answer is written in the **question's** language rather than always Turkish. |
| FR-13 | If documents contradict each other, the assistant says so and defers to the most current/authoritative one. | ◐ The prompt instructs this and the model follows it in practice, but nothing enforces or tests it. |
| FR-14 | Can operate at different levels for simple questions versus deeper analysis. | ◐ Two models are configured (a lean one for Q&A, a larger one for the compliance content tier), but routing is per-feature, not per-question. |

### Interface

| # | Requirement | Status |
|---|---|---|
| FR-15 | The web interface shows answers immediately, presents the supporting documents as cards with preview, and makes the process visible. | ✅ |
| FR-16 | The interface offers document upload, compliance results, a role-based view and chat history. | ✅ |

### Compliance checking

| # | Requirement | Status |
|---|---|---|
| FR-17 | Compares written or uploaded content against quality rules and presents a structured result (compliant / violation / missing / risk / suggestion / score). | ✅ Three tiers: deterministic structure, traceability, and an LLM-as-judge content tier. |
| FR-18 | Adjusts what is visible per role; records who decided what on which document; supports approval and version tracking. | ○ The role lens is presentational only — every role still searches everything. No audit log or approval workflow. |

### Guidance

| # | Requirement | Status |
|---|---|---|
| FR-19 | Directs an employee, according to their role, to the relevant documents, tasks and questions they might ask. | ✅ Role-aware starter questions and a role lens over the process map. |
| FR-20 | Shows the procedurally correct next steps and the documents due, based on the project's current phase. | ✅ The lifecycle is **extracted from the loaded documents**, with every item cited or dropped. |

---

## 2. Non-functional requirements

### Usability and reliability

| # | Requirement | Status |
|---|---|---|
| NFR-1 | Supports Turkish and English; answers are verifiable through cited sources. | ✅ The original required answers *in Turkish*; the assistant now replies in the language of the question, which better serves the stated bilingual requirement. |
| NFR-2 | The same question always yields the same, consistent answer. | ✅ Temperature 0, fixed seed. |
| NFR-3 | Falls back to a general answer when information is insufficient; fails with a clear message rather than crashing. | ✅ |
| NFR-4 | Information added to the system is stored persistently and survives a restart. | ✅ Qdrant for vectors, SQLite for conversations. |

### Speed and efficiency

| # | Requirement | Status |
|---|---|---|
| NFR-5 | Answers appear immediately, streamed, and the assistant is kept warm for fast response. | ✅ SSE streaming; the model is held resident between queries. |
| NFR-6 | Runs on ordinary work computers, without dedicated high-powered servers. | ✅ Developed on a 16 GB laptop, CPU-only. |
| NFR-7 | How many documents the assistant consults per answer is configurable. | ✅ `retrieval.top_k` |
| NFR-8 | How much information it considers at once is configurable. | ✅ `generation.num_ctx` |

### Security and independence

| # | Requirement | Status |
|---|---|---|
| NFR-9 | No document, question or answer leaves the organisation; everything runs in-house. | ✅ No external AI APIs. See the note below. |
| NFR-10 | The models — one for everyday Q&A, one for deeper content and compliance analysis — can be swapped as needed. | ✅ `models.chat` / `models.compliance` |
| NFR-11 | Changing these settings requires no code changes; an administrator can adjust them directly. | ✅ One commented `config.yaml`; real environment variables still override it. |

### Organisational

| # | Requirement | Status |
|---|---|---|
| NFR-12 | Runs on the organisation's own machines and starts easily. | ✅ `./run.sh` |
| NFR-13 | Correct operation is verified by regular tests. | ✅ pytest suite; plus evaluation sets for retrieval and compliance accuracy. |

### Legal and ethical

| # | Requirement | Status |
|---|---|---|
| NFR-14 | Confidential corporate data does not leave the organisation; the system is compliant with Turkish data-protection law (KVKK). | ✅ |
| NFR-15 | The assistant does not fabricate; it gives only document-grounded, cited answers. | ✅ Enforced by a relevance threshold plus an explicit fallback notice. |

---

## Note on NFR-9 / NFR-14

No document, question or answer is sent to any external service, and no external AI
API is called — this is a hard architectural constraint, not a preference. Retrieval,
embedding, generation and storage all run locally.

One caveat worth stating plainly: the frontend loads React and Babel from a public
CDN at page load, so the **browser** makes outbound requests for those libraries.
No project data is involved, but the application is not fully offline-capable as
shipped. Vendoring those three files would close the gap.
