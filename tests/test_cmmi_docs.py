"""Retrieval tests for the CMMI lifecycle documents (long, real-world docs).

The small_docs corpus contains one-sentence documents; these CMMI docs are full
multi-page Word documents (~700-1900 words each) describing a single fictional
project (Mobil Self-Servis Uygulaması, CMMI-IT-2025-014). They are extracted into
backend/data/cmmi_docs.py by scripts/corpus/build_cmmi_corpus.py and indexed into their
OWN Qdrant collection (kurumsal_kalite_cmmi_docs) by
scripts/query/index_cmmi_collection.py, kept isolated from the small-doc demo so the
two corpora never interfere.

Purpose: verify the retrieval goal works on long documents — a query targeting
content unique to one CMMI document should surface that document in the top
results. This is also the benchmark that motivates chunking work (see
PROCESS_LOG.md): if whole-document embedding struggles on fine-grained queries,
it shows up here.

These tests exercise the same hybrid (dense + sparse RRF) retrieval as the live
/chat endpoint via the `cmmi_search` fixture, but skip LLM generation — so they
are fast and don't touch the small-doc collection. Run them with the project
venv (the fixture loads the embedding model) against a Qdrant that has the CMMI
collection populated.
"""
import pytest

# All eleven CMMI document IDs (see backend/data/cmmi_docs.py).
ALL_CMMI_IDS = {
    "CMMI-IT-001", "CMMI-IT-002", "CMMI-IT-003", "CMMI-IT-004",
    "CMMI-IT-005", "CMMI-IT-006", "CMMI-IT-007", "CMMI-IT-008",
    "CMMI-IT-009", "CMMI-IT-010", "CMMI-IT-SAT", "CMMI-IT-UAT",
    "CMMI-IT-011", "CMMI-SDLC",
}

VALID_DEPARTMENTS = {"Yönetim", "Kalite", "İnsan Kaynakları", "Mühendislik", "Satın Alma"}
VALID_TYPES = {"policy", "procedure", "instruction", "form", "report"}
VALID_STATUSES = {"draft", "published", "under_review", "archived"}

# (query, expected CMMI doc id) — each query targets content unique to one doc.
# Expectation: the target appears within the top-k results (k=3, as in /chat).
PER_DOC_QUERIES = [
    # Terms unique to the TRF. The earlier query ("tarife yapısı servis seviyesi
    # transaction volume") did not satisfy this test's own premise: "tarife" appears
    # in 6 of the 14 documents and "servis seviyesi" in none of them (the TRF spells
    # it "Desired Service Levels"), so it passed on a thin margin that any re-embedding
    # could tip. These four phrases each appear in CMMI-IT-001 and nowhere else.
    ("tariff structure desired service levels uptime period processing rate", "CMMI-IT-001"),
    ("teknik öneri dokümanı sistem mimarisi alternatif", "CMMI-IT-002"),
    ("iş kırılım yapısı work breakdown structure WBS", "CMMI-IT-003"),
    ("iş birimi gereksinimleri zorunlu gereksinim", "CMMI-IT-004"),
    ("fonksiyonel gereksinim sayımı requirements count", "CMMI-IT-005"),
    ("entity relationship diagram veritabanı tablo tasarımı", "CMMI-IT-006"),
    ("sistem kabul testi planı test stratejisi", "CMMI-IT-007"),
    ("kullanıcı kabul testi planı erişim profili matrisi", "CMMI-IT-008"),
    ("sistem kabul sertifikası", "CMMI-IT-SAT"),
    ("kullanıcı kabul sertifikası üretime alınabilir", "CMMI-IT-UAT"),
    # 009/010 are the test-CASE sheets; use case numbers unique to them (the SAT/UAT
    # PLANs 007/008 embed only TC01–06), so the query targets the sheet, not the plan.
    ("SAT-TC13 yük TPS test senaryosu sonuç", "CMMI-IT-009"),
    ("UAT-TC11 erişilebilirlik ekran okuyucu test senaryosu", "CMMI-IT-010"),
    ("kazanılan dersler lessons learned proje kapanış", "CMMI-IT-011"),
    ("solutions delivery life cycle cascade process maturity", "CMMI-SDLC"),
]

# Queries whose single most relevant document is unambiguous → assert top-1.
TOP_RESULT_QUERIES = [
    ("fonksiyonel gereksinim sayımı requirements count", "CMMI-IT-005"),
    ("sistem kabul testi planı test stratejisi", "CMMI-IT-007"),
    ("kullanıcı kabul testi planı erişim profili matrisi", "CMMI-IT-008"),
    ("kazanılan dersler lessons learned proje kapanış", "CMMI-IT-011"),
]


class TestCmmiIngestion:
    def test_cmmi_docs_are_indexed(self, cmmi_search):
        """The shared project name should surface CMMI documents."""
        ids = {r["id"] for r in cmmi_search("Mobil Self-Servis Uygulaması projesi")}
        assert ids and ids <= ALL_CMMI_IDS, (
            f"Expected only CMMI docs from the isolated collection, got {ids}. "
            "Is the CMMI collection populated? (scripts/query/index_cmmi_collection.py)"
        )

    def test_project_id_sparse_match(self, cmmi_search):
        """The exact project ID is a rare token → sparse search should find CMMI docs."""
        ids = {r["id"] for r in cmmi_search("CMMI-IT-2025-014")}
        assert ids & ALL_CMMI_IDS, f"Exact project ID should surface a CMMI doc, got {ids}"

    def test_cmmi_metadata_within_schema(self, cmmi_search):
        """CMMI results must obey the same metadata schema as the small docs."""
        results = cmmi_search("Mobil Self-Servis Uygulaması teknik gereksinim")
        assert results, "No results for the CMMI corpus"
        for r in results:
            assert r["department"] in VALID_DEPARTMENTS, f"Bad department: {r['department']}"
            assert r["document_type"] in VALID_TYPES, f"Bad document_type: {r['document_type']}"
            assert r["status"] in VALID_STATUSES, f"Bad status: {r['status']}"
            assert r["language"] in {"TR", "EN"}, f"Bad language: {r['language']}"
            assert isinstance(r["tags"], list) and r["tags"], f"Tags should be a non-empty list: {r}"
            assert r["version"], "Version should not be empty"
            assert r["author"], "Author should not be empty"


class TestCmmiRetrieval:
    """The core 'does the goal work on long docs' check."""

    @pytest.mark.parametrize("query, expected_id", PER_DOC_QUERIES)
    def test_unique_content_returns_target_doc(self, cmmi_search, query, expected_id):
        results = cmmi_search(query, top_k=3)
        assert results, f"No results for: {query}"
        returned = {r["id"] for r in results}
        assert expected_id in returned, (
            f"Query '{query}' should surface {expected_id} in top-{len(results)}, got {returned}"
        )

    @pytest.mark.parametrize("query, expected_id", TOP_RESULT_QUERIES)
    def test_unambiguous_query_top_result(self, cmmi_search, query, expected_id):
        results = cmmi_search(query, top_k=3)
        assert results, f"No results for: {query}"
        assert results[0]["id"] == expected_id, (
            f"Query '{query}' expected {expected_id} as top result, got {results[0]['id']}"
        )

    def test_each_cmmi_doc_retrievable_at_least_once(self, cmmi_search):
        """Sweep all per-doc queries; every CMMI document must be reachable."""
        covered = set()
        for query, _ in PER_DOC_QUERIES:
            covered |= {r["id"] for r in cmmi_search(query, top_k=3)} & ALL_CMMI_IDS
        missing = ALL_CMMI_IDS - covered
        assert not missing, f"These CMMI docs were never retrieved by any query: {missing}"


class TestCmmiSparse:
    def test_requirement_code_sparse(self, cmmi_search):
        """A requirement code (BUR-001) is an exact token → sparse should pin the BUR doc."""
        ids = {r["id"] for r in cmmi_search("BUR-001")}
        assert "CMMI-IT-004" in ids, (
            f"Requirement code 'BUR-001' should match the BUR doc via sparse, got {ids}"
        )

    def test_exact_capacity_phrase(self, cmmi_search):
        """An exact capacity figure should surface CMMI docs that state it."""
        ids = {r["id"] for r in cmmi_search("500 TPS eşzamanlı kullanıcı")}
        assert ids & ALL_CMMI_IDS, f"Capacity phrase should surface a CMMI doc, got {ids}"


if __name__ == "__main__":
    # Manual diagnostic run (loads the embedding model). Use the project venv:
    #   QDRANT_URL=http://localhost:6333 .venv/bin/python tests/test_cmmi_docs.py
    import os
    import sys

    backend = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
    sys.path.insert(0, backend)
    from data.cmmi_docs import cmmi_documents
    from services.embedding import EmbeddingService

    svc = EmbeddingService(
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        collection_name="kurumsal_kalite_cmmi_docs",
        documents=cmmi_documents,
    )
    print("\nCMMI retrieval diagnostic\n")
    for query, expected in PER_DOC_QUERIES:
        ids = [(r["document"]["id"], round(r["score"], 3)) for r in svc.search(query, top_k=3)]
        hit = expected in [i for i, _ in ids]
        print(f"QUERY: {query}")
        print(f"  TOP 3: {ids}")
        print(f"  EXPECTED: {expected} | HIT: {hit}\n")
