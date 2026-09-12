"""Compliance Checker engine — the rule set is the primary basis.

Loads rule sets from ``backend/rules/*.yaml``, selects the rules whose
``applies_to.doc_kind`` matches a document, runs each rule's executor, and
aggregates the findings into a :class:`ComplianceReport` (a severity-weighted
score plus compliant / violation / missing / skipped breakdowns).

Every finding traces back to a rule ``id`` — the checker never decides on its
own what "compliant" means; it only evaluates a document against an authored
rule. See ``backend/rules/README.md`` for the rule schema.

Tiers (run cheapest-first; a blocker structural failure short-circuits the rest):
  structure    — deterministic checks on the document text/metadata (no LLM)
  traceability — exact-id resolution against the in-memory corpus (no LLM)
  content      — rule-guided LLM-as-judge; needs an injected ``judge`` callable,
                 otherwise reported as ``skipped`` (needs the analysis model)

structure + traceability need no external services, so the checker runs and is
testable fully offline. ``judge`` is the seam where the Week-4 analysis model
plugs in.
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import yaml

RULES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules")

# Relative weight of each severity when scoring; a failed blocker also forces the
# overall verdict to non_compliant regardless of the weighted score.
SEVERITY_WEIGHT = {"blocker": 8, "high": 4, "medium": 2, "low": 1}

# Presence-style structural checks whose failure means something is *missing*
# (vs. present-but-wrong). Used to split violations into a "missing" bucket.
_MISSING_CHECK_TYPES = {"section_present", "revision_history", "signature_block"}

# Finding statuses.
PASS, FAIL, SKIPPED, ERROR = "pass", "fail", "skipped", "error"


@dataclass
class Finding:
    rule_id: str
    tier: str
    severity: str
    statement: str
    status: str          # PASS | FAIL | SKIPPED | ERROR
    detail: str
    fix_hint: Optional[str] = None   # carried on FAIL so the UI can show the fix


@dataclass
class ComplianceReport:
    doc_id: str
    doc_kind: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def violations(self) -> List[Finding]:
        return [f for f in self.findings if f.status == FAIL]

    @property
    def passed(self) -> List[Finding]:
        return [f for f in self.findings if f.status == PASS]

    @property
    def skipped(self) -> List[Finding]:
        return [f for f in self.findings if f.status == SKIPPED]

    @property
    def errors(self) -> List[Finding]:
        return [f for f in self.findings if f.status == ERROR]

    @property
    def missing(self) -> List[Finding]:
        """Violations that are presence failures (a required part is absent)."""
        return [f for f in self.violations if f.rule_check_type in _MISSING_CHECK_TYPES]

    @property
    def has_blocker_fail(self) -> bool:
        return any(f.status == FAIL and f.severity == "blocker" for f in self.findings)

    @property
    def score(self) -> float:
        """Severity-weighted pass ratio over *evaluated* rules (0..1).

        Skipped (content-tier not run) and errored rules are excluded from the
        denominator so an un-wired analysis model doesn't drag the score down.
        Returns 1.0 when nothing was evaluated.
        """
        evaluated = [f for f in self.findings if f.status in (PASS, FAIL)]
        denom = sum(SEVERITY_WEIGHT[f.severity] for f in evaluated)
        if denom == 0:
            return 1.0
        num = sum(SEVERITY_WEIGHT[f.severity] for f in evaluated if f.status == PASS)
        return num / denom

    @property
    def verdict(self) -> str:
        if self.has_blocker_fail:
            return "non_compliant"
        if self.violations:
            return "partially_compliant"
        return "compliant"

    @staticmethod
    def bucket_of(f: Finding) -> str:
        """Disjoint UI bucket for a finding.

        Splits failures into ``missing`` (a required part is absent) vs
        ``violations`` (present but wrong) so the UI can colour and filter them
        separately — unlike ``counts.violations`` below, which counts *all*
        failures (missing included) for the top-line verdict math.
        """
        if f.status == PASS:
            return "passed"
        if f.status == SKIPPED:
            return "skipped"
        if f.status == ERROR:
            return "errors"
        return ("missing" if getattr(f, "rule_check_type", None) in _MISSING_CHECK_TYPES
                else "violations")

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "doc_kind": self.doc_kind,
            "verdict": self.verdict,
            "score": round(self.score, 3),
            "counts": {
                "passed": len(self.passed),
                "violations": len(self.violations),
                "missing": len(self.missing),
                "skipped": len(self.skipped),
                "errors": len(self.errors),
            },
            "findings": [{**f.__dict__, "bucket": self.bucket_of(f)} for f in self.findings],
        }


# Findings need the originating check type (to bucket "missing"); attach it
# dynamically so the dataclass stays about the user-facing shape.
def _tag_check_type(finding: Finding, check_type: str) -> Finding:
    finding.rule_check_type = check_type  # type: ignore[attr-defined]
    return finding


# --------------------------------------------------------------------------- #
#  Rule loading / selection
# --------------------------------------------------------------------------- #
def load_rules(rules_dir: str = RULES_DIR) -> List[dict]:
    """Load and concatenate every rule from ``rules_dir/*.yaml``."""
    rules: List[dict] = []
    for path in sorted(glob.glob(os.path.join(rules_dir, "*.yaml"))):
        loaded = yaml.safe_load(open(path, encoding="utf-8")) or []
        rules.extend(loaded)
    return rules


def rules_for(doc: dict, rules: List[dict]) -> List[dict]:
    """Rules whose ``applies_to.doc_kind`` matches the document's doc_kind."""
    kind = doc.get("doc_kind")
    return [r for r in rules if r.get("applies_to", {}).get("doc_kind") == kind]


def checkable_documents() -> List[dict]:
    """Documents the Compliance Checker can be run against.

    The published CMMI corpus plus the deliberately incomplete drafts (test
    material, flagged ``is_draft``). Drafts come first so the interesting
    (rule-tripping) examples are easy to find in the UI. Drafts are *not* part of
    the searchable RAG corpus and are never indexed into Qdrant.
    """
    from services.corpus import corpus_documents, draft_documents
    return list(draft_documents()) + list(corpus_documents())


# --------------------------------------------------------------------------- #
#  Executors — one per check.type. Each returns (status, detail).
#  ctx carries {"index": {id: doc}, "corpus": [...], "judge": callable|None}.
# --------------------------------------------------------------------------- #
def _check_section_present(rule, doc, *_):
    names = rule["check"]["any_of"]
    content = doc.get("content", "").lower()
    hit = next((n for n in names if n.lower() in content), None)
    if hit:
        return PASS, f"Section found: {hit!r}."
    return FAIL, f"None of the expected sections are present: {names}."


_REV_ROW = re.compile(r"^\s*\d+\.\d+\s*\|")


def _check_revision_history(rule, doc, *_):
    min_versions = rule["check"].get("min_versions", 1)
    lines = doc.get("content", "").splitlines()
    header = next(
        (i for i, ln in enumerate(lines)
         if "revision history" in ln.lower() or "revizyon" in ln.lower()),
        None,
    )
    if header is None:
        return FAIL, "No Revision History heading found."
    count = 0
    for ln in lines[header + 1:]:
        if _REV_ROW.match(ln):
            count += 1
        elif count:            # rows are contiguous; stop after the block ends
            break
    if count >= min_versions:
        return PASS, f"Found {count} version row(s) (minimum {min_versions})."
    return FAIL, f"Only {count} version row(s) present ({min_versions} required)."


def _check_signature_block(rule, doc, *_):
    roles = rule["check"]["roles"]
    content = doc.get("content", "").lower()
    missing = [r for r in roles if r.lower() not in content]
    if not missing:
        return PASS, f"All sign-off roles present: {roles}."
    return FAIL, f"Missing sign-off roles: {missing}."


def _check_metadata_regex(rule, doc, *_):
    fieldname = rule["check"]["field"]
    pattern = rule["check"]["pattern"]
    value = str(doc.get(fieldname, ""))
    if re.search(pattern, value):
        return PASS, f"{fieldname}={value!r} matches the expected format."
    return FAIL, f"{fieldname}={value!r} does not match the expected format ({pattern})."


def _check_refs_resolve(rule, doc, ctx):
    pattern = rule["check"]["id_pattern"]
    require_status = rule["check"].get("require_status")
    index = ctx["index"]
    refs = set(re.findall(pattern, doc.get("content", ""))) - {doc.get("id")}
    problems = []
    for ref in sorted(refs):
        target = index.get(ref)
        if target is None:
            problems.append(f"{ref} (not in the corpus)")
        elif require_status and target.get("status") != require_status:
            problems.append(f"{ref} (status={target.get('status')}, expected={require_status})")
    if not refs:
        return PASS, "No references to resolve."
    if not problems:
        return PASS, f"All {len(refs)} reference(s) resolved."
    return FAIL, "Unresolved references: " + "; ".join(problems)


def _check_id_trace(rule, doc, ctx):
    """Coarse traceability: the document carries ids of ``from_pattern`` and a
    document of ``to_doc_kind`` exists to trace them to. Item-level matrix
    matching is future work; this catches a missing trace target entirely."""
    from_pattern = rule["check"]["from_pattern"]
    to_kind = rule["check"]["to_doc_kind"]
    from_ids = sorted(set(re.findall(from_pattern, doc.get("content", ""))))
    target = next((d for d in ctx["corpus"] if d.get("doc_kind") == to_kind), None)
    if not from_ids:
        return FAIL, f"No {from_pattern} ids found to trace."
    if target is None:
        return FAIL, f"The trace target ({to_kind}) is not in the corpus."
    return PASS, (f"{len(from_ids)} {from_pattern} id(s) trace to the {to_kind} "
                  f"document ({target['id']}).")


def _check_llm_judge(rule, doc, ctx):
    """Content-tier: delegate to an injected judge, else skip.

    A judge is ``callable(rule, doc) -> (status, detail)``. Without one (the
    default, e.g. no analysis model wired), the rule is reported SKIPPED so the
    deterministic tiers still produce a full report offline.
    """
    judge = ctx.get("judge")
    if judge is None:
        return SKIPPED, "Content evaluation needs the analysis model (skipped)."
    return judge(rule, doc)


CHECKS: Dict[str, Callable] = {
    "section_present": _check_section_present,
    "revision_history": _check_revision_history,
    "signature_block": _check_signature_block,
    "metadata_regex": _check_metadata_regex,
    "refs_resolve": _check_refs_resolve,
    "id_trace": _check_id_trace,
    "llm_judge": _check_llm_judge,
}


# --------------------------------------------------------------------------- #
#  Runner
# --------------------------------------------------------------------------- #
def check_document(
    doc: dict,
    rules: Optional[List[dict]] = None,
    corpus: Optional[List[dict]] = None,
    judge: Optional[Callable] = None,
) -> ComplianceReport:
    """Run every applicable rule against ``doc`` and return a report.

    ``rules`` defaults to the loaded ``backend/rules/*.yaml``; ``corpus`` (for
    traceability resolution) defaults to the CMMI corpus. ``judge`` enables the
    content tier. Rules run in tier order (structure → traceability → content).
    """
    if rules is None:
        rules = load_rules()
    if corpus is None:
        from services.corpus import corpus_documents
        corpus = corpus_documents()

    ctx = {"corpus": corpus, "index": {d["id"]: d for d in corpus}, "judge": judge}
    report = ComplianceReport(doc_id=doc.get("id", "?"), doc_kind=doc.get("doc_kind", "?"))

    tier_order = {"structure": 0, "traceability": 1, "content": 2}
    applicable = sorted(rules_for(doc, rules), key=lambda r: tier_order.get(r.get("tier"), 9))

    for rule in applicable:
        check_type = rule["check"]["type"]
        executor = CHECKS.get(check_type)
        if executor is None:
            status, detail = ERROR, f"Unknown check type: {check_type!r}"
        else:
            try:
                status, detail = executor(rule, doc, ctx)
            except Exception as exc:  # a bad rule must not sink the whole run
                status, detail = ERROR, f"{type(exc).__name__}: {exc}"
        finding = Finding(
            rule_id=rule["id"],
            tier=rule.get("tier", "?"),
            severity=rule.get("severity", "medium"),
            statement=" ".join(rule.get("statement", "").split()),
            status=status,
            detail=detail,
            fix_hint=" ".join(rule.get("fix_hint", "").split()) if status == FAIL else None,
        )
        report.findings.append(_tag_check_type(finding, check_type))

    return report
