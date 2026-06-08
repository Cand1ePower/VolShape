from __future__ import annotations

from threading import Lock

from app.services.rag.config import RagSettings, get_rag_settings
from app.services.rag.embeddings import EmbeddingAdapter
from app.services.rag.ingest import build_default_embedder
from app.services.rag.retriever import HybridRetriever
from app.services.rag.runtime_store import get_cached_runtime_chunk_store
from app.services.rag.types import RagContextPack, RagQuery
from app.services.rag.vector_store import QdrantVectorStore, VectorStoreAdapter


class RuntimeKnowledgeBase:
    def __init__(
        self,
        *,
        settings: RagSettings | None = None,
        embedder: EmbeddingAdapter | None = None,
        vector_store: VectorStoreAdapter | None = None,
    ) -> None:
        self.settings = settings or get_rag_settings()
        self.embedder = embedder or build_default_embedder(self.settings)
        self.vector_store = vector_store or QdrantVectorStore(
            collection_name=self.settings.collection_name,
            path=self.settings.qdrant_path,
            vector_size=self.settings.embedding_dims,
        )
        self.runtime_store = get_cached_runtime_chunk_store(self.settings.runtime_artifact_path)
        self._lock = Lock()
        self._retriever: HybridRetriever | None = None
        self._artifact_signature = ""

    async def retrieve(self, query: RagQuery) -> RagContextPack:
        snapshot = self.runtime_store.load()
        print(
            f"[rag] runtime_snapshot artifact={self.settings.runtime_artifact_path} "
            f"chunk_count={len(snapshot.chunks)} signature={snapshot.signature}",
            flush=True,
        )
        if not snapshot.chunks:
            print("[rag] runtime_snapshot_empty", flush=True)
            return RagContextPack(query=query, hits=(), token_estimate=0)

        retriever = self._get_retriever(snapshot.signature, list(snapshot.chunks))
        print(
            f"[rag] retrieve query={query.query[:120]!r} intent={query.intent} "
            f"dense_top_k={query.dense_top_k or self.settings.dense_top_k} "
            f"bm25_top_k={query.bm25_top_k or self.settings.bm25_top_k}",
            flush=True,
        )
        return await retriever.retrieve(query)

    def _get_retriever(self, signature: str, chunks) -> HybridRetriever:
        with self._lock:
            if self._retriever is None or self._artifact_signature != signature:
                self._retriever = HybridRetriever(
                    chunks,
                    settings=self.settings,
                    embedder=self.embedder,
                    vector_store=self.vector_store,
                )
                self._artifact_signature = signature
            return self._retriever


_KNOWLEDGE_BASES: dict[str, RuntimeKnowledgeBase] = {}
_KNOWLEDGE_BASES_LOCK = Lock()


def get_runtime_knowledge_base(settings: RagSettings | None = None) -> RuntimeKnowledgeBase:
    settings = settings or get_rag_settings()
    key = "::".join(
        (
            str(settings.runtime_artifact_path.resolve()),
            settings.collection_name,
            settings.embedding_model,
            str(settings.context_top_k),
            str(settings.dense_top_k),
            str(settings.bm25_top_k),
            str(settings.rerank_top_k),
        )
    )
    with _KNOWLEDGE_BASES_LOCK:
        knowledge_base = _KNOWLEDGE_BASES.get(key)
        if knowledge_base is None:
            knowledge_base = RuntimeKnowledgeBase(settings=settings)
            _KNOWLEDGE_BASES[key] = knowledge_base
        return knowledge_base
