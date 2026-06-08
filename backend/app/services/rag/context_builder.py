from __future__ import annotations

from app.services.rag.types import RagContextPack, RagHit, RagQuery


def build_context_pack(query: RagQuery, hits: list[RagHit], *, top_k: int = 5, token_budget: int = 1800) -> RagContextPack:
    selected: list[RagHit] = []
    total_tokens = 0
    for hit in hits[:top_k]:
        next_total = total_tokens + hit.chunk.token_estimate
        if selected and next_total > token_budget:
            break
        selected.append(hit)
        total_tokens = next_total
    return RagContextPack(query=query, hits=tuple(selected), token_estimate=total_tokens)
