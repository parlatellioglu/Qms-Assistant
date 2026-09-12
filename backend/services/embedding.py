import threading
import os
from collections import defaultdict
from typing import List, Dict
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    SparseVector,
    Prefetch,
    FusionQuery,
    Fusion,
    Filter,
    FieldCondition,
    MatchAny,
    FilterSelector,
)

from data.small_docs import sample_documents

# Per-document aggregation for chunked retrieval: a doc's rank score is
#   best_child + PARENT_AGG_LAMBDA * (sum_children - best_child)
# λ=0 → best-child only (a short, single-chunk doc can win); λ=1 → pure sum
# (long, multi-chunk docs win). 0.5 keeps a strongly-matching short doc on top
# for narrow queries while letting a long doc whose relevance is spread across
# several chunks surface for broad/thematic queries. See search_chunked.
PARENT_AGG_LAMBDA = 0.5


class EmbeddingService:
    def __init__(self, model_name: str | None = None, qdrant_url: str | None = None,
                 collection_name: str | None = None, documents: list | None = None,
                 model=None, index_on_init: bool = True,
                 late_chunking: bool | None = None):
        if qdrant_url is None:
            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.collection_name = collection_name or "kurumsal_kalite_docs"
        # Late chunking (phase 2): index_chunked/search_chunked encode children by
        # pooling per-child token spans from a single parent forward pass instead
        # of embedding each child in isolation. Defaults on; LATE_CHUNKING=0 (or
        # passing False) reproduces phase-1 naive chunking for side-by-side runs.
        # Indexing and querying must agree, so they share this flag/env default.
        if late_chunking is None:
            late_chunking = os.getenv("LATE_CHUNKING", "1").lower() not in ("0", "false", "no")
        self.late_chunking = late_chunking
        # An already-loaded model can be injected (e.g. to share one bge-m3 across
        # several collections in tests). index_on_init=False attaches to an existing,
        # already-indexed collection for query-only use (no whole-doc re-indexing).
        if model is not None:
            self.model = model
        else:
            if model_name is None:
                model_name = os.getenv(
                    "EMBEDDING_MODEL_NAME",
                    "BAAI/bge-m3",
                )
            print(f"Loading embedding model: {model_name}...")
            from FlagEmbedding import BGEM3FlagModel
            self.model = BGEM3FlagModel(model_name, use_fp16=False)

        print(f"Connecting to Qdrant at {qdrant_url}...")
        self.qdrant = QdrantClient(url=qdrant_url)
        self.documents = documents if documents is not None else sample_documents

        if index_on_init:
            self._initialize_qdrant()

    def _initialize_qdrant(self):
        print("Checking Qdrant collection...")
        if self.qdrant.collection_exists(self.collection_name):
            info = self.qdrant.get_collection(self.collection_name)
            has_sparse = getattr(info.config.params, 'sparse_vectors_config', None) is not None
            if not has_sparse:
                print(f"Collection '{self.collection_name}' has old schema. Deleting and recreating...")
                self.qdrant.delete_collection(self.collection_name)
            else:
                print(f"Collection '{self.collection_name}' already exists with hybrid schema.")
                return
        self._create_collection()
        print("Collection created. Uploading sample documents...")
        self._upload_documents()

    def _create_collection(self):
        print(f"Creating collection '{self.collection_name}'...")
        self.qdrant.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=self.model.model.config.hidden_size,
                    distance=Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams(on_disk=False),
                ),
            },
        )

    def _encode_hybrid(self, texts: List[str]):
        output = self.model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense_vecs = output["dense_vecs"]
        lexical_weights_list = output["lexical_weights"]
        return dense_vecs, lexical_weights_list

    def _encode_query_hybrid(self, query: str):
        output = self.model.encode(
            query,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense_vec = output["dense_vecs"]
        lexical_weights = output["lexical_weights"]
        if dense_vec.ndim > 1:
            dense_vec = dense_vec[0]
        return dense_vec, lexical_weights

    def _upload_documents(self):
        texts = [doc["content"] for doc in self.documents]
        dense_vecs, lexical_weights_list = self._encode_hybrid(texts)

        points = []
        for doc, dense_emb, lexical in zip(self.documents, dense_vecs, lexical_weights_list):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc["id"]))
            sparse_indices = sorted(lexical.keys())
            sparse_values = [lexical[idx] for idx in sparse_indices]
            points.append(PointStruct(
                id=point_id,
                vector={
                    "dense": dense_emb.tolist(),
                    "sparse": SparseVector(
                        indices=sparse_indices,
                        values=sparse_values,
                    ),
                },
                payload={
                    "id": doc["id"],
                    "title": doc["title"],
                    "department": doc.get("department"),
                    "document_type": doc.get("document_type"),
                    "status": doc.get("status"),
                    "version": doc.get("version"),
                    "author": doc.get("author"),
                    "created_date": doc.get("created_date"),
                    "language": doc.get("language"),
                    "tags": doc.get("tags", []),
                    "content": doc["content"],
                },
            ))

        self.qdrant.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        print("Documents uploaded to Qdrant successfully.")

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        dense_query, lexical_weights = self._encode_query_hybrid(query)
        sparse_indices = sorted(lexical_weights.keys())
        sparse_values = [lexical_weights[idx] for idx in sparse_indices]

        limit = top_k * 3

        search_result = self.qdrant.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(
                    query=dense_query.tolist(),
                    using="dense",
                    limit=limit,
                ),
                Prefetch(
                    query=SparseVector(
                        indices=sparse_indices,
                        values=sparse_values,
                    ),
                    using="sparse",
                    limit=limit,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=top_k,
        )

        results = []
        for hit in search_result.points:
            results.append({
                "document": {
                    "id": hit.payload["id"],
                    "title": hit.payload["title"],
                    "department": hit.payload.get("department"),
                    "document_type": hit.payload.get("document_type"),
                    "status": hit.payload.get("status"),
                    "version": hit.payload.get("version"),
                    "author": hit.payload.get("author"),
                    "created_date": hit.payload.get("created_date"),
                    "language": hit.payload.get("language"),
                    "tags": hit.payload.get("tags", []),
                    "content": hit.payload["content"],
                },
                "score": float(hit.score),
            })

        return results

    # ------------------------------------------------------------------ #
    #  Parent/child chunked retrieval (phase 1)
    #
    #  Children are split from parents, embedded, and stored as the Qdrant
    #  points; the parent text is carried in each child's payload and returned
    #  as the LLM context on retrieval. Child embeddings are computed naively
    #  here (one encode per child). When self.late_chunking is on, index_chunked
    #  instead pools per-child token spans from a single parent forward pass
    #  (services.late_chunking) so children carry surrounding-parent context.
    # ------------------------------------------------------------------ #
    def _hf_backbone(self):
        """Underlying HF transformer + tokenizer behind the BGE-M3 wrapper.

        Late chunking needs token-level hidden states, which the FlagEmbedding
        M3 wrapper exposes one level below its dense/sparse encode() API.
        """
        return self.model.model.model, self.model.tokenizer

    def encode_children(self, child_texts: List[str]):
        """Encode child chunks independently (naive, phase-1 hybrid encoding).

        Used when late chunking is off. The late path lives in index_chunked,
        which needs the parent grouping that this flat-list seam can't carry.
        """
        return self._encode_hybrid(child_texts)

    def _drop_document_points(self, doc_ids) -> None:
        """Remove every existing point belonging to ``doc_ids``.

        Chunk point ids are deterministic (uuid5 over "doc:parent:child"), so a
        re-index overwrites a document's chunks in place. That is not enough on
        its own: if the new version of a document produces FEWER chunks than the
        old one, the surplus points survive with stale text and keep being
        retrieved. Deleting the document's points first makes a re-index of one
        document exact rather than merely additive.
        """
        self.qdrant.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(
                filter=Filter(must=[FieldCondition(key="id", match=MatchAny(any=list(doc_ids)))])
            ),
        )

    def index_chunked(self, documents=None, parent_max_chars: int = 2000,
                      child_max_chars: int = 500, child_overlap: int = 80,
                      recreate: bool = True):
        """Index parent/child chunks of ``documents``.

        ``recreate=True`` (the default, and what the corpus build scripts use)
        drops and rebuilds the whole collection — the right thing when the corpus
        is regenerated wholesale.

        ``recreate=False`` adds to an existing collection instead: only the given
        documents are re-embedded, and only their own points are replaced. Adding
        one document to a corpus of fourteen then costs one document's worth of
        encoding rather than the whole corpus, which on CPU is the difference
        between seconds and minutes. Re-running it on an unchanged document is a
        no-op in effect, since the point ids are deterministic.
        """
        from services.chunking import split_parents, split_children, locate_children

        documents = documents if documents is not None else self.documents

        if recreate:
            if self.qdrant.collection_exists(self.collection_name):
                print(f"Recreating collection '{self.collection_name}' for chunked indexing...")
                self.qdrant.delete_collection(self.collection_name)
            self._create_collection()
        else:
            if not self.qdrant.collection_exists(self.collection_name):
                self._create_collection()
            else:
                doc_ids = [d["id"] for d in documents]
                print(f"Appending to '{self.collection_name}': replacing points for {doc_ids}")
                self._drop_document_points(doc_ids)

        child_texts: List[str] = []
        meta: List[tuple] = []  # (doc, parent_index, parent_text, child_index, child_text)
        # parent_groups mirrors meta's order: (parent_text, [(child, start, end), ...]).
        # Late chunking encodes each parent once and pools these per-child spans.
        parent_groups: List[tuple] = []
        for doc in documents:
            parents = split_parents(doc["content"], parent_max_chars)
            for p_idx, parent in enumerate(parents):
                children = split_children(parent, child_max_chars, child_overlap)
                spans = locate_children(parent, children)
                parent_groups.append((parent, spans))
                for c_idx, (child, _start, _end) in enumerate(spans):
                    child_texts.append(child)
                    meta.append((doc, p_idx, parent, c_idx, child))

        n_parents = len({(m[0]["id"], m[1]) for m in meta})
        mode = "late-chunked" if self.late_chunking else "naive per-child"
        print(f"Encoding {len(child_texts)} child chunks "
              f"({n_parents} parents, {len(documents)} documents) [{mode}]...")
        if self.late_chunking:
            # Dense = context-aware pooled spans; sparse stays per-child (lexical
            # weights have no context-aware form), so reuse _encode_hybrid for it.
            from services.late_chunking import encode_documents_late
            hf_model, tokenizer = self._hf_backbone()
            dense_vecs = encode_documents_late(hf_model, tokenizer, parent_groups)
            _, lexical_weights_list = self._encode_hybrid(child_texts)
        else:
            dense_vecs, lexical_weights_list = self.encode_children(child_texts)

        points = []
        for (doc, p_idx, parent, c_idx, child), dense_emb, lexical in zip(
            meta, dense_vecs, lexical_weights_list
        ):
            parent_id = f'{doc["id"]}#p{p_idx}'
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f'{doc["id"]}:{p_idx}:{c_idx}'))
            sparse_indices = sorted(lexical.keys())
            sparse_values = [lexical[idx] for idx in sparse_indices]
            points.append(PointStruct(
                id=point_id,
                vector={
                    "dense": dense_emb.tolist(),
                    "sparse": SparseVector(indices=sparse_indices, values=sparse_values),
                },
                payload={
                    # document-level metadata (mirrors the whole-doc payload)
                    "id": doc["id"],
                    "title": doc["title"],
                    "department": doc.get("department"),
                    "document_type": doc.get("document_type"),
                    "status": doc.get("status"),
                    "version": doc.get("version"),
                    "author": doc.get("author"),
                    "created_date": doc.get("created_date"),
                    "language": doc.get("language"),
                    "tags": doc.get("tags", []),
                    # chunk-level fields
                    "parent_id": parent_id,
                    "parent_index": p_idx,
                    "child_index": c_idx,
                    "parent_text": parent,
                    "child_text": child,
                    # what we hand to the LLM as context = the parent chunk
                    "content": parent,
                },
            ))

        self.qdrant.upsert(collection_name=self.collection_name, points=points)
        print(f"Uploaded {len(points)} child points to '{self.collection_name}'.")
        return len(points), n_parents

    def search_chunked(self, query: str, top_k: int = 3) -> List[Dict]:
        """Hybrid-search child chunks, aggregate per document, return top_k docs.

        The query uses BGE-M3's native (CLS) encoding in both modes — late
        chunking only changes how *documents* are pooled to inject parent
        context; a short query needs no such context, and empirically the native
        query encoding retrieves the (mean-pooled) late children better than a
        mean-pooled query would.

        Children are fused (dense + sparse RRF), then grouped by DOCUMENT and
        scored as best_child + λ·(sum_children − best_child) (PARENT_AGG_LAMBDA).
        Ranking on the single best child alone let a long plan — whose relevance
        is split across several chunks — lose to a short, densely on-topic doc
        (e.g. a one-paragraph certificate) on broad queries; the blend rewards
        documents that match across multiple chunks without burying a strong
        short doc. One entry per document is returned (its best-matching parent
        chunk as context), so a single document no longer floods several slots.
        """
        dense_query, lexical_weights = self._encode_query_hybrid(query)
        sparse_indices = sorted(lexical_weights.keys())
        sparse_values = [lexical_weights[idx] for idx in sparse_indices]

        # Pool enough children to see a document's spread-out matches; aggregation
        # is over documents, so this is independent of top_k. RRF scores decay
        # with rank, so tail children barely affect the sum.
        child_limit = max(top_k * 10, 64)

        search_result = self.qdrant.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(query=dense_query.tolist(), using="dense", limit=child_limit),
                Prefetch(
                    query=SparseVector(indices=sparse_indices, values=sparse_values),
                    using="sparse",
                    limit=child_limit,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=child_limit,
        )

        # Group child hits by document; keep each doc's best-scoring hit (its
        # parent chunk is the context we return) and all child scores (to rank).
        child_scores: Dict[str, List[float]] = defaultdict(list)
        best_hit: Dict[str, object] = {}
        for hit in search_result.points:
            doc_id = hit.payload["id"]
            score = float(hit.score)
            child_scores[doc_id].append(score)
            if doc_id not in best_hit or score > float(best_hit[doc_id].score):
                best_hit[doc_id] = hit

        def doc_score(doc_id: str) -> float:
            scores = child_scores[doc_id]
            best = max(scores)
            return best + PARENT_AGG_LAMBDA * (sum(scores) - best)

        ranked_docs = sorted(child_scores, key=doc_score, reverse=True)[:top_k]

        results = []
        for doc_id in ranked_docs:
            hit = best_hit[doc_id]
            results.append({
                "document": {
                    "id": hit.payload["id"],
                    "title": hit.payload["title"],
                    "department": hit.payload.get("department"),
                    "document_type": hit.payload.get("document_type"),
                    "status": hit.payload.get("status"),
                    "version": hit.payload.get("version"),
                    "author": hit.payload.get("author"),
                    "created_date": hit.payload.get("created_date"),
                    "language": hit.payload.get("language"),
                    "tags": hit.payload.get("tags", []),
                    "content": hit.payload.get("parent_text"),
                },
                "score": doc_score(doc_id),
                "parent_id": hit.payload.get("parent_id"),
                "matched_child": hit.payload.get("child_text"),
            })

        return results


embedding_service = None
embedding_init_thread = None
embedding_init_error = None
embedding_init_lock = threading.Lock()


def init_embedding_service():
    global embedding_service
    if embedding_service is None:
        # The /chat app serves the CMMI chunked collection by default (the
        # ask_cmmi --chunked flow); override with CHAT_COLLECTION if needed.
        # index_on_init=False: the collection is indexed out-of-band by
        # scripts/query/index_cmmi_chunked.py — attach query-only, never re-upload
        # (the default True would whole-doc-index sample_documents into it).
        embedding_service = EmbeddingService(
            collection_name=os.getenv("CHAT_COLLECTION", "kurumsal_kalite_cmmi_chunked"),
            index_on_init=False,
        )


def _initialize_embedding_service_background():
    global embedding_service, embedding_init_error
    try:
        init_embedding_service()
    except Exception as exc:
        embedding_init_error = exc


def start_embedding_service_background():
    global embedding_init_thread
    with embedding_init_lock:
        if embedding_service is not None or embedding_init_thread is not None:
            return

        embedding_init_thread = threading.Thread(
            target=_initialize_embedding_service_background,
            daemon=True,
            name="embedding-service-init",
        )
        embedding_init_thread.start()


def get_embedding_service() -> EmbeddingService:
    global embedding_service
    if embedding_service is None:
        if embedding_init_error is not None:
            raise embedding_init_error
        raise RuntimeError("Embedding service is still loading. Try again in a few seconds.")
    return embedding_service


def is_embedding_service_ready() -> bool:
    return embedding_service is not None


def get_embedding_service_error():
    return embedding_init_error
