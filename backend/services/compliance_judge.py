"""LLM-as-judge for the content tier of the Compliance Checker.

`compliance.py` stays deterministic and offline; this module supplies the
optional `judge` callable it accepts. A judge is `callable(rule, doc) ->
(status, detail)` where status is "pass" | "fail" | "error". It sends the rule's
`criterion` plus the document text to a local Ollama model and parses a strict
JSON verdict — the model only ever judges the document against ONE authored rule,
never decides compliance freely (the rule set stays primary).

    from services.compliance import check_document
    from services.compliance_judge import make_ollama_judge
    report = check_document(doc, judge=make_ollama_judge())   # model=gemma4:e4b
"""
import json
import os
import urllib.request

# The analysis tier wants the *larger* model, separate
# from the lean Q&A model (DEFAULT_MODEL in llm.py). Env-overridable.
COMPLIANCE_MODEL = os.getenv("COMPLIANCE_MODEL", "gemma4:e4b")
# Cap how much document text we send so a long doc can't overflow the context.
MAX_DOC_CHARS = int(os.getenv("COMPLIANCE_JUDGE_MAX_CHARS", "16000"))

_SYSTEM = (
    "You are a CMMI quality auditor. You are given one RULE criterion and one "
    "DOCUMENT. Your task: decide only whether the document satisfies that "
    "criterion. Be strict: if the document does not clearly satisfy it, "
    "verdict='fail'. The document may be written in a different language than "
    "the criterion; judge the content, not the language, and answer in English. "
    "Reply ONLY in this JSON form: "
    '{"verdict": "pass" | "fail", '
    '"citation": "a verbatim quote from the document supporting your verdict (empty if none)", '
    '"reason": "a one-sentence justification"}'
)


def _build_prompt(rule: dict, doc: dict) -> str:
    check = rule.get("check", {})
    parts = [
        _SYSTEM,
        f"\nRULE: {' '.join(rule.get('statement', '').split())}",
        f"CRITERION: {' '.join(check.get('criterion', '').split())}",
    ]
    must_cover = check.get("must_cover")
    if must_cover:
        parts.append(
            "The document must address EACH of these; if any is missing, "
            f"verdict='fail': {must_cover}"
        )
    content = doc.get("content", "")[:MAX_DOC_CHARS]
    parts.append(f"\nDOCUMENT:\n{content}\n\nReturn ONLY JSON.")
    return "\n".join(parts)


def _ollama_generate(prompt: str, model: str, ollama_url: str) -> str:
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",          # constrain output to valid JSON
        "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
        "think": False,            # skip gemma's slow hidden reasoning pass
        "options": {"num_ctx": int(os.getenv("LLM_NUM_CTX", "8192")),
                    "temperature": 0, "seed": 42},
    }
    req = urllib.request.Request(
        f"{ollama_url}/api/generate",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8")).get("response", "")


def make_ollama_judge(model: str = COMPLIANCE_MODEL, ollama_url: str | None = None):
    """Return a judge(rule, doc) -> (status, detail) backed by a local Ollama model."""
    ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")

    def judge(rule: dict, doc: dict):
        try:
            raw = _ollama_generate(_build_prompt(rule, doc), model, ollama_url)
            verdict = json.loads(raw)
        except Exception as exc:
            return "error", f"Judge model error ({model}): {type(exc).__name__}: {exc}"

        status = "pass" if str(verdict.get("verdict", "")).lower() == "pass" else "fail"
        reason = str(verdict.get("reason", "")).strip() or "(no reason given)"
        citation = str(verdict.get("citation", "")).strip()

        detail = f"[{model}] {reason}"
        if citation:
            detail += f' | quote: "{citation[:180]}"'
        elif rule.get("check", {}).get("require_citation") and status == "pass":
            detail += " | (no citation given)"
        return status, detail

    return judge
