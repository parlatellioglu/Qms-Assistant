#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compliance Checker evaluation harness.

Runs the checker over every case in backend/eval/compliance_cases.yaml and scores
its output against the hand-labelled `expected` verdicts, so accuracy is measured
rather than eyeballed: change a rule or the judge prompt, re-run, and see whether
false positives/negatives went down.

"Positive" = a defect flagged (a rule FAILs). So, per rule id:
    TP  expected fail, got fail   (correctly caught)
    FP  expected pass, got fail   (false alarm)          <- a false positive
    FN  expected fail, got pass   (missed defect)        <- a false negative
    TN  expected pass, got pass   (correctly clean)
precision = TP/(TP+FP)   recall = TP/(TP+FN)

The deterministic tiers (structure, traceability) are graded on every run. The
content tier (llm_judge) is graded only with --content, which wires the local
Ollama judge (backend/services/compliance_judge.py); without it those rules come
back `skipped` and are reported as UNGRADED, not as failures.

    .venv/bin/python scripts/query/eval_compliance.py            # deterministic tiers
    .venv/bin/python scripts/query/eval_compliance.py --content  # + LLM-as-judge

Exit code is non-zero if any case has a false positive, false negative or error,
so it can gate a change to the rules or the judge prompt.
"""
import argparse
import os
import sys
from collections import defaultdict

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from services.compliance import check_document, checkable_documents, load_rules  # noqa: E402

CASES_PATH = os.path.join(BACKEND, "eval", "compliance_cases.yaml")

PASS, FAIL, SKIPPED, ERROR = "pass", "fail", "skipped", "error"


def load_cases(path=CASES_PATH):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or []


def resolve_doc(case, by_id):
    """Return the document dict for a case (doc_ref id or inline doc_inline)."""
    if case.get("doc_inline") is not None:
        return case["doc_inline"]
    ref = case.get("doc_ref")
    if ref not in by_id:
        raise KeyError(f"case {case.get('name')!r}: doc_ref {ref!r} is not a checkable document")
    return by_id[ref]


def classify(expected: str, actual: str) -> str:
    """Bucket one (expected, actual) pair. 'fail' is the positive class."""
    if actual == SKIPPED:
        return "ungraded"          # content tier not run
    if actual == ERROR:
        return "error"
    if expected == FAIL and actual == FAIL:
        return "TP"
    if expected == PASS and actual == FAIL:
        return "FP"
    if expected == FAIL and actual == PASS:
        return "FN"
    if expected == PASS and actual == PASS:
        return "TN"
    return "error"                 # unexpected label in the eval file


def main() -> int:
    ap = argparse.ArgumentParser(description="Score the Compliance Checker against the eval set.")
    ap.add_argument("--content", action="store_true",
                    help="also grade the content tier via the local Ollama judge (needs Ollama).")
    ap.add_argument("--cases", default=CASES_PATH, help="path to the eval cases YAML.")
    args = ap.parse_args()

    cases = load_cases(args.cases)
    by_id = {d["id"]: d for d in checkable_documents()}
    tier_of = {r["id"]: r.get("tier", "?") for r in load_rules()}

    judge = None
    if args.content:
        from services.compliance_judge import make_ollama_judge
        judge = make_ollama_judge()
        print(f"Grading content tier via Ollama judge ({os.getenv('COMPLIANCE_MODEL', 'gemma4:e4b')}).\n")
    else:
        print("Deterministic tiers only (structure + traceability). "
              "Pass --content to grade the LLM-as-judge tier.\n")

    # buckets[tier][kind] = count ; also keep the mismatches to print.
    buckets = defaultdict(lambda: defaultdict(int))
    mismatches = []   # (case_name, rule_id, tier, expected, actual, kind)
    ungraded = 0

    for case in cases:
        name = case.get("name", "?")
        doc = resolve_doc(case, by_id)
        report = check_document(doc, judge=judge)
        actual = {f.rule_id: f.status for f in report.findings}
        expected = case.get("expected", {})

        case_bad = []
        for rule_id, exp in expected.items():
            act = actual.get(rule_id)
            if act is None:
                # rule labelled but not applicable to this doc — a mislabelled case.
                kind, act = "error", "(not evaluated)"
            else:
                kind = classify(exp, act)
            tier = tier_of.get(rule_id, "?")
            if kind == "ungraded":
                ungraded += 1
                continue
            buckets[tier][kind] += 1
            buckets["ALL"][kind] += 1
            if kind in ("FP", "FN", "error"):
                case_bad.append((rule_id, tier, exp, act, kind))
                mismatches.append((name, rule_id, tier, exp, act, kind))

        flag = "  <-- mismatches" if case_bad else ""
        print(f"• {name:24s} verdict={report.verdict:20s} "
              f"({len(expected)} labels){flag}")

    # ------------------------------------------------------------------ #
    #  Mismatch detail
    # ------------------------------------------------------------------ #
    if mismatches:
        print("\nMismatches (case · rule · expected -> actual · kind):")
        for name, rule_id, _tier, exp, act, kind in mismatches:
            print(f"  [{kind:5s}] {name:24s} {rule_id:20s} {exp} -> {act}")

    # ------------------------------------------------------------------ #
    #  Per-tier + overall confusion / precision / recall
    # ------------------------------------------------------------------ #
    def line(tier):
        b = buckets[tier]
        tp, fp, fn, tn = b["TP"], b["FP"], b["FN"], b["TN"]
        err = b["error"]
        prec = tp / (tp + fp) if (tp + fp) else float("nan")
        rec = tp / (tp + fn) if (tp + fn) else float("nan")
        return (f"  {tier:13s} TP={tp:3d} FP={fp:3d} FN={fn:3d} TN={tn:3d} err={err:2d}"
                f"   precision={prec:.2f}  recall={rec:.2f}")

    print("\nScores (positive class = defect flagged):")
    for tier in ("structure", "traceability", "content"):
        if buckets[tier]:
            print(line(tier))
    print(line("ALL"))
    if ungraded:
        print(f"\n  {ungraded} content-tier label(s) UNGRADED "
              f"(run with --content to grade them).")

    b = buckets["ALL"]
    bad = b["FP"] + b["FN"] + b["error"]
    print(f"\n{'FAIL' if bad else 'OK'}: "
          f"{b['FP']} false positive(s), {b['FN']} false negative(s), {b['error']} error(s).")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
