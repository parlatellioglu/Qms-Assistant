# Test samples — Compliance Checker uploads

Sample documents for manually testing the Compliance Checker's **upload** flow
(Uyum Denetimi → dosya yükle → doc kind **SRS** → Denetle). These are *not* shown
in the UI and are *not* indexed into the RAG — they exist only so you have real
files to upload when trying the checker.

**SRS** and **BUR** have rule sets today; all four samples here are SRS variants,
which exercise different outcomes:

| File | What it is | Expect |
| --- | --- | --- |
| `CMMI-IT-005_SRS_complete.docx` | The full, published SRS | Mostly passing |
| `CMMI-IT-005_SRS_incomplete.docx` | Draft with sections missing | Several "eksik" (missing) |
| `CMMI-IT-005_SRS_content_gaps.docx` | Sections present but thin content | Fails show up under the AI content tier |
| `CMMI-IT-005_SRS_skeleton.docx` | Headings only, little body | Most rules fail |

These are copies of the corpus source files under `data/CMMI_completed/` and
`data/CMMI_drafts/`; editing them here doesn't affect the indexed corpus.
