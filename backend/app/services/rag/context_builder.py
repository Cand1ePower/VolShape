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


def build_source_labels(hits: list[RagHit], *, limit: int = 3) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()

    for hit in hits:
        chunk = hit.chunk
        title = (chunk.title or "").strip()
        headings = [part.strip() for part in chunk.heading_path if part and part.strip()]
        trailing_heading = ""
        if headings:
            tail = headings[-2:] if len(headings) > 1 else headings[-1:]
            trailing_heading = " > ".join(tail).strip()
            if trailing_heading == title:
                trailing_heading = ""

        page = ""
        if chunk.page_start:
            page = f" (p.{chunk.page_start})"
            if chunk.page_end and chunk.page_end != chunk.page_start:
                page = f" (p.{chunk.page_start}-{chunk.page_end})"

        label = title or "未命名来源"
        if trailing_heading:
            label = f"{label} · {trailing_heading}"
        label = f"{label}{page}"

        if label in seen:
            continue
        seen.add(label)
        labels.append(label)
        if len(labels) >= limit:
            break

    return labels
