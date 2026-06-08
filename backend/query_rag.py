from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.rag.config import get_rag_settings
from app.services.rag.knowledge_base import RuntimeKnowledgeBase
from app.services.rag.types import RagQuery, RagSourceType


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query VolShape RAG with dense + BM25 hybrid retrieval.")
    parser.add_argument("query", help="Natural-language query.")
    parser.add_argument("--runtime-artifact", default=None, help="Override runtime chunk artifact. Defaults to data/rag_runtime_chunks.jsonl.")
    parser.add_argument("--top-k", type=int, default=5, help="Final context chunk count.")
    parser.add_argument("--dense-top-k", type=int, default=None, help="Dense retrieval candidate size.")
    parser.add_argument("--bm25-top-k", type=int, default=None, help="BM25 retrieval candidate size.")
    parser.add_argument(
        "--source-type",
        action="append",
        choices=[source_type.value for source_type in RagSourceType if source_type != RagSourceType.UNKNOWN],
        default=[],
        help="Restrict retrieval to selected source types. Can be repeated.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    settings = get_rag_settings()
    if args.top_k > 0:
        settings = settings.__class__(**{**settings.__dict__, "context_top_k": args.top_k})
    if args.runtime_artifact:
        settings = settings.__class__(**{**settings.__dict__, "runtime_artifact_path": Path(args.runtime_artifact)})

    retriever = RuntimeKnowledgeBase(settings=settings)
    query = RagQuery(
        query=args.query,
        source_types=tuple(RagSourceType(source_type) for source_type in args.source_type),
        dense_top_k=args.dense_top_k,
        bm25_top_k=args.bm25_top_k,
    )
    pack = await retriever.retrieve(query)
    payload = {
        "query": args.query,
        "runtime_artifact_path": str(settings.runtime_artifact_path),
        "token_estimate": pack.token_estimate,
        "hits": [
            {
                "rank": hit.rank,
                "score": hit.score,
                "score_type": hit.score_type,
                "source": hit.source,
                "title": hit.chunk.title,
                "source_id": hit.chunk.source_id,
                "source_type": hit.chunk.source_type.value,
                "heading_path": list(hit.chunk.heading_path),
                "topics": list(hit.chunk.topics),
                "preview": hit.chunk.text[:220],
                "metadata": hit.metadata,
            }
            for hit in pack.hits
        ],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"query: {payload['query']}")
        print(f"token_estimate: {payload['token_estimate']}")
        print(f"hits: {len(payload['hits'])}")
        for hit in payload["hits"]:
            print(f"{hit['rank']}. [{hit['source']}] {hit['title']} :: {' > '.join(hit['heading_path'])}")
            print(f"   score={hit['score']:.4f} type={hit['score_type']} topics={','.join(hit['topics'])}")
            print(f"   preview={hit['preview']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
