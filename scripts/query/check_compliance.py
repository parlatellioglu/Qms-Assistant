#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hand-run the Compliance Checker against the SRS (CMMI-IT-005) and a deliberately
broken copy — the walking skeleton for the Compliance Checker.

Deterministic (structure) and traceability tiers run with no Qdrant/LLM; the
content tier is reported as skipped until the analysis model is wired. Shows the
rule set (backend/rules/srs.yaml) catching planted defects, each mapped to the
exact rule id that fires.

    .venv/bin/python scripts/query/check_compliance.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from data.cmmi_docs import cmmi_documents        # noqa: E402
from services.compliance import check_document    # noqa: E402

_ICON = {"pass": "✓", "fail": "✗", "skipped": "•", "error": "!"}


def break_srs(srs: dict) -> dict:
    """Plant four defects, each of which should trip a specific rule."""
    broken = dict(srs)
    content = srs["content"]
    # Case-insensitive so incidental mentions (e.g. the "Security requirements | 8"
    # row in the Requirements Count table) can't keep section_present passing.
    content = re.sub(r"(?i)revision history", "REDACTED", content)   # -> STRUCT-001 (blocker)
    content = re.sub(r"(?i)security requirements", "REDACTED", content)  # -> STRUCT-002
    content = re.sub(r"(?i)güvenlik", "REDACTED", content)
    content += "\nEksik referans: CMMI-IT-999 (mevcut değil)."       # -> TRACE-010
    broken["content"] = content
    broken["version"] = "0.9"                                       # -> META-005
    broken["id"] = "CMMI-IT-005-BROKEN"
    return broken


def print_report(title: str, report) -> None:
    print(f"\n{'=' * 72}\n{title}")
    print(f"  doc={report.doc_id}  kind={report.doc_kind}  "
          f"verdict={report.verdict.upper()}  score={report.score:.0%}")
    c = report.to_dict()["counts"]
    print(f"  passed={c['passed']}  violations={c['violations']}  "
          f"missing={c['missing']}  skipped={c['skipped']}  errors={c['errors']}")
    print("-" * 72)
    for f in report.findings:
        print(f"  {_ICON[f.status]} {f.status.upper():7s} [{f.severity:7s} {f.tier:12s}] "
              f"{f.rule_id}")
        print(f"        {f.detail}")
        if f.fix_hint:
            print(f"        ↳ düzeltme: {f.fix_hint}")


def main() -> None:
    srs = next(d for d in cmmi_documents if d.get("doc_kind") == "SRS")

    print_report("REAL SRS (CMMI-IT-005) — approved reference", check_document(srs))
    print_report("BROKEN SRS — 4 planted defects", check_document(break_srs(srs)))

    print(f"\n{'=' * 72}")
    print("Content-tier (llm_judge) rules show as SKIPPED: they need the Week-4 "
          "analysis model,\ninjected via check_document(..., judge=<callable>).")


if __name__ == "__main__":
    main()
