from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.services.rag.types import RagChunk, RagHit


class VectorStoreAdapter(ABC):
    name = "base"

    @abstractmethod
    def upsert_chunks(self, chunks: list[RagChunk], vectors: list[list[float]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, vector: list[float], *, top_k: int = 20, filters: dict | None = None) -> list[RagHit]:
        raise NotImplementedError

    @abstractmethod
    def delete_source(self, source_id: str) -> None:
        raise NotImplementedError


class QdrantVectorStore(VectorStoreAdapter):
    name = "qdrant"

    def __init__(self, *, collection_name: str, path: Path, vector_size: int) -> None:
        self.collection_name = collection_name
        self.path = path
        self.vector_size = vector_size

    def upsert_chunks(self, chunks: list[RagChunk], vectors: list[list[float]], *, batch_size: int = 64) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")

        from qdrant_client import QdrantClient
        from qdrant_client.http import models

        client = QdrantClient(path=str(self.path))
        try:
            self._ensure_collection(client)
            for start in range(0, len(chunks), max(1, batch_size)):
                points = [
                    models.PointStruct(
                        id=str(uuid5(NAMESPACE_URL, chunk.chunk_id)),
                        vector=vector,
                        payload=chunk.to_payload(),
                    )
                    for chunk, vector in zip(chunks[start : start + batch_size], vectors[start : start + batch_size])
                ]
                client.upsert(collection_name=self.collection_name, points=points)
        finally:
            _safe_close(client)

    def search(self, vector: list[float], *, top_k: int = 20, filters: dict | None = None) -> list[RagHit]:
        from qdrant_client import QdrantClient

        client = QdrantClient(path=str(self.path))
        try:
            self._ensure_collection(client)
            query_filter = self._build_filter(filters)

            if hasattr(client, "query_points"):
                response = client.query_points(
                    collection_name=self.collection_name,
                    query=vector,
                    limit=top_k,
                    query_filter=query_filter,
                )
                results = getattr(response, "points", None)
                if results is None and getattr(response, "result", None) is not None:
                    results = getattr(response.result, "points", None)
            elif hasattr(client, "search"):
                results = client.search(
                    collection_name=self.collection_name,
                    query_vector=vector,
                    limit=top_k,
                    query_filter=query_filter,
                )
            else:
                raise AttributeError("Qdrant client does not support search or query_points")

            hits: list[RagHit] = []
            for rank, point in enumerate(results or [], start=1):
                payload = dict(point.payload or {})
                chunk = RagChunk.from_payload(payload)
                hits.append(
                    RagHit(
                        chunk=chunk,
                        score=float(point.score or 0.0),
                        score_type="dense",
                        rank=rank,
                        source="dense",
                        metadata={"point_id": str(point.id)},
                    )
                )
            return hits
        finally:
            _safe_close(client)

    def delete_source(self, source_id: str) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models

        client = QdrantClient(path=str(self.path))
        try:
            self._ensure_collection(client)
            client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="source_id",
                                match=models.MatchValue(value=source_id),
                            )
                        ]
                    )
                ),
            )
        finally:
            _safe_close(client)

    def _ensure_collection(self, client) -> None:
        from qdrant_client.http import models

        existing = {collection.name for collection in client.get_collections().collections}
        if self.collection_name in existing:
            return
        client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    def _build_filter(self, filters: dict | None):
        if not filters:
            return None

        from qdrant_client.http import models

        must_conditions = []
        for key, value in filters.items():
            if value in (None, "", [], ()):
                continue
            if isinstance(value, (list, tuple, set)):
                should = [
                    models.FieldCondition(key=key, match=models.MatchValue(value=item))
                    for item in value
                ]
                must_conditions.append(models.Filter(should=should))
                continue
            must_conditions.append(
                models.FieldCondition(
                    key=key,
                    match=models.MatchValue(value=value),
                )
            )
        if not must_conditions:
            return None
        return models.Filter(must=must_conditions)


def _safe_close(client) -> None:
    close = getattr(client, "close", None)
    if not callable(close):
        return
    try:
        close()
    except Exception:
        pass
