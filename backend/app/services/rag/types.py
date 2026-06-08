from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

_RAG_CHUNK_CORE_FIELDS = {
    "chunk_id",
    "source_id",
    "source_type",
    "title",
    "heading_path",
    "chunk_type",
    "language",
    "topics",
    "page_start",
    "page_end",
    "token_estimate",
    "char_count",
    "text",
}


class RagSourceType(str, Enum):
    TEXTBOOK = "textbook"
    PERSONAL_NOTE = "personal_note"
    UNKNOWN = "unknown"


class RagChunkType(str, Enum):
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    NOTE = "note"
    HEADING_SUMMARY = "heading_summary"


class RagLanguage(str, Enum):
    ZH = "zh"
    EN = "en"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RagSource:
    source_id: str
    source_type: RagSourceType
    title: str
    path: Path
    metadata_path: Path | None = None
    original_path: Path | None = None
    layout_path: Path | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class RagDocument:
    source: RagSource
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RagChunk:
    chunk_id: str
    source_id: str
    source_type: RagSourceType
    title: str
    text: str
    heading_path: tuple[str, ...] = ()
    chunk_type: RagChunkType = RagChunkType.PARAGRAPH
    language: RagLanguage = RagLanguage.UNKNOWN
    topics: tuple[str, ...] = ()
    page_start: int | None = None
    page_end: int | None = None
    token_estimate: int = 0
    char_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "source_type": self.source_type.value,
            "title": self.title,
            "heading_path": list(self.heading_path),
            "chunk_type": self.chunk_type.value,
            "language": self.language.value,
            "topics": list(self.topics),
            "page_start": self.page_start,
            "page_end": self.page_end,
            "token_estimate": self.token_estimate,
            "char_count": self.char_count,
            "text": self.text,
            **self.metadata,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "RagChunk":
        metadata = {
            key: value
            for key, value in payload.items()
            if key not in _RAG_CHUNK_CORE_FIELDS
        }
        return cls(
            chunk_id=str(payload.get("chunk_id", "")),
            source_id=str(payload.get("source_id", "")),
            source_type=RagSourceType(str(payload.get("source_type", "unknown"))),
            title=str(payload.get("title", "")),
            text=str(payload.get("text", "")),
            heading_path=tuple(payload.get("heading_path", []) or ()),
            chunk_type=RagChunkType(str(payload.get("chunk_type", "paragraph"))),
            language=RagLanguage(str(payload.get("language", "unknown"))),
            topics=tuple(payload.get("topics", []) or ()),
            page_start=payload.get("page_start"),
            page_end=payload.get("page_end"),
            token_estimate=int(payload.get("token_estimate", 0) or 0),
            char_count=int(payload.get("char_count", 0) or 0),
            metadata=metadata,
        )


@dataclass(frozen=True)
class RagQuery:
    query: str
    intent: str | None = None
    topics: tuple[str, ...] = ()
    source_types: tuple[RagSourceType, ...] = ()
    top_k: int = 20
    dense_top_k: int | None = None
    bm25_top_k: int | None = None


@dataclass(frozen=True)
class RagHit:
    chunk: RagChunk
    score: float
    score_type: str
    rank: int
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RagContextPack:
    query: RagQuery
    hits: tuple[RagHit, ...]
    token_estimate: int

    def to_prompt_block(self) -> str:
        if not self.hits:
            return ""

        lines = ["[运动科学依据]"]
        for hit in self.hits:
            chunk = hit.chunk
            heading = " > ".join(chunk.heading_path) if chunk.heading_path else chunk.title
            page = ""
            if chunk.page_start:
                page = f" / p.{chunk.page_start}"
                if chunk.page_end and chunk.page_end != chunk.page_start:
                    page = f" / p.{chunk.page_start}-{chunk.page_end}"
            lines.extend(
                [
                    f"{hit.rank}. 来源: {chunk.title}{page}",
                    f"   位置: {heading}",
                    f"   片段: {chunk.text}",
                ]
            )
        lines.append("[运动科学依据结束]")
        return "\n".join(lines)


@dataclass(frozen=True)
class RagIngestPreview:
    source_count: int
    document_count: int
    chunk_count: int
    skipped_empty_sources: tuple[str, ...] = ()
    sample_chunks: tuple[RagChunk, ...] = ()


@dataclass(frozen=True)
class RagIngestResult:
    scanned_sources: int
    processed_sources: int
    skipped_sources: int
    deleted_sources: int
    embedded_chunks: int
    upserted_chunks: int
    collection_name: str
    manifest_path: str
    runtime_artifact_path: str
    skipped_source_ids: tuple[str, ...] = ()
    processed_source_ids: tuple[str, ...] = ()
    deleted_source_ids: tuple[str, ...] = ()
