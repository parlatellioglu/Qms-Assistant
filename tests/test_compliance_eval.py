"""Guards the compliance eval set (backend/eval/compliance_cases.yaml).

Runs offline: it grades only the deterministic tiers (structure + traceability).
Content-tier labels come back `skipped` without a judge and are not asserted here
— they are exercised by scripts/query/eval_compliance.py --content when Ollama is
up. The point of this test is that a change to the rules can't silently
invalidate the eval set's answer key for the tiers we CAN check for free.
"""
import os
import sys

import pytest
import yaml

BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from services.compliance import check_document, checkable_documents  # noqa: E402

CASES_PATH = os.path.join(BACKEND, "eval", "compliance_cases.yaml")


def _load_cases():
    with open(CASES_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or []


def _resolve(case, by_id):
    if case.get("doc_inline") is not None:
        return case["doc_inline"]
    return by_id[case["doc_ref"]]


CASES = _load_cases()
BY_ID = {d["id"]: d for d in checkable_documents()}


def test_eval_set_is_nonempty_and_has_both_polarities():
    verdicts = set()
    for case in CASES:
        doc = _resolve(case, BY_ID)
        verdicts.add(check_document(doc).verdict)
    # must contain at least one clean and one broken document to measure both
    # false positives and false negatives.
    assert "compliant" in verdicts
    assert {"partially_compliant", "non_compliant"} & verdicts


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_deterministic_labels_match(case):
    doc = _resolve(case, BY_ID)
    actual = {f.rule_id: f.status for f in check_document(doc).findings}
    for rule_id, expected in case["expected"].items():
        got = actual.get(rule_id)
        assert got is not None, f"{case['name']}: rule {rule_id} not evaluated on this doc"
        if got == "skipped":
            continue  # content tier — not graded offline
        assert got == expected, (
            f"{case['name']}: {rule_id} expected {expected!r} but checker gave {got!r}"
        )
