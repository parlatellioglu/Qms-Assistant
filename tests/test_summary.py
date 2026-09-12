"""Tests for the rolling conversation summary (backend/services/llm.py).

The summary compresses older turns into a short "what this chat is about" block
so long chats keep far context without carrying every turn verbatim. These cover
the deterministic plumbing — prompt assembly, incremental folding, length cap and
failure fallback — with a stubbed LLM; summary *quality* needs live Ollama.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from services import llm  # noqa: E402


def U(text):
    return {"role": "user", "content": text}


def A(text):
    return {"role": "assistant", "content": text}


@pytest.fixture
def capture_llm(monkeypatch):
    """Stub _ollama_generate; record the prompt, return a canned summary."""
    calls = {}

    def _fake(prompt, model_name=None):
        calls["prompt"] = prompt
        return calls.get("reply", "güncellenmiş özet")

    monkeypatch.setattr(llm, "_ollama_generate", _fake)
    return calls


# --- summary block in the prompt ------------------------------------------- #

def test_summary_block_empty_when_absent():
    assert llm._summary_block("") == ""
    assert llm._summary_block(None) == ""


def test_summary_block_present_when_given():
    block = llm._summary_block("kullanıcı SAT testlerini soruyor")
    assert "SAT testlerini" in block


def test_summary_lands_in_grounded_prompt():
    prompt = llm._build_grounded_prompt("BAĞLAM", "yeni soru",
                                        history_str="", summary_str="önceki konu X")
    assert "önceki konu X" in prompt
    # summary comes before the context block
    assert prompt.index("önceki konu X") < prompt.index("BAĞLAM")


def test_summary_lands_in_general_prompt():
    prompt = llm._build_general_prompt("yeni soru", history_str="", summary_str="konu Y")
    assert "konu Y" in prompt


def test_summary_before_history_in_prompt():
    prompt = llm._build_grounded_prompt("BAĞLAM", "soru",
                                        history_str="Kullanıcı: eski", summary_str="ÖZET")
    assert prompt.index("ÖZET") < prompt.index("Kullanıcı: eski")


# --- summarize_conversation ------------------------------------------------- #

def test_summarize_folds_previous_and_new_turns(capture_llm):
    out = llm.summarize_conversation(
        [U("SAT kabul kriterleri neler"), A("...")],
        previous_summary="önceki özet",
    )
    assert out == "güncellenmiş özet"
    # the prompt must carry both the previous summary and the new turns
    assert "önceki özet" in capture_llm["prompt"]
    assert "SAT kabul kriterleri neler" in capture_llm["prompt"]


def test_summarize_empty_history_returns_previous(capture_llm):
    out = llm.summarize_conversation([], previous_summary="değişmemeli")
    assert out == "değişmemeli"
    assert "prompt" not in capture_llm  # LLM never called


def test_summarize_blank_turns_return_previous(capture_llm):
    out = llm.summarize_conversation([U("   "), A("")], previous_summary="aynı kalır")
    assert out == "aynı kalır"
    assert "prompt" not in capture_llm


def test_summarize_caps_length(capture_llm, monkeypatch):
    monkeypatch.setattr(llm, "SUMMARY_MAX_CHARS", 20)
    capture_llm["reply"] = "x" * 200
    out = llm.summarize_conversation([U("soru")], previous_summary="")
    assert len(out) <= 21  # 20 chars + ellipsis
    assert out.endswith("…")


def test_summarize_collapses_whitespace(capture_llm):
    capture_llm["reply"] = "iki    boşluk\n\nsatır"
    out = llm.summarize_conversation([U("soru")], previous_summary="")
    assert out == "iki boşluk satır"


def test_summarize_keeps_previous_on_llm_failure(monkeypatch):
    def _boom(prompt, model_name=None):
        raise RuntimeError("ollama down")
    monkeypatch.setattr(llm, "_ollama_generate", _boom)
    out = llm.summarize_conversation([U("soru")], previous_summary="korunmalı")
    assert out == "korunmalı"


def test_summarize_no_previous_first_time(capture_llm):
    out = llm.summarize_conversation([U("ilk soru"), A("ilk cevap")], previous_summary="")
    assert out == "güncellenmiş özet"
    assert "(henüz özet yok)" in capture_llm["prompt"]
