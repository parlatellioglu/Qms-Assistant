import os
import sys

import requests
import pytest

BASE_URL = "http://127.0.0.1:8013"
CHAT_ENDPOINT = f"{BASE_URL}/chat"
HEALTH_ENDPOINT = f"{BASE_URL}/health"

# Isolated collection holding the long CMMI lifecycle documents (kept separate
# from the small-doc demo collection so the two corpora don't interfere).
CMMI_COLLECTION = "kurumsal_kalite_cmmi_docs"
# Parent/child chunked variant of the CMMI corpus (phase 1 chunking).
CMMI_CHUNKED_COLLECTION = "kurumsal_kalite_cmmi_chunked"
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")


@pytest.fixture(scope="session")
def api_ready():
    resp = requests.get(HEALTH_ENDPOINT, timeout=5)
    assert resp.status_code == 200, "API is not reachable"
    data = resp.json()
    assert data.get("status") == "ready", f"API not ready: {data}"
    return True


def chat(query: str) -> dict:
    resp = requests.post(CHAT_ENDPOINT, json={"query": query}, timeout=30)
    assert resp.status_code == 200, f"Chat endpoint returned {resp.status_code}"
    return resp.json()


# One bge-m3 instance shared across every collection-search engine in a test
# session (the model is ~2 GB; loading it once per dataset would be wasteful).
_SHARED_MODEL = None


def _flatten(results: list[dict]) -> list[dict]:
    """Flatten EmbeddingService.search() hits into metadata + score dicts."""
    return [
        {
            "id": r["document"]["id"],
            "title": r["document"]["title"],
            "department": r["document"].get("department"),
            "document_type": r["document"].get("document_type"),
            "status": r["document"].get("status"),
            "version": r["document"].get("version"),
            "author": r["document"].get("author"),
            "language": r["document"].get("language"),
            "tags": r["document"].get("tags", []),
            "score": r["score"],
        }
        for r in results
    ]


def make_collection_search(collection_name: str):
    """Build a retrieval-only search over an existing Qdrant collection.

    Returns a callable ``search(query, top_k=3) -> list[dict]`` (one flat dict
    per hit: the document's metadata + score). It runs the same hybrid
    (dense + sparse RRF) retrieval as the live /chat endpoint, but query-only
    (no LLM), so tests are fast and never re-index or touch other collections.

    The collection must already be indexed out-of-band (see scripts/query/index_*.py);
    this attaches to it read-only. The embedding model is loaded once and reused
    across all collections. Requires the project venv (embedding deps) and a
    reachable Qdrant (QDRANT_URL).

    Use it to add a new dataset's fixture in one line:

        @pytest.fixture(scope="session")
        def legal_search():
            return make_collection_search("kurumsal_kalite_legal_docs")
    """
    global _SHARED_MODEL

    backend = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"
    )
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from services.embedding import EmbeddingService

    svc = EmbeddingService(
        qdrant_url=QDRANT_URL,
        collection_name=collection_name,
        model=_SHARED_MODEL,
        index_on_init=False,  # query-only; collection is indexed by scripts/query/index_*.py
    )
    if _SHARED_MODEL is None:
        _SHARED_MODEL = svc.model

    if not svc.qdrant.collection_exists(collection_name):
        raise RuntimeError(
            f"Qdrant collection '{collection_name}' does not exist. "
            f"Index it first (e.g. python scripts/query/index_*.py)."
        )

    def _search(query: str, top_k: int = 3) -> list[dict]:
        return _flatten(svc.search(query, top_k=top_k))

    return _search


@pytest.fixture(scope="session")
def cmmi_search():
    """Retrieval-only search over the isolated CMMI collection."""
    return make_collection_search(CMMI_COLLECTION)


def _flatten_chunked(results: list[dict]) -> list[dict]:
    """Flatten EmbeddingService.search_chunked() hits (parent chunk + chunk info)."""
    return [
        {
            "id": r["document"]["id"],
            "title": r["document"]["title"],
            "department": r["document"].get("department"),
            "document_type": r["document"].get("document_type"),
            "status": r["document"].get("status"),
            "language": r["document"].get("language"),
            "content": r["document"].get("content"),  # the parent chunk
            "parent_id": r.get("parent_id"),
            "matched_child": r.get("matched_child"),
            "score": r["score"],
        }
        for r in results
    ]


def make_chunked_collection_search(collection_name: str):
    """Like make_collection_search, but over a parent/child chunked collection.

    Returns ``search(query, top_k=3) -> list[dict]`` where each hit is a unique
    PARENT chunk (the LLM context) plus the child that matched. The collection
    must be indexed by scripts/query/index_cmmi_chunked.py.
    """
    global _SHARED_MODEL

    backend = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"
    )
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from services.embedding import EmbeddingService

    svc = EmbeddingService(
        qdrant_url=QDRANT_URL,
        collection_name=collection_name,
        model=_SHARED_MODEL,
        index_on_init=False,
    )
    if _SHARED_MODEL is None:
        _SHARED_MODEL = svc.model

    if not svc.qdrant.collection_exists(collection_name):
        raise RuntimeError(
            f"Qdrant collection '{collection_name}' does not exist. "
            f"Index it first: python scripts/query/index_cmmi_chunked.py"
        )

    def _search(query: str, top_k: int = 3) -> list[dict]:
        return _flatten_chunked(svc.search_chunked(query, top_k=top_k))

    return _search


@pytest.fixture(scope="session")
def cmmi_chunked_search():
    """Parent/child chunked retrieval over the isolated CMMI chunked collection."""
    return make_chunked_collection_search(CMMI_CHUNKED_COLLECTION)
