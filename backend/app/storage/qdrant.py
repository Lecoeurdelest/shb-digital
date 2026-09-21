"""Qdrant adapter for derived vector indexes; PostgreSQL remains authoritative."""

from __future__ import annotations

import re
from typing import Any

from app.storage.contracts import StoreConfigurationError, StoreDefinition, VectorMatch

_NAME_RE = re.compile(r"[^a-zA-Z0-9_]+")


class QdrantDataStore:
    kind = "qdrant"

    def __init__(self, definition: StoreDefinition) -> None:
        if not definition.dsn:
            raise StoreConfigurationError(f"store {definition.name!r} has no configured DSN")
        try:
            from qdrant_client import QdrantClient, models
        except ImportError as exc:  # pragma: no cover - package is a runtime dependency
            raise StoreConfigurationError("Qdrant adapter dependency is not installed") from exc
        self.definition = definition
        self._models = models
        self._prefix = str(definition.options.get("collection_prefix", "shb_"))
        timeout = float(definition.options.get("timeout_seconds", 3))

        self._client: Any = (
            QdrantClient(location=definition.dsn, timeout=timeout)
            if definition.dsn == ":memory:"
            else QdrantClient(url=definition.dsn, timeout=timeout)
        )

    def _collection(self, namespace: str) -> str:
        normalized = _NAME_RE.sub("_", namespace).strip("_")
        if not normalized:
            raise StoreConfigurationError("vector namespace cannot be empty")
        return f"{self._prefix}{normalized}"

    def _ensure_collection(self, collection: str, dimension: int) -> None:
        if self._client.collection_exists(collection):
            return
        self._client.create_collection(
            collection_name=collection,
            vectors_config=self._models.VectorParams(size=dimension, distance=self._models.Distance.COSINE),
        )

        self._client.create_payload_index(
            collection_name=collection,
            field_name="owner_id",
            field_schema=self._models.PayloadSchemaType.KEYWORD,
        )

    def upsert(self, namespace: str, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        first_vector = records[0].get("vector")
        if not isinstance(first_vector, list) or not first_vector:
            raise StoreConfigurationError("vector records need a non-empty vector list")
        dimension = len(first_vector)
        points = []
        for record in records:
            record_id = record.get("id")
            vector = record.get("vector")
            metadata = record.get("metadata", {})
            if not isinstance(record_id, (str, int)) or not isinstance(vector, list) or len(vector) != dimension:
                raise StoreConfigurationError("vector records need stable IDs and equal dimensions")
            if not isinstance(metadata, dict):
                raise StoreConfigurationError("vector record metadata must be an object")
            points.append(self._models.PointStruct(id=record_id, vector=vector, payload=metadata))
        collection = self._collection(namespace)
        self._ensure_collection(collection, dimension)
        self._client.upsert(collection_name=collection, points=points, wait=True)

    def query(
        self, namespace: str, vector: list[float], *, limit: int, filters: dict[str, Any] | None = None
    ) -> list[VectorMatch]:
        if not vector:
            return []
        conditions = []
        for key, value in (filters or {}).items():
            conditions.append(self._models.FieldCondition(key=key, match=self._models.MatchValue(value=value)))
        response = self._client.query_points(
            collection_name=self._collection(namespace),
            query=vector,
            query_filter=self._models.Filter(must=conditions) if conditions else None,
            limit=max(1, min(limit, 20)),
            with_payload=True,
            with_vectors=False,
        )
        return [
            VectorMatch(record_id=str(point.id), score=float(point.score), metadata=dict(point.payload or {}))
            for point in response.points
        ]

    def delete(self, namespace: str, record_ids: list[str]) -> None:
        if record_ids:
            self._client.delete(
                collection_name=self._collection(namespace),
                points_selector=self._models.PointIdsList(points=record_ids),
                wait=True,
            )

    def healthcheck(self) -> None:
        self._client.get_collections()

    def close(self) -> None:
        self._client.close()
