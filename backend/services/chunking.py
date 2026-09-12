"""Parent/child text splitting for chunked retrieval (phase 1).

Pure, dependency-free string helpers so they can be unit-tested without a model
or Qdrant. The pipeline is:

    document text
      -> split_parents(...)   ~2000-char parent chunks (no overlap; they partition)
      -> split_children(...)  ~500-char child chunks (with overlap, for context)

Children are what gets embedded + indexed; the parent is what we return to the
LLM as context. Splitting prefers natural boundaries (line breaks, sentence ends,
spaces) near the size limit so chunks don't cut mid-word/mid-sentence.
"""
from typing import List

PARENT_MAX_CHARS = 2000
CHILD_MAX_CHARS = 500
CHILD_OVERLAP = 80


def _split_by_size(text: str, max_chars: int, overlap: int) -> List[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    if overlap >= max_chars:
        raise ValueError("overlap must be smaller than max_chars")

    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            # Snap the cut to a natural boundary in the latter half of the window
            # so we don't split mid-sentence/word. Preference: newline > ". " > space.
            window = text[start:end]
            cut = max(window.rfind("\n"), window.rfind(". "), window.rfind(" "))
            if cut > max_chars // 2:
                end = start + cut + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        # Step forward, keeping `overlap` chars of trailing context for the next chunk.
        start = max(end - overlap, start + 1)
    return chunks


def split_parents(text: str, max_chars: int = PARENT_MAX_CHARS) -> List[str]:
    """Split a document into parent chunks (no overlap — they partition the text)."""
    return _split_by_size(text, max_chars, overlap=0)


def split_children(
    text: str,
    max_chars: int = CHILD_MAX_CHARS,
    overlap: int = CHILD_OVERLAP,
) -> List[str]:
    """Split a parent chunk into overlapping child chunks (what gets embedded)."""
    return _split_by_size(text, max_chars, overlap=overlap)


def locate_children(parent: str, children: List[str]) -> List[tuple]:
    """Map each child back to its ``(child, start, end)`` char span in ``parent``.

    Children are substrings of ``parent`` produced left-to-right by
    ``split_children`` (only leading/trailing whitespace is stripped), so we scan
    forward from a moving cursor; that resolves repeated text in chunk order.
    Late chunking needs these spans to pool the right token range per child.
    """
    spans: List[tuple] = []
    cursor = 0
    for child in children:
        idx = parent.find(child, cursor)
        if idx == -1:  # not found ahead of the cursor (unexpected) — retry from start
            idx = parent.find(child)
        if idx == -1:  # still missing; fall back so spans stay aligned with children
            idx = min(cursor, len(parent))
        spans.append((child, idx, idx + len(child)))
        cursor = idx + 1
    return spans
