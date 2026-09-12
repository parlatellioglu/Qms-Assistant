#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Index the CMMI lifecycle documents into a PARENT/CHILD chunked Qdrant collection
(kurumsal_kalite_cmmi_chunked), separate from both the small-doc demo and the
whole-document CMMI collection (kurumsal_kalite_cmmi_docs) so the chunked vs
whole-doc approaches can be compared side by side.

Children (~500 chars, overlapping) are embedded and stored as points; the parent
(~2000 chars) is carried in each child's payload and returned as context.

By default this uses LATE CHUNKING (phase 2): each parent is encoded once and a
child's dense vector is pooled from that parent's token span, so children carry
surrounding context. Set LATE_CHUNKING=0 to index with naive per-child encoding
(phase 1) instead — useful for an A/B comparison. Whatever you pick here, query
the collection with the same setting (ask_cmmi.py --chunked honours LATE_CHUNKING).

Run with the project venv (needs FlagEmbedding/torch) and a reachable Qdrant:
    QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/query/index_cmmi_chunked.py
    # naive (phase 1) for comparison:
    LATE_CHUNKING=0 QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/query/index_cmmi_chunked.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

from data.cmmi_docs import cmmi_documents  # noqa: E402
from services.embedding import EmbeddingService  # noqa: E402

CMMI_CHUNKED_COLLECTION = "kurumsal_kalite_cmmi_chunked"


def main():
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    svc = EmbeddingService(
        qdrant_url=qdrant_url,
        collection_name=CMMI_CHUNKED_COLLECTION,
        index_on_init=False,  # we drive chunked indexing explicitly below
    )
    mode = "late chunking (phase 2)" if svc.late_chunking else "naive per-child (phase 1)"
    print(f"Indexing mode: {mode}")
    n_children, n_parents = svc.index_chunked(cmmi_documents)
    print(f"Collection '{CMMI_CHUNKED_COLLECTION}' now holds {n_children} child points "
          f"across {n_parents} parents ({len(cmmi_documents)} CMMI documents).")


if __name__ == "__main__":
    main()
