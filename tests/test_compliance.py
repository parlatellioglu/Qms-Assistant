"""Compliance Checker tests — the rule set (backend/rules/*.yaml) as ground truth.

These run fully offline: the structure + traceability tiers need no Qdrant or
LLM (deterministic text/metadata checks + exact-id resolution over the in-memory
corpus). The content tier (llm_judge) is reported SKIPPED without a judge.

This doubles as the seed of the Week-4 compliance eval set: each planted defect
maps to the exact rule id it must trip.
"""
import os
import sys

import pytest

BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from data.cmmi_docs import cmmi_documents          # noqa: E402
from services.compliance import (  # noqa: E402
    check_document,
    checkable_documents,
    load_rules,
    rules_for,
)


@pytest.fixture(scope="module")
def srs():
    return next(d for d in cmmi_documents if d.get("doc_kind") == "SRS")


def _statuses(report):
    return {f.rule_id: f.status for f in report.findings}


def test_rules_load_and_bind_to_srs():
    rules = load_rules()
    srs_rules = rules_for({"doc_kind": "SRS"}, rules)
    assert len(srs_rules) >= 8, "expected the SRS seed rule set to be loaded"
    tiers = {r["tier"] for r in srs_rules}
    assert {"structure", "traceability", "content"} <= tiers, "all three tiers present"


def test_real_srs_is_compliant(srs):
    report = check_document(srs)
    assert report.verdict == "compliant", [f.rule_id for f in report.violations]
    assert not report.violations
    # every deterministic rule was actually evaluated (not skipped)
    assert report.passed
    # content-tier rules skip cleanly without a judge
    assert all(f.tier == "content" for f in report.skipped)
    assert report.score == pytest.approx(1.0)


# planted defect -> the rule id it must trip
BROKEN_CASES = {
    "revision_history_removed": ("RULE-SRS-STRUCT-001", lambda c, d: _drop(c, "revision history"), None),
    "security_section_removed": ("RULE-SRS-STRUCT-002", lambda c, d: _drop(_drop(c, "security requirements"), "güvenlik"), None),
    "bad_version": ("RULE-SRS-META-005", lambda c, d: c, "0.9"),
    "dangling_reference": ("RULE-SRS-TRACE-010", lambda c, d: c + "\nCMMI-IT-999", None),
}


def _drop(content, phrase):
    import re
    return re.sub(f"(?i){re.escape(phrase)}", "REDACTED", content)


@pytest.mark.parametrize("case", list(BROKEN_CASES))
def test_planted_defect_trips_expected_rule(srs, case):
    expected_rule, mutate_content, new_version = BROKEN_CASES[case]
    broken = dict(srs)
    broken["content"] = mutate_content(srs["content"], srs)
    if new_version is not None:
        broken["version"] = new_version

    statuses = _statuses(check_document(broken))
    assert statuses[expected_rule] == "fail", f"{case}: expected {expected_rule} to fail"


def test_blocker_failure_forces_non_compliant(srs):
    broken = dict(srs)
    broken["content"] = _drop(srs["content"], "revision history")  # blocker rule
    report = check_document(broken)
    assert report.has_blocker_fail
    assert report.verdict == "non_compliant"


def test_score_excludes_skipped_content_rules(srs):
    # With no judge, content rules skip and must not drag the score below 1.0
    report = check_document(srs)
    assert report.skipped
    assert report.score == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
#  Checkable documents (corpus + incomplete drafts) — what the UI checker runs
#  against via GET /compliance/documents and POST /compliance/check.
# --------------------------------------------------------------------------- #
def test_checkable_documents_include_corpus_and_draft():
    docs = checkable_documents()
    ids = {d["id"] for d in docs}
    assert "CMMI-IT-005" in ids, "published corpus documents must be checkable"
    draft = next((d for d in docs if d.get("is_draft")), None)
    assert draft is not None, "the incomplete draft(s) must be checkable"
    assert draft["id"] == "CMMI-IT-005-DRAFT"
    # drafts are listed first so the interesting examples surface in the UI
    assert docs[0].get("is_draft")


def test_draft_srs_is_non_compliant_with_expected_violations():
    draft = next(d for d in checkable_documents() if d.get("id") == "CMMI-IT-005-DRAFT")
    report = check_document(draft)
    assert report.verdict == "non_compliant"
    assert report.has_blocker_fail          # missing Revision History (blocker)
    statuses = _statuses(report)
    for rid in ("RULE-SRS-STRUCT-001", "RULE-SRS-STRUCT-002",
                "RULE-SRS-META-005", "RULE-SRS-TRACE-010"):
        assert statuses[rid] == "fail", f"{rid} should fail on the draft"
    # the signature block and references it *does* have should still pass
    assert statuses["RULE-SRS-STRUCT-003"] == "pass"
