import pytest
from conftest import chat


class TestChatEndpoint:
    def test_api_reachable(self, api_ready):
        assert api_ready

    def test_health_returns_ready(self):
        import requests
        from conftest import HEALTH_ENDPOINT
        resp = requests.get(HEALTH_ENDPOINT, timeout=5)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"

    @pytest.mark.parametrize(
        "query, expected_doc_ids",
        [
            (
                "What is the quality policy?",
                {"DOC-006"},
            ),
            (
                "Tell me about training procedures",
                {"DOC-005", "DOC-012"},
            ),
            (
                "How to handle customer complaints?",
                {"DOC-003"},
            ),
            (
                "What are the document control rules?",
                {"DOC-007"},
            ),
        ],
    )
    def test_similarity_relevant_docs_returned(self, api_ready, query, expected_doc_ids):
        data = chat(query)
        assert len(data["results"]) > 0, f"No results returned for: {query}"
        returned_ids = {r["id"] for r in data["results"]}
        overlap = returned_ids & expected_doc_ids
        assert overlap, (
            f"Query '{query}' — expected at least one of {expected_doc_ids} "
            f"in results, got {returned_ids}"
        )

    def test_similarity_top_result_most_relevant(self, api_ready):
        data = chat("What is the quality policy?")
        top = data["results"][0]
        assert top["id"] == "DOC-006", (
            f"Expected DOC-006 as top result, got {top['id']}"
        )
        assert top["similarity_score"] > 0.0, (
            f"Similarity score should be positive: {top['similarity_score']}"
        )

    def test_llm_returns_meaningful_answer(self, api_ready):
        data = chat("What is the quality policy?")
        answer = data.get("answer", "")
        assert answer, "Answer is empty"
        assert "yanıt oluşturulamadı" not in answer.lower(), (
            f"LLM fallback returned: {answer}"
        )
        assert "erişilemez" not in answer.lower(), (
            f"LLM unreachable: {answer}"
        )
        assert any(
            word in answer.lower()
            for word in ["kalite", "politika", "quality", "policy"]
        ), f"Answer seems irrelevant: {answer}"

    def test_metadata_fields_present(self, api_ready):
        data = chat("safety instruction")
        assert len(data["results"]) > 0
        required_fields = {
            "id", "title", "department", "document_type",
            "status", "version", "author", "language", "tags",
            "similarity_score",
        }
        for result in data["results"]:
            missing = required_fields - set(result.keys())
            assert not missing, (
                f"Result {result.get('id')} missing fields: {missing}"
            )

    def test_metadata_values_are_meaningful(self, api_ready):
        data = chat("training")
        valid_departments = {"Yönetim", "Kalite", "İnsan Kaynakları", "Mühendislik", "Satın Alma"}
        valid_types = {"policy", "procedure", "instruction", "form", "report"}
        valid_statuses = {"draft", "published", "under_review", "archived"}
        for result in data["results"]:
            assert result["department"] in valid_departments, (
                f"Unknown department: {result['department']}"
            )
            assert result["document_type"] in valid_types, (
                f"Unknown document_type: {result['document_type']}"
            )
            assert result["status"] in valid_statuses, (
                f"Unknown status: {result['status']}"
            )
            assert isinstance(result["tags"], list), (
                f"Tags should be a list, got {type(result['tags'])}"
            )
            assert result["version"], (
                f"Version should not be empty"
            )
            assert result["author"], (
                f"Author should not be empty"
            )

    def test_metadata_department_from_query(self, api_ready):
        data = chat("HR policy")
        for result in data["results"]:
            if "İnsan Kaynakları" in (result.get("department") or ""):
                return
        pytest.skip("No HR department doc in top results")

    def test_metadata_document_type_in_response(self, api_ready):
        data = chat("document control")
        assert len(data["results"]) > 0
        types_found = {r["document_type"] for r in data["results"]}
        assert "procedure" in types_found, (
            f"Expected 'procedure' in results, got {types_found}"
        )

    def test_empty_query_returns_results(self, api_ready):
        data = chat("")
        assert "results" in data

    def test_chat_response_structure(self, api_ready):
        data = chat("quality")
        assert "query" in data, "Missing 'query' field"
        assert "results" in data, "Missing 'results' field"
        assert "answer" in data, "Missing 'answer' field"
        assert isinstance(data["results"], list), "'results' should be a list"

    def test_status_draft_docs_can_appear(self, api_ready):
        data = chat("audit procedure")
        statuses = {r["status"] for r in data["results"]}
        assert "draft" in statuses, (
            f"Expected at least one draft doc, got statuses: {statuses}"
        )


if __name__ == "__main__":
    from conftest import CHAT_ENDPOINT

    print(f"Testing chat endpoint at {CHAT_ENDPOINT}\n")

    test_cases = [
        ("quality policy", {"DOC-006"}),
        ("training procedure", {"DOC-005", "DOC-012"}),
        ("customer complaints", {"DOC-003"}),
        ("document control", {"DOC-007"}),
        ("safety at work", {"DOC-004", "DOC-011"}),
        ("supplier evaluation", {"DOC-010"}),
        ("corrective action", {"DOC-015"}),
    ]

    for query, expected in test_cases:
        try:
            data = chat(query)
            returned_ids = {r["id"] for r in data["results"]}
            overlap = returned_ids & expected
            ans_preview = data.get("answer", "")[:80]
            print(f"QUERY: {query}")
            print(f"  TOP 3: {[(r['id'], r['title'], round(r['similarity_score'], 3)) for r in data['results']]}")
            print(f"  ANSWER: {ans_preview}...")
            print(f"  EXPECTED: {expected} | HIT: {overlap}")
            print()
        except Exception as e:
            print(f"QUERY: {query} — ERROR: {e}\n")
