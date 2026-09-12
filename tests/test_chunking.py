"""Pure unit tests for the parent/child splitter (no model or Qdrant needed)."""
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
)
from services.chunking import (  # noqa: E402
    split_parents,
    split_children,
    locate_children,
    _split_by_size,
)


def test_short_text_is_single_chunk():
    assert split_parents("kısa metin") == ["kısa metin"]
    assert split_children("kısa metin") == ["kısa metin"]


def test_empty_text_returns_empty():
    assert split_parents("") == []
    assert split_children("   \n  ") == []


def test_parents_respect_size_and_cover_text():
    text = "\n".join(f"Bu {i}. satırdır ve biraz uzundur." for i in range(300))
    parents = split_parents(text, max_chars=2000)
    assert len(parents) > 1
    # No parent grossly exceeds the limit (boundary snap adds a little slack).
    assert all(len(p) <= 2000 + 200 for p in parents)
    # Coverage: every line shows up in some parent.
    joined = " ".join(parents)
    assert "Bu 0. satırdır" in joined and "Bu 299. satırdır" in joined


def test_children_overlap_between_consecutive_chunks():
    # Long single line so splitting falls back to size-based windows.
    text = " ".join(f"kelime{i}" for i in range(400))
    children = split_children(text, max_chars=500, overlap=80)
    assert len(children) > 1
    assert all(len(c) <= 500 + 100 for c in children)
    # Consecutive children should share some trailing/leading context (overlap).
    a_tail = set(children[0].split()[-8:])
    b_head = set(children[1].split()[:8])
    assert a_tail & b_head, "expected overlapping tokens between consecutive children"


def test_overlap_must_be_smaller_than_max():
    import pytest
    with pytest.raises(ValueError):
        _split_by_size("x" * 100, max_chars=50, overlap=50)


def test_locate_children_spans_point_at_real_substrings():
    # A real parent split into overlapping children; every reported span must
    # slice back to exactly that child (this is what late chunking pools over).
    text = " ".join(f"kelime{i}" for i in range(400))
    children = split_children(text, max_chars=500, overlap=80)
    spans = locate_children(text, children)
    assert [c for c, _, _ in spans] == children
    for child, start, end in spans:
        assert text[start:end] == child
    # Children are produced left-to-right, so located starts are non-decreasing.
    starts = [start for _, start, _ in spans]
    assert starts == sorted(starts)


def test_locate_children_disambiguates_repeats_in_order():
    # Identical children must map to distinct, forward-moving offsets, not all
    # collapse onto the first occurrence.
    parent = "ABCABCABC"
    spans = locate_children(parent, ["ABC", "ABC", "ABC"])
    assert [s for _, s, _ in spans] == [0, 3, 6]
