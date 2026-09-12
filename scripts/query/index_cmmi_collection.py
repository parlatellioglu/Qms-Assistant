#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Index the CMMI lifecycle documents into their own isolated Qdrant collection
(kurumsal_kalite_cmmi_docs), separate from the small-doc demo collection so the
two corpora never interfere.

Order:
    1. python3 scripts/corpus/build_cmmi_corpus.py  # (re)generate backend/data/cmmi_docs.py
    2. python3 scripts/query/index_cmmi_collection.py # index into Qdrant

Run with the project venv (needs FlagEmbedding/torch) and a reachable Qdrant:
    QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/query/index_cmmi_collection.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

from data.cmmi_docs import cmmi_documents  # noqa: E402
from services.embedding import EmbeddingService  # noqa: E402

CMMI_COLLECTION = "kurumsal_kalite_cmmi_docs"


def main():
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    svc = EmbeddingService(
        qdrant_url=qdrant_url,
        collection_name=CMMI_COLLECTION,
        documents=cmmi_documents,
    )
    count = svc.qdrant.count(CMMI_COLLECTION).count
    print(f"Collection '{CMMI_COLLECTION}' now holds {count} points "
          f"({len(cmmi_documents)} CMMI documents).")


if __name__ == "__main__":
    main()
