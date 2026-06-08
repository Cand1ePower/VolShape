from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services.rag.normalizer import normalize_text
from app.services.rag.types import RagDocument, RagSource, RagSourceType


def discover_markdown_sources(root: Path) -> list[RagSource]:
    sources: list[RagSource] = []
    for path in sorted(root.rglob("*.md")):
        source_type = _infer_source_type(path)
        source_id = _build_source_id(path, root)
        metadata_path = _find_mineru_metadata(path)
        original_path = _find_sibling(path, "_origin.pdf")
        layout_path = _find_sibling(path, "_layout.pdf")
        title = path.stem
        if source_type == RagSourceType.PERSONAL_NOTE:
            title = path.name.removesuffix(path.suffix)
        sources.append(
            RagSource(
                source_id=source_id,
                source_type=source_type,
                title=title,
                path=path,
                metadata_path=metadata_path,
                original_path=original_path,
                layout_path=layout_path,
                tags=_infer_tags(path),
            )
        )
    return sources


def load_markdown_documents(root: Path) -> tuple[list[RagDocument], list[str]]:
    documents: list[RagDocument] = []
    skipped: list[str] = []
    for source in discover_markdown_sources(root):
        document = load_markdown_document(source)
        if document is None:
            skipped.append(str(source.path))
            continue
        documents.append(document)
    return documents, skipped


def load_markdown_document(source: RagSource) -> RagDocument | None:
    raw_text = source.path.read_text(encoding="utf-8", errors="ignore")
    text = normalize_text(raw_text)
    if not text:
        return None
    metadata = _load_optional_mineru_metadata(source)
    return RagDocument(source=source, text=text, metadata=metadata)


def _infer_source_type(path: Path) -> RagSourceType:
    parts = {part.lower() for part in path.parts}
    if "physicalogical" in parts:
        return RagSourceType.PERSONAL_NOTE
    if any("nsca" in part.lower() or "cscs" in part.lower() for part in path.parts):
        return RagSourceType.TEXTBOOK
    return RagSourceType.UNKNOWN


def _build_source_id(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix().lower()
    digest = hashlib.sha1(relative.encode("utf-8")).hexdigest()[:10]
    slug = path.stem.lower()
    slug = "".join(ch if ch.isalnum() else "_" for ch in slug).strip("_")
    return f"{slug[:48]}_{digest}"


def _find_mineru_metadata(path: Path) -> Path | None:
    for suffix in ("_content_list_v2.json", "_content_list.json"):
        candidate = path.with_name(f"{path.stem}{suffix}")
        if candidate.exists():
            return candidate
    return None


def _find_sibling(path: Path, suffix: str) -> Path | None:
    candidate = path.with_name(f"{path.stem}{suffix}")
    return candidate if candidate.exists() else None


def _infer_tags(path: Path) -> tuple[str, ...]:
    tags: list[str] = []
    if path.parent.name:
        tags.append(path.parent.name)
    if path.stem:
        tags.append(path.stem)
    return tuple(tags)


def _load_optional_mineru_metadata(source: RagSource) -> dict:
    if not source.metadata_path:
        return {}
    try:
        data = json.loads(source.metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"metadata_error": str(source.metadata_path)}

    if isinstance(data, list):
        return {
            "mineru_blocks": len(data),
            "mineru_metadata_path": str(source.metadata_path),
        }
    return {
        "mineru_metadata_path": str(source.metadata_path),
        "mineru_metadata_type": type(data).__name__,
    }
