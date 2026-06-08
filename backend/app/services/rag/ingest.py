from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.services.rag.chunker import chunk_documents
from app.services.rag.config import RagSettings, get_rag_settings
from app.services.rag.embeddings import OpenAICompatibleEmbeddingAdapter, embed_in_batches
from app.services.rag.loaders import discover_markdown_sources, load_markdown_document, load_markdown_documents
from app.services.rag.manifest import (
    RagManifest,
    build_manifest_entry,
    build_manifest_entry_for_source,
    build_source_fingerprint,
    manifest_entry_matches,
)
from app.services.rag.runtime_store import RuntimeChunkArtifact
from app.services.rag.types import RagIngestPreview, RagIngestResult
from app.services.rag.vector_store import QdrantVectorStore


def build_ingest_preview(root: Path | None = None, settings: RagSettings | None = None, *, sample_size: int = 5) -> RagIngestPreview:
    settings = settings or get_rag_settings()
    source_root = root or settings.source_root
    documents, skipped = load_markdown_documents(source_root)
    chunks = chunk_documents(documents, settings)
    return RagIngestPreview(
        source_count=len(documents) + len(skipped),
        document_count=len(documents),
        chunk_count=len(chunks),
        skipped_empty_sources=tuple(skipped),
        sample_chunks=tuple(chunks[:sample_size]),
    )


async def ingest_sources(
    root: Path | None = None,
    settings: RagSettings | None = None,
    *,
    force: bool = False,
    prune_missing: bool = False,
    progress: Callable[[str], None] | None = None,
) -> RagIngestResult:
    settings = settings or get_rag_settings()
    source_root = root or settings.source_root
    manifest = RagManifest.load(settings.manifest_path)
    runtime_artifact = RuntimeChunkArtifact.load(settings.runtime_artifact_path)
    runtime_source_ids = set(runtime_artifact.chunks_by_source.keys())
    sources = discover_markdown_sources(source_root)
    discovered_source_ids = {source.source_id for source in sources}

    embedder = OpenAICompatibleEmbeddingAdapter(
        api_key=_required_value("EMBEDDING_API_KEY", settings.embedding_api_key),
        base_url=_required_value("EMBEDDING_BASE_URL", settings.embedding_base_url),
        model=_required_value("EMBEDDING_MODEL", settings.embedding_model),
        dimensions=settings.embedding_dims,
    )
    vector_store = QdrantVectorStore(
        collection_name=settings.collection_name,
        path=settings.qdrant_path,
        vector_size=settings.embedding_dims,
    )

    skipped_source_ids: list[str] = []
    processed_source_ids: list[str] = []
    deleted_source_ids: list[str] = []
    embedded_chunks = 0
    upserted_chunks = 0

    for index, source in enumerate(sources, start=1):
        _emit(progress, f"[scan {index}/{len(sources)}] {source.path}")
        fingerprint = build_source_fingerprint(source, settings)
        current_entry = manifest.get(source.source_id)
        document = load_markdown_document(source)

        if document is None:
            if not force and manifest_entry_matches(current_entry, fingerprint=fingerprint, settings=settings):
                had_runtime_entry = source.source_id in runtime_source_ids
                runtime_artifact.delete_source(source.source_id)
                runtime_source_ids.discard(source.source_id)
                if had_runtime_entry:
                    runtime_artifact.save()
                skipped_source_ids.append(source.source_id)
                _emit(progress, f"[skip-empty] {source.source_id}")
                continue

            if current_entry is not None and current_entry.chunk_count > 0:
                vector_store.delete_source(source.source_id)
                deleted_source_ids.append(source.source_id)
                _emit(progress, f"[delete-old-empty] {source.source_id}")

            runtime_artifact.delete_source(source.source_id)
            manifest.upsert(
                build_manifest_entry_for_source(
                    source,
                    settings,
                    fingerprint=fingerprint,
                    chunk_count=0,
                )
            )
            manifest.save(settings.manifest_path)
            runtime_artifact.save()
            processed_source_ids.append(source.source_id)
            _emit(progress, f"[done-empty] {source.source_id}")
            continue

        if not force and manifest_entry_matches(current_entry, fingerprint=fingerprint, settings=settings):
            needs_runtime_sync = current_entry.chunk_count > 0 and source.source_id not in runtime_source_ids
            if needs_runtime_sync:
                chunks = chunk_documents([document], settings)
                runtime_artifact.upsert_source(source.source_id, chunks)
                runtime_source_ids.add(source.source_id)
                runtime_artifact.save()
                processed_source_ids.append(source.source_id)
                _emit(progress, f"[sync-runtime] {source.source_id} -> {len(chunks)} chunks")
                continue
            skipped_source_ids.append(source.source_id)
            _emit(progress, f"[skip-unchanged] {source.source_id}")
            continue

        chunks = chunk_documents([document], settings)
        _emit(progress, f"[chunked] {source.source_id} -> {len(chunks)} chunks")
        if current_entry is not None:
            if current_entry.chunk_count > 0:
                vector_store.delete_source(source.source_id)
                deleted_source_ids.append(source.source_id)
                _emit(progress, f"[delete-old] {source.source_id}")
            runtime_artifact.delete_source(source.source_id)
            runtime_source_ids.discard(source.source_id)

        if not chunks:
            runtime_artifact.delete_source(source.source_id)
            runtime_source_ids.discard(source.source_id)
            manifest.upsert(
                build_manifest_entry(
                    document,
                    settings,
                    fingerprint=fingerprint,
                    chunk_count=0,
                )
            )
            manifest.save(settings.manifest_path)
            runtime_artifact.save()
            processed_source_ids.append(source.source_id)
            _emit(progress, f"[done-empty] {source.source_id}")
            continue

        vectors = await embed_in_batches(
            embedder,
            [chunk.text for chunk in chunks],
            batch_size=settings.embedding_batch_size,
            progress=(lambda message, sid=source.source_id: _emit(progress, f"[embed {sid}] {message}")),
        )
        embedded_chunks += len(vectors)
        vector_store.upsert_chunks(
            chunks,
            vectors,
            batch_size=settings.qdrant_upsert_batch_size,
        )
        runtime_artifact.upsert_source(source.source_id, chunks)
        runtime_source_ids.add(source.source_id)
        upserted_chunks += len(chunks)
        _emit(progress, f"[upserted] {source.source_id} -> {len(chunks)} chunks")
        manifest.upsert(
            build_manifest_entry(
                document,
                settings,
                fingerprint=fingerprint,
                chunk_count=len(chunks),
            )
        )
        manifest.save(settings.manifest_path)
        runtime_artifact.save()
        processed_source_ids.append(source.source_id)
        _emit(progress, f"[done] {source.source_id}")

    if prune_missing:
        stale_source_ids = [
            source_id
            for source_id in list(manifest.entries.keys())
            if source_id not in discovered_source_ids
        ]
        for source_id in stale_source_ids:
            entry = manifest.get(source_id)
            if entry is not None and entry.chunk_count > 0:
                vector_store.delete_source(source_id)
            manifest.remove(source_id)
            runtime_artifact.delete_source(source_id)
            runtime_source_ids.discard(source_id)
            deleted_source_ids.append(source_id)
            _emit(progress, f"[prune-missing] {source_id}")

    manifest.save(settings.manifest_path)
    runtime_artifact.save()
    _emit(progress, "[complete] ingest finished")
    return RagIngestResult(
        scanned_sources=len(sources),
        processed_sources=len(processed_source_ids),
        skipped_sources=len(skipped_source_ids),
        deleted_sources=len(deleted_source_ids),
        embedded_chunks=embedded_chunks,
        upserted_chunks=upserted_chunks,
        collection_name=settings.collection_name,
        manifest_path=str(settings.manifest_path),
        runtime_artifact_path=str(settings.runtime_artifact_path),
        skipped_source_ids=tuple(skipped_source_ids),
        processed_source_ids=tuple(processed_source_ids),
        deleted_source_ids=tuple(deleted_source_ids),
    )


def _required_value(name: str, fallback: str) -> str:
    value = fallback.strip() if fallback else ""
    if not value:
        raise ValueError(f"Missing required embedding config: {name}")
    return value


def build_default_embedder(settings: RagSettings | None = None) -> OpenAICompatibleEmbeddingAdapter:
    settings = settings or get_rag_settings()
    return OpenAICompatibleEmbeddingAdapter(
        api_key=_required_value("EMBEDDING_API_KEY", settings.embedding_api_key),
        base_url=_required_value("EMBEDDING_BASE_URL", settings.embedding_base_url),
        model=_required_value("EMBEDDING_MODEL", settings.embedding_model),
        dimensions=settings.embedding_dims,
    )


def _emit(progress: Callable[[str], None] | None, message: str) -> None:
    if progress:
        progress(message)
