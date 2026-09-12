#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ad-hoc query tool for the isolated CMMI collections.

Retrieval-only by default (fast, no LLM). Add --answer to also generate an LLM
answer with the same prompt as the /chat endpoint (needs Ollama running).

By default queries the whole-document collection (kurumsal_kalite_cmmi_docs).
Pass --chunked to query the parent/child chunked collection
(kurumsal_kalite_cmmi_chunked) instead: child chunks are searched and the unique
parent chunks are returned as context. This lets you compare whole-doc vs chunked
retrieval on the same query.

Run with the project venv and a reachable Qdrant. The collection you query must
already be indexed:
    whole-doc -> scripts/query/index_cmmi_collection.py
    chunked   -> scripts/query/index_cmmi_chunked.py

Examples:
    # one-shot query (whole-doc)
    QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/query/ask_cmmi.py "kabul kriterleri nelerdir"

    # query the chunked collection (returns parent chunks)
    QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/query/ask_cmmi.py --chunked "kabul kriterleri nelerdir"

    # interactive: type queries until you enter a blank line
    QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/query/ask_cmmi.py

    # also generate the LLM answer (needs Ollama)
    OLLAMA_URL=http://localhost:11434 QDRANT_URL=http://localhost:6333 \
        .venv/bin/python scripts/query/ask_cmmi.py --answer "test stratejisi nedir"
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from services.embedding import EmbeddingService  # noqa: E402

CMMI_COLLECTION = "kurumsal_kalite_cmmi_docs"
CMMI_CHUNKED_COLLECTION = "kurumsal_kalite_cmmi_chunked"
TOP_K = 3
TOP_K_CHUNKED = 3


def main():
    args = sys.argv[1:]
    want_answer = "--answer" in args
    want_chunked = "--chunked" in args
    query_args = [a for a in args if a not in ("--answer", "--chunked")]

    collection = CMMI_CHUNKED_COLLECTION if want_chunked else CMMI_COLLECTION
    svc = EmbeddingService(
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        collection_name=collection,
        index_on_init=False,  # query-only; collection already indexed
    )
    mode = ""
    if want_chunked:
        mode = " [late chunking]" if svc.late_chunking else " [naive chunking]"
    print(f"Querying collection: {collection}"
          + (" (parent/child chunked)" if want_chunked else " (whole-doc)") + mode)

    def run(query: str):
        top_k = TOP_K_CHUNKED if want_chunked else TOP_K
        results = (svc.search_chunked(query, top_k=top_k) if want_chunked
                   else svc.search(query, top_k=top_k))
        print("\nSources (top {}):".format(top_k))
        for r in results:
            d = r["document"]
            print(f"  {d['id']:12s} {r['score']:.3f}  {d['title']}")
            if want_chunked:
                child = (r.get("matched_child") or "").replace("\n", " ")
                snippet = child[:100] + ("…" if len(child) > 100 else "")
                print(f"               matched child: {snippet}")
        if want_answer:
            from services.llm import generate_answer
            print("\nAnswer:\n" + generate_answer(query, results))

    if query_args:
        run(" ".join(query_args))
        return

    print("CMMI sorgu aracı — boş satır girince çıkar.")
    while True:
        try:
            query = input("\nSoru: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not query:
            break
        run(query)


if __name__ == "__main__":
    main()
