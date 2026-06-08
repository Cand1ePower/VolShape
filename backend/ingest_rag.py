from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.rag.config import get_rag_settings
from app.services.rag.ingest import build_ingest_preview, ingest_sources


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline RAG ingestion for VolShape.")
    parser.add_argument("--source-root", default=None, help="Override source root. Defaults to ragdata.")
    parser.add_argument("--preview", action="store_true", help="Only scan and chunk; do not call embedding or Qdrant.")
    parser.add_argument("--sample-size", type=int, default=5, help="Preview sample chunk count.")
    parser.add_argument("--force", action="store_true", help="Reprocess even if manifest says unchanged.")
    parser.add_argument("--prune-missing", action="store_true", help="Delete indexed sources that are no longer present under source root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON result.")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    settings = get_rag_settings()
    source_root = Path(args.source_root) if args.source_root else settings.source_root

    if args.preview:
        preview = build_ingest_preview(source_root, settings, sample_size=args.sample_size)
        payload = {
            "mode": "preview",
            "source_count": preview.source_count,
            "document_count": preview.document_count,
            "chunk_count": preview.chunk_count,
            "skipped_empty_sources": list(preview.skipped_empty_sources),
            "sample_chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "title": chunk.title,
                    "heading_path": list(chunk.heading_path),
                    "char_count": chunk.char_count,
                    "topics": list(chunk.topics),
                    "language": chunk.language.value,
                }
                for chunk in preview.sample_chunks
            ],
        }
        _print_payload(payload, as_json=args.json)
        return 0

    result = await ingest_sources(
        source_root,
        settings,
        force=args.force,
        prune_missing=args.prune_missing,
        progress=_print_progress if not args.json else None,
    )
    payload = {
        "mode": "ingest",
        "scanned_sources": result.scanned_sources,
        "processed_sources": result.processed_sources,
        "skipped_sources": result.skipped_sources,
        "deleted_sources": result.deleted_sources,
        "embedded_chunks": result.embedded_chunks,
        "upserted_chunks": result.upserted_chunks,
        "collection_name": result.collection_name,
        "manifest_path": result.manifest_path,
        "runtime_artifact_path": result.runtime_artifact_path,
        "processed_source_ids": list(result.processed_source_ids),
        "skipped_source_ids": list(result.skipped_source_ids),
        "deleted_source_ids": list(result.deleted_source_ids),
    }
    _print_payload(payload, as_json=args.json)
    return 0


def _print_payload(payload: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    for key, value in payload.items():
        if isinstance(value, list):
            print(f"{key}: {len(value)} items")
            for item in value[:10]:
                print(f"  - {item}")
            if len(value) > 10:
                print(f"  ... {len(value) - 10} more")
        else:
            print(f"{key}: {value}")


def _print_progress(message: str) -> None:
    print(message, flush=True)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
