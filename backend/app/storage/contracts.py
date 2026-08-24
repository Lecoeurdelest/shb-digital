"""Small contracts shared by datastore adapters and the runtime registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


class StoreConfigurationError(ValueError):
    """Configuration is invalid; messages must not include credentials or DSNs."""


@dataclass(frozen=True)
class StoreDefinition:
    name: str
    driver: str
    capabilities: frozenset[str]
    required: bool = True
    dsn: str | None = field(default=None, repr=False)
    target: str | None = None
    options: dict[str, Any] = field(default_factory=dict, repr=False)


@runtime_checkable
class DataStore(Protocol):
    kind: str

    def healthcheck(self) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class ConnectionStore(DataStore, Protocol):
    def acquire(self) -> Any: ...

    def release(self, connection: Any) -> None: ...


@dataclass(frozen=True)
class VectorMatch:
    record_id: str
    score: float
    metadata: dict[str, Any]


@runtime_checkable
class VectorStore(DataStore, Protocol):
    """Port implemented by pgvector/Qdrant/OpenSearch adapters, never by business code."""

    def upsert(self, namespace: str, records: list[dict[str, Any]]) -> None: ...

    def query(
        self, namespace: str, vector: list[float], *, limit: int, filters: dict[str, Any] | None = None
    ) -> list[VectorMatch]: ...

    def delete(self, namespace: str, record_ids: list[str]) -> None: ...


@runtime_checkable
class KeyValueStore(DataStore, Protocol):
    """Port for optional distributed cache/coordination adapters such as Redis."""

    def get(self, key: str) -> bytes | None: ...

    def set(self, key: str, value: bytes, *, ttl_seconds: int | None = None) -> None: ...

    def delete(self, key: str) -> None: ...


class StoreFactory(Protocol):
    def __call__(self, definition: StoreDefinition) -> DataStore: ...
