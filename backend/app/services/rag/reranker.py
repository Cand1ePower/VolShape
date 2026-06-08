from __future__ import annotations

from app.services.rag.types import RagHit, RagQuery


class ScoreFusionReranker:
    """Local first-pass reranker used before adding an external rerank API."""

    def rerank(self, query: RagQuery, hits: list[RagHit], *, top_k: int = 5) -> list[RagHit]:
        query_terms = _query_terms(query)
        scored: list[tuple[float, RagHit]] = []
        for hit in hits:
            title_text = hit.chunk.title.lower()
            heading_text = " ".join(hit.chunk.heading_path).lower()
            topic_boost = 0.15 if set(query.topics).intersection(hit.chunk.topics) else 0.0
            title_boost = sum(8.0 for term in query_terms if term and term in title_text)
            heading_boost = sum(1.5 for term in query_terms if term and term in heading_text)
            source_boost = 0.05 if hit.chunk.source_type in query.source_types else 0.0
            fused_score = hit.score + topic_boost + title_boost + heading_boost + source_boost
            scored.append((fused_score, hit))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RagHit(
                chunk=hit.chunk,
                score=score,
                score_type=f"{hit.score_type}+fusion_rerank",
                rank=rank,
                source=hit.source,
                metadata={**hit.metadata, "original_rank": hit.rank, "original_score": hit.score},
            )
            for rank, (score, hit) in enumerate(scored[:top_k], start=1)
        ]


def _query_terms(query: RagQuery) -> tuple[str, ...]:
    terms = [term.lower() for term in query.query.replace("/", " ").split() if len(term.strip()) >= 2]
    return tuple(terms)
