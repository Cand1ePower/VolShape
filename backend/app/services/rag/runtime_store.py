from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from app.services.rag.types import RagChunk


@dataclass
class RuntimeChunkArtifact:
    path: Path
    chunks_by_source: dict[str, list[RagChunk]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "RuntimeChunkArtifact":
        if not path.exists():
            return cls(path=path)

        chunks_by_source: dict[str, list[RagChunk]] = {}
        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid runtime artifact JSON on line {line_number}: {path}") from exc
                chunk = RagChunk.from_payload(payload)
                chunks_by_source.setdefault(chunk.source_id, []).append(chunk)

        for chunks in chunks_by_source.values():
            chunks.sort(key=lambda item: item.chunk_id)
        return cls(path=path, chunks_by_source=chunks_by_source)

    def upsert_source(self, source_id: str, chunks: list[RagChunk]) -> None:
        self.chunks_by_source[source_id] = sorted(chunks, key=lambda item: item.chunk_id)

    def delete_source(self, source_id: str) -> None:
        self.chunks_by_source.pop(source_id, None)

    def all_chunks(self) -> list[RagChunk]:
        flattened: list[RagChunk] = []
        for source_id in sorted(self.chunks_by_source):
            flattened.extend(self.chunks_by_source[source_id])
        return flattened

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            for chunk in self.all_chunks():
                handle.write(json.dumps(chunk.to_payload(), ensure_ascii=False))
                handle.write("\n")
        temp_path.replace(self.path)


@dataclass(frozen=True)
class RuntimeChunkSnapshot:
    chunks: tuple[RagChunk, ...]
    signature: str


class CachedRuntimeChunkStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()
        self._snapshot = RuntimeChunkSnapshot(chunks=(), signature="missing")

    def load(self) -> RuntimeChunkSnapshot:
        if not self.path.exists():
            with self._lock:
                self._snapshot = RuntimeChunkSnapshot(chunks=(), signature="missing")
                return self._snapshot

        stat = self.path.stat()
        signature = f"{stat.st_mtime_ns}:{stat.st_size}"
        with self._lock:
            if self._snapshot.signature == signature:
                return self._snapshot

            artifact = RuntimeChunkArtifact.load(self.path)
            self._snapshot = RuntimeChunkSnapshot(
                chunks=tuple(artifact.all_chunks()),
                signature=signature,
            )
            return self._snapshot


_CACHED_STORES: dict[str, CachedRuntimeChunkStore] = {}
_CACHED_STORES_LOCK = Lock()


def get_cached_runtime_chunk_store(path: Path) -> CachedRuntimeChunkStore:
    key = str(path.resolve())
    with _CACHED_STORES_LOCK:
        store = _CACHED_STORES.get(key)
        if store is None:
            store = CachedRuntimeChunkStore(path)
            _CACHED_STORES[key] = store
        return store
