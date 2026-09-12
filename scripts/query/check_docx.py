#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check a real document FILE (data/…/*.docx) against the compliance rule set.

This is the on-disk counterpart to check_compliance.py (which uses an in-memory
copy). It flattens the Word file to text with the same extractor the corpus
build uses, attaches the metadata the rules need (doc_kind, version, …), then
runs check_document — auto-loading backend/rules/*.yaml and selecting rules by
doc_kind. Defaults to the incomplete draft SRS.

    .venv/bin/python scripts/query/check_docx.py          # the bundled draft SRS
    .venv/bin/python scripts/query/check_docx.py path/to/other.docx --kind SRS
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "corpus"))  # extract_docx lives here
sys.path.insert(0, os.path.join(ROOT, "scripts", "query"))     # reuse print_report

from build_cmmi_corpus import extract_docx        # noqa: E402  (same flattening as the corpus)
from services.compliance import check_document    # noqa: E402
from check_compliance import print_report         # noqa: E402

DEFAULT_DOC = os.path.join(ROOT, "data", "CMMI_drafts", "CMMI-IT-005_SRS_incomplete.docx")


def build_doc(path: str, doc_kind: str, version: str, status: str) -> dict:
    """Flatten a Word file and attach the metadata the rules read.

    Content comes from the file; metadata (doc_kind, version, status) is supplied
    here — exactly as the corpus build attaches it via its META table, and as an
    upload form would supply it in the Week-5 UI flow.
    """
    return {
        "id": os.path.splitext(os.path.basename(path))[0],
        "doc_kind": doc_kind,
        "version": version,
        "status": status,
        "title": os.path.basename(path),
        "content": extract_docx(path),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=DEFAULT_DOC, help="path to a .docx file")
    ap.add_argument("--kind", default="SRS", help="doc_kind to check against (default: SRS)")
    ap.add_argument("--version", default="0.9", help="document version metadata")
    ap.add_argument("--status", default="draft", help="document status metadata")
    ap.add_argument("--judge", action="store_true",
                    help="run the content-tier LLM judge via Ollama (needs Ollama running)")
    ap.add_argument("--model", default=None, help="override the judge model (default: gemma4:e4b)")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        sys.exit(f"File not found: {args.path}\n"
                 f"Pass a path to a .docx, or use one of the bundled drafts in data/CMMI_drafts/.")

    judge = None
    if args.judge:
        from services.compliance_judge import make_ollama_judge
        judge = make_ollama_judge(model=args.model) if args.model else make_ollama_judge()

    doc = build_doc(args.path, args.kind, args.version, args.status)
    report = check_document(doc, judge=judge)
    print_report(f"FILE: {os.path.relpath(args.path, ROOT)}  (doc_kind={args.kind})", report)


if __name__ == "__main__":
    main()
