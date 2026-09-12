"""Tests for the chat-history SQLite store (backend/services/history_store.py).

Each test runs against a fresh temp DB (DB_PATH is monkeypatched), so nothing
touches the real backend/data/history.db. Covers the upsert semantics, ordering,
JSON round-trip of messages/docs, and delete.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from services import history_store as h  # noqa: E402


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point the store at an isolated temp DB file."""
    monkeypatch.setattr(h, "DB_PATH", str(tmp_path / "history.db"))
    return h


def test_empty_list(store):
    assert store.list_conversations() == []


def test_get_missing_is_none(store):
    assert store.get_conversation("nope") is None


def test_save_then_list_and_get(store):
    store.save_conversation("c1", {
        "title": "Sohbet A",
        "messages": [{"role": "user", "text": "q1"}, {"role": "assistant", "text": "a1"}],
        "docsById": {"d1": {"title": "Doc"}},
        "summary": "özet",
        "summarizedCount": 4,
    })
    lst = store.list_conversations()
    assert len(lst) == 1 and lst[0]["id"] == "c1" and lst[0]["title"] == "Sohbet A"

    got = store.get_conversation("c1")
    assert got["messages"][0]["text"] == "q1"
    assert got["docsById"]["d1"]["title"] == "Doc"
    assert got["summary"] == "özet"
    assert got["summarizedCount"] == 4


def test_turkish_chars_survive_roundtrip(store):
    store.save_conversation("c1", {"title": "Şçğüöı", "messages": [{"text": "üç ağ"}]})
    got = store.get_conversation("c1")
    assert got["title"] == "Şçğüöı"
    assert got["messages"][0]["text"] == "üç ağ"


def test_newest_first_ordering(store):
    store.save_conversation("c1", {"title": "A", "updatedAt": 1000})
    store.save_conversation("c2", {"title": "B", "updatedAt": 2000})
    assert [c["id"] for c in store.list_conversations()] == ["c2", "c1"]


def test_upsert_updates_not_duplicates(store):
    store.save_conversation("c1", {"title": "A", "updatedAt": 1000})
    store.save_conversation("c1", {"title": "A2", "updatedAt": 3000})
    lst = store.list_conversations()
    assert len(lst) == 1
    assert lst[0]["title"] == "A2"
    assert lst[0]["updated_at"] == 3000


def test_defaults_when_fields_missing(store):
    store.save_conversation("c1", {})
    got = store.get_conversation("c1")
    assert got["title"] == "Adsız sohbet"
    assert got["messages"] == [] and got["docsById"] == {}
    assert got["summary"] == "" and got["summarizedCount"] == 0


def test_updated_at_autofilled(store):
    ts = store.save_conversation("c1", {"title": "A"})
    assert isinstance(ts, int) and ts > 0
    assert store.list_conversations()[0]["updated_at"] == ts


def test_delete(store):
    store.save_conversation("c1", {"title": "A"})
    store.save_conversation("c2", {"title": "B"})
    store.delete_conversation("c1")
    ids = [c["id"] for c in store.list_conversations()]
    assert ids == ["c2"]
    assert store.get_conversation("c1") is None


def test_delete_missing_is_noop(store):
    store.delete_conversation("ghost")  # must not raise
    assert store.list_conversations() == []
