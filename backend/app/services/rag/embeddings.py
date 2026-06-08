from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable


class EmbeddingAdapter(ABC):
    name = "base"

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class OpenAICompatibleEmbeddingAdapter(EmbeddingAdapter):
    name = "openai_compatible"

    def __init__(self, *, api_key: str, base_url: str, model: str, dimensions: int) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.dimensions = dimensions

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        from app.services.llm_client import get_openai_client

        client = get_openai_client(api_key=self.api_key, base_url=self.base_url, trace_enabled=False)
        response = await client.embeddings.create(model=self.model, input=texts)
        vectors = [item.embedding for item in response.data]
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self.dimensions}, got {len(vector)}"
                )
        return vectors


async def embed_in_batches(
    adapter: EmbeddingAdapter,
    texts: list[str],
    *,
    batch_size: int = 32,
    progress: Callable[[str], None] | None = None,
) -> list[list[float]]:
    vectors: list[list[float]] = []
    if batch_size <= 0:
        batch_size = len(texts) or 1
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        if progress:
            progress(f"batch {start // batch_size + 1} size={len(batch)}")
        vectors.extend(await adapter.embed_texts(batch))
    return vectors
