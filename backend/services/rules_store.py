"""CRUD over the compliance rule sets (backend/rules/*.yaml) for the UI editor.

The Compliance Checker reads rules with services.compliance.load_rules (PyYAML,
read-only). This module is the *write* side: it lists/creates/updates/deletes
individual rules while preserving the hand-authored comments and formatting in
the YAML files, via ruamel.yaml round-trip.

Storage convention: a rule for doc_kind ``SRS`` lives in ``srs.yaml`` (the file
is named after the lowercased doc_kind). New doc_kinds create a new file.

Every write is validated against the rule schema (see backend/rules/README.md)
and rule ids must be globally unique. Raises ValidationError on bad input and
NotFoundError when a rule id can't be located.
"""
from __future__ import annotations

import glob
import os
import re
from typing import Dict, List, Optional, Tuple

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

RULES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules")

TIERS = ("structure", "traceability", "content")
SEVERITIES = ("blocker", "high", "medium", "low")
# check.type -> the tier it belongs to (mirrors backend/rules/README.md).
CHECK_TYPES = {
    "section_present": "structure",
    "revision_history": "structure",
    "signature_block": "structure",
    "metadata_regex": "structure",
    "refs_resolve": "traceability",
    "id_trace": "traceability",
    "llm_judge": "content",
}

_yaml = YAML()          # round-trip mode: preserves comments + formatting
_yaml.preserve_quotes = True
_yaml.indent(mapping=2, sequence=2, offset=0)


class ValidationError(ValueError):
    """A rule failed schema validation (surface as HTTP 400)."""


class NotFoundError(KeyError):
    """A rule id could not be found (surface as HTTP 404)."""


# --------------------------------------------------------------------------- #
#  File helpers
# --------------------------------------------------------------------------- #
def _path_for_kind(doc_kind: str) -> str:
    return os.path.join(RULES_DIR, f"{doc_kind.lower()}.yaml")


def _load_file(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = _yaml.load(f)
    return data if data is not None else []


def _dump_file(path: str, data: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        _yaml.dump(data, f)


def _all_files() -> List[str]:
    return sorted(glob.glob(os.path.join(RULES_DIR, "*.yaml")))


# --------------------------------------------------------------------------- #
#  Validation
# --------------------------------------------------------------------------- #
def validate_rule(rule: dict, existing_ids: Optional[set] = None,
                  updating_id: Optional[str] = None) -> None:
    """Validate a rule dict against the schema. Raises ValidationError."""
    if not isinstance(rule, dict):
        raise ValidationError("Rule must be an object.")

    rid = rule.get("id")
    if not rid or not isinstance(rid, str):
        raise ValidationError("Rule 'id' is required and must be a string.")
    if existing_ids is not None and rid in existing_ids and rid != updating_id:
        raise ValidationError(f"Rule id '{rid}' already exists.")

    applies_to = rule.get("applies_to") or {}
    if not applies_to.get("doc_kind"):
        raise ValidationError("'applies_to.doc_kind' is required.")

    if rule.get("tier") not in TIERS:
        raise ValidationError(f"'tier' must be one of {TIERS}.")
    if rule.get("severity") not in SEVERITIES:
        raise ValidationError(f"'severity' must be one of {SEVERITIES}.")
    if not (rule.get("statement") or "").strip():
        raise ValidationError("'statement' is required.")

    check = rule.get("check") or {}
    ctype = check.get("type")
    if ctype not in CHECK_TYPES:
        raise ValidationError(f"'check.type' must be one of {sorted(CHECK_TYPES)}.")
    expected_tier = CHECK_TYPES[ctype]
    if rule["tier"] != expected_tier:
        raise ValidationError(
            f"check.type '{ctype}' belongs to tier '{expected_tier}', not '{rule['tier']}'."
        )


# --------------------------------------------------------------------------- #
#  Read
# --------------------------------------------------------------------------- #
def _plain(obj):
    """Deep-convert ruamel Commented* structures into plain dict/list for JSON."""
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_plain(v) for v in obj]
    return obj


def list_rules() -> List[dict]:
    """All rules across every file, each tagged with its source filename."""
    out: List[dict] = []
    for path in _all_files():
        fname = os.path.basename(path)
        for rule in _load_file(path):
            item = _plain(rule)
            item["_file"] = fname
            out.append(item)
    return out


def _find(rule_id: str) -> Tuple[str, list, int]:
    """Locate a rule by id -> (path, loaded_seq, index). Raises NotFoundError."""
    for path in _all_files():
        seq = _load_file(path)
        for i, rule in enumerate(seq):
            if rule.get("id") == rule_id:
                return path, seq, i
    raise NotFoundError(rule_id)


def _existing_ids() -> set:
    return {r["id"] for r in list_rules() if r.get("id")}


# --------------------------------------------------------------------------- #
#  Write
# --------------------------------------------------------------------------- #
_FIELD_ORDER = ["id", "applies_to", "tier", "severity", "statement", "check",
                "source", "fix_hint"]


def _to_commented(rule: dict) -> CommentedMap:
    """Build a CommentedMap in canonical field order (nested maps too)."""
    cm = CommentedMap()
    for key in _FIELD_ORDER:
        if key in rule and rule[key] is not None:
            val = rule[key]
            cm[key] = CommentedMap(val) if isinstance(val, dict) else val
    # carry any extra keys the schema doesn't enumerate
    for key, val in rule.items():
        if key not in cm and not key.startswith("_"):
            cm[key] = val
    return cm


def _generate_id(doc_kind: str, existing: set) -> str:
    """Auto-assign a stable, unique rule id so non-technical users never type one.

    Format: RULE-<KIND>-<NNN> (e.g. RULE-SRS-011), numbering per document kind.
    """
    prefix = f"RULE-{(doc_kind or 'DOC').upper()}-"
    nums = [int(m.group(1)) for rid in existing
            if (m := re.match(re.escape(prefix) + r"(\d+)$", rid))]
    n = (max(nums) + 1) if nums else 1
    rid = f"{prefix}{n:03d}"
    while rid in existing:
        n += 1
        rid = f"{prefix}{n:03d}"
    return rid


def create_rule(rule: dict) -> dict:
    """Validate and append a new rule to its doc_kind file (created if needed).

    If no ``id`` is supplied, one is generated (RULE-<KIND>-<NNN>) — the UI leaves
    it blank so users don't have to invent identifiers.
    """
    rule = {k: v for k, v in rule.items() if not k.startswith("_")}
    if not (rule.get("id") or "").strip():
        rule["id"] = _generate_id((rule.get("applies_to") or {}).get("doc_kind", ""),
                                   _existing_ids())
    validate_rule(rule, existing_ids=_existing_ids())
    path = _path_for_kind(rule["applies_to"]["doc_kind"])
    seq = _load_file(path)
    seq.append(_to_commented(rule))
    _dump_file(path, seq)
    return {**rule, "_file": os.path.basename(path)}


def update_rule(rule_id: str, rule: dict) -> dict:
    """Validate and replace the rule with the given id (in place, comments kept)."""
    rule = {k: v for k, v in rule.items() if not k.startswith("_")}
    validate_rule(rule, existing_ids=_existing_ids(), updating_id=rule_id)
    path, seq, idx = _find(rule_id)

    # If the doc_kind changed, this rule must move to another file.
    new_path = _path_for_kind(rule["applies_to"]["doc_kind"])
    if os.path.abspath(new_path) != os.path.abspath(path):
        del seq[idx]
        _dump_file(path, seq)
        dest = _load_file(new_path)
        dest.append(_to_commented(rule))
        _dump_file(new_path, dest)
        return {**rule, "_file": os.path.basename(new_path)}

    seq[idx] = _to_commented(rule)
    _dump_file(path, seq)
    return {**rule, "_file": os.path.basename(path)}


def delete_rule(rule_id: str) -> None:
    path, seq, idx = _find(rule_id)
    del seq[idx]
    _dump_file(path, seq)


def _corpus_doc_kinds() -> List[str]:
    """doc_kinds present in the indexed corpus (SRS, PMP, SAT_PLAN, …).

    These are the document templates the checker knows about, so the UI can offer
    them as targets for a new rule set even before any rule exists for them.
    """
    try:
        from services.corpus import corpus_documents
        return sorted({d.get("doc_kind") for d in corpus_documents() if d.get("doc_kind")})
    except Exception:
        return []


def doc_kinds() -> List[str]:
    """All document kinds the editor should offer: corpus kinds ∪ kinds that
    already have a rule set. Each can hold its own independent set of rules."""
    rule_kinds = {r.get("applies_to", {}).get("doc_kind") for r in list_rules()}
    return sorted({k for k in (set(_corpus_doc_kinds()) | rule_kinds) if k})


def schema_meta() -> Dict:
    """Enum/vocabulary the UI form needs to render selects."""
    return {
        "tiers": list(TIERS),
        "severities": list(SEVERITIES),
        "check_types": CHECK_TYPES,   # {type: tier}
        "doc_kinds": doc_kinds(),     # document templates, each with its own rule set
    }
