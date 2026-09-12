"""Tests for the asymmetric conversation-memory window (format_history in
backend/services/llm.py).

Memory is asymmetric on purpose: many recent USER questions (short, carry the
thread's intent) but only the last few ASSISTANT answers (long, re-derivable from
retrieval), all under a total character budget. These cover the selection and the
budget eviction deterministically — no LLM, no Qdrant.
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


def _roles(block):
    """Turn a rendered history block back into a list of 'user'/'assistant'."""
    return ["user" if ln.startswith("Kullanıcı:") else "assistant"
            for ln in block.splitlines() if ln.strip()]


def test_empty_history_is_empty_string():
    assert llm.format_history([]) == ""
    assert llm.format_history(None) == ""


def test_blank_messages_are_dropped():
    block = llm.format_history([U("gerçek soru"), U("   "), A("")])
    assert _roles(block) == ["user"]


def test_keeps_many_user_turns_but_few_assistant(monkeypatch):
    monkeypatch.setattr(llm, "HISTORY_USER_TURNS", 10)
    monkeypatch.setattr(llm, "HISTORY_ASSISTANT_TURNS", 2)
    monkeypatch.setattr(llm, "HISTORY_CHAR_BUDGET", 100000)  # don't let budget interfere
    history = []
    for i in range(8):
        history.append(U(f"soru {i}"))
        history.append(A(f"cevap {i}"))
    roles = _roles(llm.format_history(history))
    assert roles.count("user") == 8            # all 8 user turns (< cap of 10)
    assert roles.count("assistant") == 2       # only the last 2 answers


def test_chronological_order_preserved(monkeypatch):
    monkeypatch.setattr(llm, "HISTORY_USER_TURNS", 10)
    monkeypatch.setattr(llm, "HISTORY_ASSISTANT_TURNS", 1)
    monkeypatch.setattr(llm, "HISTORY_CHAR_BUDGET", 100000)
    history = [U("bir"), A("cevap-bir"), U("iki"), A("cevap-iki")]
    block = llm.format_history(history)
    # last assistant (cevap-iki) must render after both user turns, in order
    assert block.index("bir") < block.index("iki") < block.index("cevap-iki")


def test_user_turn_cap_keeps_most_recent(monkeypatch):
    monkeypatch.setattr(llm, "HISTORY_USER_TURNS", 3)
    monkeypatch.setattr(llm, "HISTORY_ASSISTANT_TURNS", 0)
    monkeypatch.setattr(llm, "HISTORY_CHAR_BUDGET", 100000)
    history = [U(f"soru {i}") for i in range(6)]
    block = llm.format_history(history)
    assert "soru 3" in block and "soru 5" in block
    assert "soru 0" not in block and "soru 2" not in block


def test_char_budget_drops_oldest_first(monkeypatch):
    monkeypatch.setattr(llm, "HISTORY_USER_TURNS", 10)
    monkeypatch.setattr(llm, "HISTORY_ASSISTANT_TURNS", 0)
    monkeypatch.setattr(llm, "HISTORY_MAX_CHARS", 100)
    # Budget is on content chars only; "eski"+"orta"+"yeni" = 12, so 5 keeps just one.
    monkeypatch.setattr(llm, "HISTORY_CHAR_BUDGET", 5)
    history = [U("eski"), U("orta"), U("yeni")]
    block = llm.format_history(history)
    assert "yeni" in block          # newest survives
    assert "eski" not in block      # oldest evicted first


def test_budget_never_drops_newest_user_turn(monkeypatch):
    monkeypatch.setattr(llm, "HISTORY_USER_TURNS", 10)
    monkeypatch.setattr(llm, "HISTORY_ASSISTANT_TURNS", 2)
    monkeypatch.setattr(llm, "HISTORY_MAX_CHARS", 600)
    monkeypatch.setattr(llm, "HISTORY_CHAR_BUDGET", 1)  # budget smaller than any turn
    history = [U("önceki"), A("uzun cevap"), U("son soru")]
    block = llm.format_history(history)
    assert _roles(block) == ["user"]
    assert "son soru" in block


def test_long_message_is_truncated(monkeypatch):
    monkeypatch.setattr(llm, "HISTORY_MAX_CHARS", 20)
    monkeypatch.setattr(llm, "HISTORY_CHAR_BUDGET", 100000)
    block = llm.format_history([U("x" * 200)])
    assert "…" in block
    assert len(block) < 60  # "Kullanıcı: " + 20 chars + ellipsis, not 200


def test_whitespace_is_collapsed(monkeypatch):
    monkeypatch.setattr(llm, "HISTORY_CHAR_BUDGET", 100000)
    block = llm.format_history([U("iki    boşluk\n\nsatır")])
    assert "iki boşluk satır" in block
