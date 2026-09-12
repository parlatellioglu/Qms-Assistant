import pytest
from conftest import chat


class TestTableDocument:
    def test_priority_matrix_returns_doc_016(self, api_ready):
        data = chat("P1 kritik öncelik yanıt süresi")
        returned_ids = {r["id"] for r in data["results"]}
        assert "DOC-016" in returned_ids, (
            f"Priority query should return DOC-016, got {returned_ids}"
        )

    def test_priority_exact_phrase_sparse(self, api_ready):
        data = chat("30 dakika yanıt süresi")
        returned_ids = {r["id"] for r in data["results"]}
        assert "DOC-016" in returned_ids, (
            f"Exact phrase '30 dakika' should match DOC-016 via sparse, got {returned_ids}"
        )

    def test_priority_p4_dusuk_oncelik(self, api_ready):
        data = chat("P4 düşük öncelik iyileştirme talebi")
        returned_ids = {r["id"] for r in data["results"]}
        assert "DOC-016" in returned_ids, (
            f"P4 query should return DOC-016, got {returned_ids}"
        )

    def test_priority_dense_semantic(self, api_ready):
        data = chat("How should I prioritize a production bug?")
        returned_ids = {r["id"] for r in data["results"]}
        assert "DOC-016" in returned_ids, (
            f"Semantic priority query should return DOC-016, got {returned_ids}"
        )

    def test_priority_top_result(self, api_ready):
        data = chat("talep önceliklendirme matrisi")
        first = data["results"][0]
        assert first["id"] == "DOC-016", (
            f"Expected DOC-016 as top result, got {first['id']}"
        )


class TestCsvDocument:
    def test_csv_audit_log_returns_doc_017(self, api_ready):
        data = chat("denetim bulgu kaydı")
        returned_ids = {r["id"] for r in data["results"]}
        assert "DOC-017" in returned_ids, (
            f"Audit query should return DOC-017, got {returned_ids}"
        )

    def test_csv_exact_audit_id_sparse(self, api_ready):
        data = chat("AUD-2025-004")
        returned_ids = {r["id"] for r in data["results"]}
        assert "DOC-017" in returned_ids, (
            f"Exact audit ID 'AUD-2025-004' should match DOC-017 via sparse, got {returned_ids}"
        )

    def test_csv_critical_finding(self, api_ready):
        data = chat("kritik bulgu tedarikçi değerlendirme")
        returned_ids = {r["id"] for r in data["results"]}
        assert "DOC-017" in returned_ids, (
            f"Critical finding query should return DOC-017, got {returned_ids}"
        )

    def test_csv_exact_phrase_sparse(self, api_ready):
        data = chat("tedarikçi değerlendirme formları güncel değil")
        returned_ids = {r["id"] for r in data["results"]}
        assert "DOC-017" in returned_ids, (
            f"Exact phrase should match DOC-017 via sparse, got {returned_ids}"
        )

    def test_csv_major_finding_ik(self, api_ready):
        data = chat("eğitim kayıtları eksik major bulgu")
        returned_ids = {r["id"] for r in data["results"]}
        assert "DOC-017" in returned_ids, (
            f"Training records finding should return DOC-017, got {returned_ids}"
        )

    def test_csv_dense_semantic(self, api_ready):
        data = chat("What audit findings are still open?")
        returned_ids = {r["id"] for r in data["results"]}
        assert "DOC-017" in returned_ids, (
            f"Semantic audit query should return DOC-017, got {returned_ids}"
        )

    def test_csv_top_result(self, api_ready):
        data = chat("denetim bulgu logu")
        first = data["results"][0]
        assert first["id"] == "DOC-017", (
            f"Expected DOC-017 as top result, got {first['id']}"
        )


if __name__ == "__main__":
    from conftest import CHAT_ENDPOINT

    print(f"Testing table & CSV documents at {CHAT_ENDPOINT}\n")

    test_cases = [
        # DOC-016: İstek Önceliklendirme Tablosu
        ("P1 kritik öncelik yanıt süresi", {"DOC-016"}),
        ("30 dakika yanıt süresi", {"DOC-016"}),
        ("P4 düşük öncelik iyileştirme talebi", {"DOC-016"}),
        ("How should I prioritize a production bug?", {"DOC-016"}),
        ("talep önceliklendirme matrisi", {"DOC-016"}),
        # DOC-017: Denetim Bulgu Logu
        ("denetim bulgu kaydı", {"DOC-017"}),
        ("AUD-2025-004", {"DOC-017"}),
        ("kritik bulgu tedarikçi değerlendirme", {"DOC-017"}),
        ("tedarikçi değerlendirme formları güncel değil", {"DOC-017"}),
        ("eğitim kayıtları eksik major bulgu", {"DOC-017"}),
        ("What audit findings are still open?", {"DOC-017"}),
        ("denetim bulgu logu", {"DOC-017"}),
    ]

    for query, expected in test_cases:
        try:
            data = chat(query)
            returned_ids = {r["id"] for r in data["results"]}
            overlap = returned_ids & expected
            print(f"QUERY: {query}")
            print(f"  TOP 3: {[(r['id'], r['title'], round(r['similarity_score'], 3)) for r in data['results']]}")
            print(f"  EXPECTED: {expected} | HIT: {overlap}")
            print()
        except Exception as e:
            print(f"QUERY: {query} — ERROR: {e}\n")
