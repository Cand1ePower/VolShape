from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


_REPO_ROOT = Path(__file__).resolve().parents[4]


def _resolve_repo_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (_REPO_ROOT / path).resolve()


@dataclass(frozen=True)
class RagSettings:
    source_root: Path
    collection_name: str
    qdrant_path: Path
    manifest_path: Path
    runtime_artifact_path: Path
    pipeline_version: str = "v1"
    chunk_target_chars: int = 700
    chunk_min_chars: int = 220
    chunk_max_chars: int = 1200
    chunk_overlap_chars: int = 100
    dense_top_k: int = 20
    context_top_k: int = 5
    bm25_top_k: int = 20
    rerank_top_k: int = 5
    query_embedding_timeout_seconds: float = 12.0
    embedding_batch_size: int = 32
    qdrant_upsert_batch_size: int = 64
    embedding_provider: str = "jina"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = ""
    embedding_dims: int = 768


def get_rag_settings() -> RagSettings:
    return RagSettings(
        source_root=_resolve_repo_path(os.getenv("RAG_SOURCE_ROOT", "ragdata")),
        collection_name=os.getenv("RAG_COLLECTION_NAME", "volshape_knowledge_v1"),
        qdrant_path=_resolve_repo_path(os.getenv("RAG_QDRANT_PATH", "data/rag_qdrant")),
        manifest_path=_resolve_repo_path(os.getenv("RAG_MANIFEST_PATH", "data/rag_ingest_manifest.json")),
        runtime_artifact_path=_resolve_repo_path(os.getenv("RAG_RUNTIME_ARTIFACT_PATH", "data/rag_runtime_chunks.jsonl")),
        pipeline_version=os.getenv("RAG_PIPELINE_VERSION", "v1"),
        chunk_target_chars=int(os.getenv("RAG_CHUNK_TARGET_CHARS", "700")),
        chunk_min_chars=int(os.getenv("RAG_CHUNK_MIN_CHARS", "220")),
        chunk_max_chars=int(os.getenv("RAG_CHUNK_MAX_CHARS", "1200")),
        chunk_overlap_chars=int(os.getenv("RAG_CHUNK_OVERLAP_CHARS", "100")),
        dense_top_k=int(os.getenv("RAG_DENSE_TOP_K", "20")),
        context_top_k=int(os.getenv("RAG_CONTEXT_TOP_K", "5")),
        bm25_top_k=int(os.getenv("RAG_BM25_TOP_K", "20")),
        rerank_top_k=int(os.getenv("RAG_RERANK_TOP_K", "5")),
        query_embedding_timeout_seconds=float(os.getenv("RAG_QUERY_EMBEDDING_TIMEOUT_SECONDS", "12")),
        embedding_batch_size=int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "32")),
        qdrant_upsert_batch_size=int(os.getenv("RAG_QDRANT_UPSERT_BATCH_SIZE", "64")),
        embedding_provider=os.getenv("RAG_EMBEDDING_PROVIDER", "jina"),
        embedding_api_key=settings.EMBEDDING_API_KEY,
        embedding_base_url=settings.EMBEDDING_BASE_URL,
        embedding_model=settings.EMBEDDING_MODEL,
        embedding_dims=settings.EMBEDDING_DIMS,
    )
