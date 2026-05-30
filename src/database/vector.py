"""Qdrant vector store interface."""

from typing import Optional, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models


class VectorStore:
    """Vector similarity search via Qdrant."""

    def __init__(self, host: str = "localhost", port: int = 6333,
                 collection: str = "objective03", vector_size: int = 384):
        self.client = QdrantClient(host=host, port=port)
        self.collection = collection
        self.vector_size = vector_size
        self._ensure_collection()

    def _ensure_collection(self):
        collections = self.client.get_collections().collections
        existing = {c.name for c in collections}
        if self.collection not in existing:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE,
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                ),
            )

    def insert(self, point_id: str, vector: list[float], payload: Optional[dict] = None):
        self.client.upsert(
            collection_name=self.collection,
            points=[models.PointStruct(
                id=point_id,
                vector=vector,
                payload=payload or {},
            )],
        )

    def upsert_batch(self, points: list[dict]):
        self.client.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(
                    id=p["id"],
                    vector=p["vector"],
                    payload=p.get("payload", {}),
                )
                for p in points
            ],
        )

    def search(self, vector: list[float], top_k: int = 20,
               score_threshold: Optional[float] = None,
               filter_conditions: Optional[dict] = None) -> list[tuple[str, float]]:
        query_filter = None
        if filter_conditions:
            conditions = []
            for key, value in filter_conditions.items():
                if isinstance(value, dict):
                    if "gte" in value or "lte" in value:
                        conditions.append(models.FieldCondition(
                            key=key,
                            range=models.Range(
                                gte=value.get("gte"),
                                lte=value.get("lte"),
                            ),
                        ))
                else:
                    conditions.append(models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value),
                    ))
            if conditions:
                query_filter = models.Filter(must=conditions)

        results = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )
        return [(r.id, r.score) for r in results]

    def search_with_payload(self, vector: list[float], top_k: int = 20,
                             score_threshold: Optional[float] = None) -> list[dict]:
        results = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return [r.payload for r in results]

    def delete(self, point_id: str):
        self.client.delete(
            collection_name=self.collection,
            points_selector=models.PointIdsList(points=[point_id]),
        )

    def count(self) -> int:
        result = self.client.count(collection_name=self.collection)
        return result.count

    def close(self):
        self.client.close()
