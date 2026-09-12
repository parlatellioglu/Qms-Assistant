# Compliance rule sets

The **rule/policy set is the primary basis** for the Compliance Checker. Every
finding the checker emits must trace back to a rule `id` defined here — the LLM never decides on its own what "compliant" means;
it only ever evaluates a document against a specific rule statement.

Rules live in `backend/rules/` (tracked in git and shipped inside the backend
image so the checker can load them at runtime) — one YAML file per document
template (`srs.yaml`, `pmp.yaml`, …). Authoring or tightening a rule = editing YAML, not
writing Python, so quality staff can maintain them. A rule binds to documents via
`applies_to.doc_kind` (the fine-grained template id added to the corpus in
`scripts/corpus/build_cmmi_corpus.py`, e.g. `SRS`, `PMP`, `BUR`).

## Rule schema

```yaml
- id: RULE-SRS-STRUCT-001        # stable, unique; findings cite this
  applies_to:
    doc_kind: SRS                # which documents this rule binds to
  tier: structure                # structure | traceability | content
  severity: high                 # blocker | high | medium | low
  statement: >                   # human-readable requirement (shown to the user)
    Belge bir Revizyon Geçmişi (Revision History) tablosu içermelidir.
  check:                         # how the rule is executed (see check.type below)
    type: revision_history
    min_versions: 3
  source: "CMMI CM / kurumsal doküman şablonu"   # the policy it is grounded in
  fix_hint: >                    # actionable guidance emitted with a violation
    En az üç sürüm satırı (taslak, iç gözden geçirme, onay) içeren bir
    Revizyon Geçmişi tablosu ekleyin.
```

## Tiers — cheapest first, and how the three bases combine

| tier           | executor                        | which "basis" | LLM? |
|----------------|---------------------------------|---------------|------|
| `structure`    | deterministic (regex/section)   | rule set      | no   |
| `traceability` | exact id resolution over the corpus | existing docs | no   |
| `content`      | rule-guided judge, forced cite  | LLM-as-judge  | yes  |

The checker runs a document's applicable rules in this order and short-circuits
on a `blocker` structural failure before spending a large-model call on `content`
rules.

## `check.type` vocabulary

Each `type` maps to one executor. Adding a rule is common (new YAML entry);
adding a `type` is rare (new executor). Types used by the seed rules:

| type                | tier          | params                                    | passes when |
|---------------------|---------------|-------------------------------------------|-------------|
| `section_present`   | structure     | `any_of: [names…]`                        | one of the section headings appears |
| `revision_history`  | structure     | `min_versions: N`                         | a Revision History with ≥ N version rows exists |
| `signature_block`   | structure     | `roles: [names…]`                         | every listed sign-off role is present |
| `metadata_regex`    | structure     | `field:`, `pattern:`                      | the document-dict field matches the regex |
| `refs_resolve`      | traceability  | `id_pattern:`, `require_status:`          | every referenced doc id exists in the corpus with the required status |
| `id_trace`          | traceability  | `from_pattern:`, `to_doc_kind:`           | ids of one form are corroborated by a doc of another kind |
| `llm_judge`         | content       | `criterion:`, `require_citation:`, `must_cover: [..]` | the model, citing the document, judges the criterion satisfied |

> All seven executors are implemented in `backend/services/compliance.py` (see
> `CHECKS`). Adding a *rule* means adding a YAML entry here; adding a *check type*
> means adding an executor there, and is rare.
>
> Rule sets currently exist for **SRS** (14 rules: 7 structure, 2 traceability,
> 5 content) and **BUR** (2 content rules). Other document kinds have none yet — the
> checker reports "no applicable rules" for them rather than guessing.
