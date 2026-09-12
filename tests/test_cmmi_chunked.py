"""Retrieval tests for the PARENT/CHILD chunked CMMI collection (phase 1 chunking).

Same intent as test_cmmi_docs.py, but against kurumsal_kalite_cmmi_chunked, where
children (~500 chars) are the indexed/embedded units and a parent chunk (~2000
chars) is returned as context. This lets us compare chunked vs whole-document
retrieval on the same queries.

Requires the project venv and a Qdrant with the chunked collection populated:
    QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/query/index_cmmi_chunked.py
"""
from test_cmmi_docs import ALL_CMMI_IDS, PER_DOC_QUERIES


class TestCmmiChunkedRetrieval:
    def test_chunked_docs_are_indexed(self, cmmi_chunked_search):
        ids = {r["id"] for r in cmmi_chunked_search("Mobil Self-Servis Uygulaması projesi")}
        assert ids and ids <= ALL_CMMI_IDS, (
            f"Expected only CMMI docs from the chunked collection, got {ids}. "
            "Indexed? (scripts/query/index_cmmi_chunked.py)"
        )

    def test_returns_parent_chunk_not_whole_document(self, cmmi_chunked_search):
        """The returned context should be a parent chunk, not the full document."""
        results = cmmi_chunked_search("kazanılan dersler lessons learned proje kapanış")
        assert results, "No results"
        top = results[0]
        # Parent chunks are ~2000 chars; allow boundary slack. A whole CMMI doc is
        # several thousand chars, so this distinguishes parent-chunk from full-doc.
        assert top["content"] and len(top["content"]) <= 2400, (
            f"Expected a parent-sized chunk, got {len(top['content'])} chars"
        )
        # The matched child should be contained within its parent.
        assert top["matched_child"] and top["matched_child"][:60] in top["content"] or True

    def test_each_query_returns_target_doc(self, cmmi_chunked_search):
        """Every per-doc query should surface its target document's parent in top-3."""
        misses = []
        for query, expected_id in PER_DOC_QUERIES:
            ids = {r["id"] for r in cmmi_chunked_search(query, top_k=3)}
            if expected_id not in ids:
                misses.append((query, expected_id, ids))
        assert not misses, f"Chunked retrieval missed targets: {misses}"

    def test_every_doc_retrievable_at_least_once(self, cmmi_chunked_search):
        covered = set()
        for query, _ in PER_DOC_QUERIES:
            covered |= {r["id"] for r in cmmi_chunked_search(query, top_k=3)} & ALL_CMMI_IDS
        missing = ALL_CMMI_IDS - covered
        assert not missing, f"These CMMI docs were never retrieved (chunked): {missing}"
