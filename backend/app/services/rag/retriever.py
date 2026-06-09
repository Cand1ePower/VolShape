from __future__ import annotations

import asyncio
from collections import defaultdict

from app.services.rag.bm25 import BM25Index
from app.services.rag.config import RagSettings, get_rag_settings
from app.services.rag.context_builder import build_context_pack
from app.services.rag.embeddings import EmbeddingAdapter
from app.services.rag.ingest import build_default_embedder
from app.services.rag.reranker import ScoreFusionReranker
from app.services.rag.types import RagChunk, RagContextPack, RagHit, RagQuery
from app.services.rag.vector_store import QdrantVectorStore, VectorStoreAdapter


class LocalHybridRetriever:
    """Sparse-only retriever used before dense indexing is available."""

    def __init__(self, chunks: list[RagChunk], settings: RagSettings | None = None) -> None:
        self.settings = settings or get_rag_settings()
        self.bm25 = BM25Index(chunks)
        self.reranker = ScoreFusionReranker()

    def retrieve(self, query: RagQuery) -> RagContextPack:
        bm25_hits = self.bm25.search(query.query, top_k=self.settings.bm25_top_k)
        bm25_hits = _filter_hits(bm25_hits, query)
        hits = self._dedupe_hits(bm25_hits)
        reranked = self.reranker.rerank(query, hits, top_k=self.settings.rerank_top_k)
        return build_context_pack(query, reranked, top_k=self.settings.context_top_k)

    @staticmethod
    def _dedupe_hits(hits: list[RagHit]) -> list[RagHit]:
        seen: set[str] = set()
        deduped: list[RagHit] = []
        for hit in hits:
            if hit.chunk.chunk_id in seen:
                continue
            seen.add(hit.chunk.chunk_id)
            deduped.append(hit)
        return deduped


class HybridRetriever:
    def __init__(
        self,
        chunks: list[RagChunk],
        *,
        settings: RagSettings | None = None,
        embedder: EmbeddingAdapter | None = None,
        vector_store: VectorStoreAdapter | None = None,
    ) -> None:
        self.settings = settings or get_rag_settings()
        self.bm25 = BM25Index(chunks)
        self.embedder = embedder or build_default_embedder(self.settings)
        self.vector_store = vector_store or QdrantVectorStore(
            collection_name=self.settings.collection_name,
            path=self.settings.qdrant_path,
            vector_size=self.settings.embedding_dims,
        )
        self.reranker = ScoreFusionReranker()

    async def retrieve(self, query: RagQuery) -> RagContextPack:
        dense_top_k = query.dense_top_k or self.settings.dense_top_k
        bm25_top_k = query.bm25_top_k or self.settings.bm25_top_k

        filters = _build_source_filters(query)
        dense_hits: list[RagHit] = []
        dense_error: Exception | None = None

        print(
            f"[rag] query_embedding_start text={query.query[:120]!r} "
            f"dense_top_k={dense_top_k} bm25_top_k={bm25_top_k} filters={filters}",
            flush=True,
        )
        try:
            query_vector = (
                await asyncio.wait_for(
                    self.embedder.embed_texts([query.query]),
                    timeout=max(1.0, float(self.settings.query_embedding_timeout_seconds)),
                )
            )[0]
            print(f"[rag] query_embedding_done dims={len(query_vector)}", flush=True)
            dense_hits = self.vector_store.search(query_vector, top_k=dense_top_k, filters=filters)
        except Exception as exc:
            dense_error = exc
            print(
                f"[rag] dense_retrieval_degraded reason={exc.__class__.__name__}: {exc}. "
                f"falling_back=bm25_only",
                flush=True,
            )

        try:
            bm25_hits = self.bm25.search(query.query, top_k=bm25_top_k)
            bm25_hits = _filter_hits(bm25_hits, query)
        except Exception as exc:
            print(
                f"[rag] bm25_retrieval_failed reason={exc.__class__.__name__}: {exc}",
                flush=True,
            )
            if dense_hits:
                bm25_hits = []
            else:
                raise

        print(
            f"[rag] retrieval_candidates dense={len(dense_hits)} bm25={len(bm25_hits)}",
            flush=True,
        )

        if dense_hits:
            fused_hits = _reciprocal_rank_fusion(dense_hits, bm25_hits)
        else:
            fused_hits = self._dedupe_hits(bm25_hits)

        reranked = self.reranker.rerank(query, fused_hits, top_k=self.settings.rerank_top_k)
        print(
            f"[rag] rerank_done mode={'hybrid' if dense_hits else 'bm25_only'} "
            f"fused={len(fused_hits)} reranked={len(reranked)} "
            f"top_titles={[hit.chunk.title for hit in reranked[:5]]}",
            flush=True,
        )
        return build_context_pack(query, reranked, top_k=self.settings.context_top_k)

    @staticmethod
    def _dedupe_hits(hits: list[RagHit]) -> list[RagHit]:
        seen: set[str] = set()
        deduped: list[RagHit] = []
        for hit in hits:
            if hit.chunk.chunk_id in seen:
                continue
            seen.add(hit.chunk.chunk_id)
            deduped.append(hit)
        return deduped


def _build_source_filters(query: RagQuery) -> dict | None:
    if not query.source_types:
        return None
    return {"source_type": [source_type.value for source_type in query.source_types]}


def _filter_hits(hits: list[RagHit], query: RagQuery) -> list[RagHit]:
    if not query.source_types:
        return hits
    allowed_source_types = set(query.source_types)
    filtered = [hit for hit in hits if hit.chunk.source_type in allowed_source_types]
    return [
        RagHit(
            chunk=hit.chunk,
            score=hit.score,
            score_type=hit.score_type,
            rank=rank,
            source=hit.source,
            metadata=hit.metadata,
        )
        for rank, hit in enumerate(filtered, start=1)
    ]


def _reciprocal_rank_fusion(*hit_lists: list[RagHit], k: int = 60) -> list[RagHit]:
    by_chunk_id: dict[str, dict] = defaultdict(lambda: {"chunk": None, "score": 0.0, "sources": [], "meta": {}})
    for hit_list in hit_lists:
        for hit in hit_list:
            entry = by_chunk_id[hit.chunk.chunk_id]
            entry["chunk"] = hit.chunk
            entry["score"] += 1.0 / (k + hit.rank)
            entry["sources"].append(hit.source or hit.score_type)
            entry["meta"][hit.source or hit.score_type] = {"rank": hit.rank, "score": hit.score}

    ranked = sorted(by_chunk_id.values(), key=lambda item: item["score"], reverse=True)
    return [
        RagHit(
            chunk=item["chunk"],
            score=item["score"],
            score_type="rrf",
            rank=rank,
            source="+".join(item["sources"]),
            metadata=item["meta"],
        )
        for rank, item in enumerate(ranked, start=1)
    ]
