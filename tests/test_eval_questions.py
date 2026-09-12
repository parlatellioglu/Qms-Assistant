"""The evaluation question set is defined in two places for two different tools.

`rag_test_questions.txt` feeds the batch runner (send_test_questions.py, plain
stdlib, runs anywhere); `rag_eval/promptfooconfig.yaml` carries the same questions
next to their per-question assertions, which a flat text file cannot express.

Two copies drift. These tests fail loudly when they do, so a question edited in one
place is not silently missing from the other run. Pure-logic: no services needed.
"""
import os
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TXT = os.path.join(ROOT, "rag_test_questions.txt")
CFG = os.path.join(ROOT, "rag_eval", "promptfooconfig.yaml")


def _txt_questions():
    with open(TXT, encoding="utf-8") as fh:
        return [ln.strip() for ln in fh if ln.strip() and not ln.lstrip().startswith("#")]


def _cfg_tests():
    with open(CFG, encoding="utf-8") as fh:
        return (yaml.safe_load(fh) or {}).get("tests", [])


def test_question_sets_are_identical():
    txt, cfg = _txt_questions(), [t["vars"]["question"].strip() for t in _cfg_tests()]
    assert cfg == txt, (
        "rag_test_questions.txt and rag_eval/promptfooconfig.yaml have drifted.\n"
        f"  only in txt:  {[q for q in txt if q not in cfg]}\n"
        f"  only in yaml: {[q for q in cfg if q not in txt]}"
    )


@pytest.mark.parametrize("test", _cfg_tests(), ids=lambda t: t["vars"]["question"][:40])
def test_every_question_carries_an_assertion(test):
    """A question with no assertion is graded only by the shared rubric, which is
    exactly the weak setup this eval was rewritten to get away from."""
    assert test.get("assert"), "question has no per-question assertion"


# Distinctive fragments of each language's fallback notice (services/llm.py).
# The assistant answers in the question's language, so the notice a question should
# trigger depends on the language that question is written in.
_FALLBACK_MARKERS = ("bulamadığım", "could not find enough relevant information")


def test_out_of_scope_questions_check_the_fallback():
    """The three unanswerable questions must assert the honest fallback fires.

    These are the easiest assertions to lose while tuning prompts, and losing them
    silently turns a hallucination check into no check at all.
    """
    fallback = [t for t in _cfg_tests()
                if any(a.get("type") == "icontains"
                       and any(m in str(a.get("value")) for m in _FALLBACK_MARKERS)
                       for a in t["assert"])]
    assert len(fallback) == 3, f"expected 3 fallback-checked questions, found {len(fallback)}"
    # Each must also guard against inventing a specific, not merely say "not found".
    for t in fallback:
        kinds = {a["type"] for a in t["assert"]}
        assert kinds & {"javascript", "llm-rubric"}, (
            f"{t['vars']['question'][:50]!r} checks the fallback text but nothing "
            "stops it inventing a value alongside it"
        )


def test_fallback_assertion_matches_the_question_language():
    """The asserted notice must be in the language the question is written in.

    The assistant answers in the question's language, so an English question
    triggers the English notice. Asserting the Turkish string on an English
    question fails every run for the wrong reason.
    """
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    from services.llm import detect_language, fallback_notice

    for t in _cfg_tests():
        marker = next((str(a["value"]) for a in t["assert"]
                       if a.get("type") == "icontains"
                       and any(m in str(a.get("value")) for m in _FALLBACK_MARKERS)), None)
        if marker is None:
            continue                       # not a fallback question
        question = t["vars"]["question"]
        expected = fallback_notice(detect_language(question))
        assert marker in expected, (
            f"{question[:60]!r} is {detect_language(question)!r}, so it will get "
            f"the {detect_language(question)} fallback notice — but the assertion "
            f"looks for {marker!r}, which belongs to the other language."
        )
