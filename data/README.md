# Demo corpus — synthetic documents

**Every document in this folder is synthetic.** They were written for this project
so the assistant has a realistic quality-management corpus to retrieve from, index,
and check rules against. They contain **no real company documents, no real people,
and no real business data**. The organisation, the project, the staff names, the
identifiers and the integrations in them are all invented.

People and organisations are deliberately named as obvious placeholders rather than
realistic-sounding names, so no reader can mistake them for real individuals. They
are Turkish, because the documents they appear in are Turkish:

- **`Kişi 1` … `Kişi 18`** — *kişi* = "person"
- **`Şirket 1`, `Şirket 2`** — *şirket* = "company"

Each placeholder maps to one consistent role throughout (`Kişi 1` is the Project
Manager, `Kişi 2` the Software Architect, and so on), because the traceability rules
and the evaluation answer key depend on the same person holding the same role across
documents. Telephone numbers use the reserved `555` range.

They are modelled on the *structure* of a CMMI / SDLC document set — a technical
requirements form, a project management plan, a requirements specification, design,
test plans and cases, acceptance certificates, a close-out report — because that
structure is what makes the retrieval and compliance problems interesting: long
documents, heavy tables, cross-references between documents, and rules that only
make sense against a real template.

## What's here

| Folder | Contents | Used by |
|---|---|---|
| `CMMI_completed/` | 11 published lifecycle documents for one fictional project | the RAG corpus + traceability rules |
| `CMMI_drafts/` | 3 deliberately incomplete SRS drafts | Compliance Checker test material |
| `CMMI_xlsx_pptx/` | SAT/UAT test-case spreadsheets | the RAG corpus |
| `small_docs/` | 13 short quality policies/procedures with YAML frontmatter | the small-document demo collection |

Two things are deliberately **not** in the repository:

- **`SDLC Process_1.pptx`** — the process deck the lifecycle is extracted from. It's
  3.8 MB, its extracted text already ships inside `backend/data/cmmi_docs.py`, and
  `backend/data/process_map.json` ships prebuilt. Rebuilding the process map from
  source therefore needs a deck of your own.
- **The scripts that fabricated this content.** They author the fictional data and
  aren't part of the product. The pipeline that *ingests* documents — which is the
  part that matters — is in `scripts/corpus/` and `scripts/ingest.py`.

## Using your own documents instead

Nothing here is load-bearing for the system itself; it's demo data. To point the
assistant at a real corpus:

```bash
# see what would be picked up
.venv/bin/python scripts/ingest.py /path/to/your/documents --dry-run

# build a corpus module and index it
QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/ingest.py \
    /path/to/your/documents --out backend/data/my_docs.py \
    --index --collection my_docs
```

Then set `retrieval.collection: my_docs` in `config.yaml` and restart.

`.docx`, `.xlsx`, `.pptx`, `.md` and `.txt` are supported. Documents carrying YAML
frontmatter (like `small_docs/`) have their declared `title`, `id`, `department`,
`document_type`, `status`, `version`, `author`, `created_date` and `tags` honoured
rather than guessed.
