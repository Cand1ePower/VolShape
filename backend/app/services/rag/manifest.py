from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.rag.config import RagSettings
from app.services.rag.types import RagDocument, RagSource


@dataclass
class RagManifestEntry:
    source_id: str
    path: str
    fingerprint: str
    collection_name: str
    embedding_provider: str
    embedding_model: str
    embedding_dims: int
    pipeline_version: str
    chunk_count: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "path": self.path,
            "fingerprint": self.fingerprint,
            "collection_name": self.collection_name,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_dims": self.embedding_dims,
            "pipeline_version": self.pipeline_version,
            "chunk_count": self.chunk_count,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RagManifestEntry":
        return cls(
            source_id=str(data["source_id"]),
            path=str(data["path"]),
            fingerprint=str(data["fingerprint"]),
            collection_name=str(data.get("collection_name", "")),
            embedding_provider=str(data.get("embedding_provider", "")),
            embedding_model=str(data.get("embedding_model", "")),
            embedding_dims=int(data.get("embedding_dims", 0) or 0),
            pipeline_version=str(data.get("pipeline_version", "")),
            chunk_count=int(data.get("chunk_count", 0) or 0),
            updated_at=str(data.get("updated_at", "")),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class RagManifest:
    entries: dict[str, RagManifestEntry]

    @classmethod
    def load(cls, path: Path) -> "RagManifest":
        if not path.exists():
            return cls(entries={})
        data = json.loads(path.read_text(encoding="utf-8"))
        raw_entries = data.get("entries", {})
        return cls(
            entries={
                source_id: RagManifestEntry.from_dict(entry)
                for source_id, entry in raw_entries.items()
            }
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "entries": {
                source_id: entry.to_dict()
                for source_id, entry in sorted(self.entries.items())
            }
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, source_id: str) -> RagManifestEntry | None:
        return self.entries.get(source_id)

    def upsert(self, entry: RagManifestEntry) -> None:
        self.entries[entry.source_id] = entry

    def remove(self, source_id: str) -> RagManifestEntry | None:
        return self.entries.pop(source_id, None)


def build_source_fingerprint(source: RagSource, settings: RagSettings) -> str:
    digest = hashlib.sha256()
    _update_digest_from_file(digest, source.path)
    if source.metadata_path and source.metadata_path.exists():
        _update_digest_from_file(digest, source.metadata_path)
    digest.update(settings.pipeline_version.encode("utf-8"))
    digest.update(str(settings.chunk_target_chars).encode("utf-8"))
    digest.update(str(settings.chunk_min_chars).encode("utf-8"))
    digest.update(str(settings.chunk_max_chars).encode("utf-8"))
    digest.update(str(settings.chunk_overlap_chars).encode("utf-8"))
    digest.update(settings.embedding_provider.encode("utf-8"))
    digest.update((settings.embedding_model or "").encode("utf-8"))
    digest.update(str(settings.embedding_dims).encode("utf-8"))
    return digest.hexdigest()


def build_manifest_entry(document: RagDocument, settings: RagSettings, *, fingerprint: str, chunk_count: int) -> RagManifestEntry:
    return build_manifest_entry_for_source(
        document.source,
        settings,
        fingerprint=fingerprint,
        chunk_count=chunk_count,
    )


def build_manifest_entry_for_source(source: RagSource, settings: RagSettings, *, fingerprint: str, chunk_count: int) -> RagManifestEntry:
    return RagManifestEntry(
        source_id=source.source_id,
        path=str(source.path),
        fingerprint=fingerprint,
        collection_name=settings.collection_name,
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
        embedding_dims=settings.embedding_dims,
        pipeline_version=settings.pipeline_version,
        chunk_count=chunk_count,
        metadata={
            "title": source.title,
            "source_type": source.source_type.value,
            "metadata_path": str(source.metadata_path) if source.metadata_path else None,
        },
    )


def manifest_entry_matches(entry: RagManifestEntry | None, *, fingerprint: str, settings: RagSettings) -> bool:
    if entry is None:
        return False
    return (
        entry.fingerprint == fingerprint
        and entry.collection_name == settings.collection_name
        and entry.embedding_provider == settings.embedding_provider
        and entry.embedding_model == settings.embedding_model
        and entry.embedding_dims == settings.embedding_dims
        and entry.pipeline_version == settings.pipeline_version
    )


def _update_digest_from_file(digest, path: Path) -> None:
    digest.update(str(path).encode("utf-8"))
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
