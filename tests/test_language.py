"""Answer language follows the QUESTION, not the corpus.

The documents are Turkish, but a user asking in English should get an English
answer — including the "I couldn't find this" notice, which is prepended by the
backend rather than written by the model. These tests cover the detection
heuristic and the prompt/notice wiring that depends on it. No services needed.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from services.llm import (  # noqa: E402
    DEFAULT_LANGUAGE,
    FALLBACK_NOTICES,
    _build_general_prompt,
    _build_grounded_prompt,
    build_context,
    detect_language,
    fallback_notice,
    has_fallback_notice,
)

TURKISH = [
    "SAT kabul kriterleri nelerdir?",
    "Bir SRS hangi bölümlerden oluşmalıdır?",
    "UAT ortamında üretim verisi maskelenmeden kullanılabilir mi?",
    "Proje kapanışında hangi dersler çıkarıldı?",
    "TRF hangi iki rol tarafından imzalanır ve hangi aşamada temellenir?",
    # written without diacritics — still Turkish
    "kabul kriterleri nelerdir",
    "bir dokumanin onay akisi nasil isler",
]

ENGLISH = [
    "What exit criteria must be met before the SAT acceptance certificate is issued?",
    "Which record demonstrates bi-directional traceability between requirements and test cases?",
    "Give an overview of the full set of documents produced across a project's life cycle.",
    "Compare the Prepared / Recommended / Approved sign-off roles across the PMP and the SRS.",
    "How do the BUR, TRF, SRS and DSAD documents feed into one another?",
    "What is the production server IP address and database password for the deployment?",
]


@pytest.mark.parametrize("question", TURKISH)
def test_turkish_questions_detected(question):
    assert detect_language(question) == "tr"


@pytest.mark.parametrize("question", ENGLISH)
def test_english_questions_detected(question):
    assert detect_language(question) == "en"


@pytest.mark.parametrize("text", ["", "   ", "\n", "?!.", "12345", "SAT UAT TRF"])
def test_undecidable_input_falls_back_to_the_default(text):
    """Acronym-only or empty input carries no language signal. Guessing English
    for a Turkish-facing product is the worse error, so the default holds."""
    assert detect_language(text) == DEFAULT_LANGUAGE


def test_turkish_characters_outweigh_incidental_english_words():
    """A Turkish question quoting English document terms stays Turkish."""
    q = "SRS içindeki Security Requirements bölümü ne için gereklidir?"
    assert detect_language(q) == "tr"


def test_each_language_has_its_own_notice():
    assert set(FALLBACK_NOTICES) == {"tr", "en"}
    assert FALLBACK_NOTICES["tr"] != FALLBACK_NOTICES["en"]
    assert fallback_notice("tr") == FALLBACK_NOTICES["tr"]
    assert fallback_notice("en") == FALLBACK_NOTICES["en"]


def test_unknown_language_code_degrades_to_the_default():
    assert fallback_notice("de") == FALLBACK_NOTICES[DEFAULT_LANGUAGE]


def test_has_fallback_notice_recognises_either_language():
    for lang in ("tr", "en"):
        assert has_fallback_notice(f"{FALLBACK_NOTICES[lang]}\n\nSome answer.")
    assert not has_fallback_notice("A perfectly ordinary grounded answer.")


@pytest.mark.parametrize("lang", ["tr", "en"])
def test_prompts_embed_the_matching_notice(lang):
    """Both prompt paths must instruct the model with the notice for `lang`, or a
    user gets the wrong language's preamble on their answer."""
    docs = [{"document": {"title": "T", "content": "C"}, "score": 0.9}]
    grounded = _build_grounded_prompt(build_context(docs), "q", "", "", lang)
    general = _build_general_prompt("q", "", "", lang)
    for prompt in (grounded, general):
        assert fallback_notice(lang) in prompt
        other = "en" if lang == "tr" else "tr"
        assert fallback_notice(other) not in prompt


def test_prompts_instruct_matching_the_question_language():
    """The old prompts hard-coded 'answer in Turkish only'. Guard the replacement."""
    docs = [{"document": {"title": "T", "content": "C"}, "score": 0.9}]
    for prompt in (_build_grounded_prompt(build_context(docs), "q"), _build_general_prompt("q")):
        assert "YANITIN DİLİ" in prompt
        assert "Sadece Türkçe yanıt ver" not in prompt
