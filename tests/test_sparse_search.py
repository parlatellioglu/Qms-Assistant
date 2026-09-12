import pytest
from conftest import chat


class TestSparseSearch:
    def test_sparse_exact_phrase_pull_request(self, api_ready):
        data = chat("pull request üzerinden")
        returned_ids = {r["id"] for r in data["results"]}
        assert "DOC-004" in returned_ids, (
            f"Sparse should match exact term 'pull request' in DOC-004, got {returned_ids}"
        )

    def test_sparse_exact_phrase_24_saat(self, api_ready):
        data = chat("24 saat içinde")
        returned_ids = {r["id"] for r in data["results"]}
        assert "DOC-003" in returned_ids, (
            f"Sparse should match exact term '24 saat' in DOC-003, got {returned_ids}"
        )

    def test_sparse_version_number_term(self, api_ready):
        data = chat("versiyon numarası")
        returned_ids = {r["id"] for r in data["results"]}
        assert "DOC-007" in returned_ids, (
            f"Sparse should match 'versiyon numarası' in DOC-007, got {returned_ids}"
        )

    def test_sparse_kok_neden_analizi(self, api_ready):
        data = chat("kök neden analizi")
        returned_ids = {r["id"] for r in data["results"]}
        assert "DOC-015" in returned_ids, (
            f"Sparse should match 'kök neden analizi' in DOC-015, got {returned_ids}"
        )

    def test_sparse_picks_more_exact_hits_than_dense_alone(self, api_ready):
        data = chat("yılda en az bir kez")
        returned_ids = {r["id"] for r in data["results"]}
        overlap = returned_ids & {"DOC-009", "DOC-013"}
        assert overlap, (
            f"Sparse should surface docs with exact phrase match, got {returned_ids}"
        )


if __name__ == "__main__":
    from conftest import CHAT_ENDPOINT

    print(f"Testing sparse search at {CHAT_ENDPOINT}\n")

    test_cases = [
        ("pull request üzerinden", {"DOC-004"}),
        ("24 saat içinde", {"DOC-003"}),
        ("versiyon numarası", {"DOC-007"}),
        ("kök neden analizi", {"DOC-015"}),
        ("yılda en az bir kez", {"DOC-009", "DOC-013"}),
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
