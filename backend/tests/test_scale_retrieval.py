"""Scale profile: Qdrant/Redis ports work without making derived stores authoritative."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from app.retrieval import vector_notes
from app.retrieval.sync_vectors import _records
from app.storage import StoreDefinition
from app.storage.qdrant import QdrantDataStore


class _FakeQdrantClient:
    def __init__(self, **_kwargs):
        self.collections: set[str] = set()
        self.indexes: list[tuple[str, str]] = []
        self.upserts = []

    def collection_exists(self, collection: str) -> bool:
        return collection in self.collections

    def create_collection(self, collection_name: str, **_kwargs) -> None:
        self.collections.add(collection_name)

    def create_payload_index(self, collection_name: str, field_name: str, **_kwargs) -> None:
        self.indexes.append((collection_name, field_name))

    def upsert(self, **kwargs) -> None:
        self.upserts.append(kwargs)

    def query_points(self, **_kwargs):
        return SimpleNamespace(
            points=[
                SimpleNamespace(
                    id=1,
                    score=0.91,
                    payload={"note_id": 1, "owner_id": "C001", "ts": "2026-01-01", "channel": "rm", "text": "x"},
                )
            ]
        )

    def delete(self, **_kwargs) -> None:
        return None

    def get_collections(self) -> None:
        return None

    def close(self) -> None:
        return None


def test_qdrant_adapter_creates_owner_index_and_maps_query(monkeypatch):
    import qdrant_client

    fake = _FakeQdrantClient()
    monkeypatch.setattr(qdrant_client, "QdrantClient", lambda **_kwargs: fake)
    store = QdrantDataStore(StoreDefinition("notes", "qdrant", frozenset({"vector"}), dsn="http://qdrant.internal"))

    store.upsert("interaction_notes_v1", [{"id": 1, "vector": [0.1, 0.2], "metadata": {"owner_id": "C001"}}])
    matches = store.query("interaction_notes_v1", [0.1, 0.2], limit=5, filters={"owner_id": "C001"})

    assert fake.indexes == [("shb_interaction_notes_v1", "owner_id")]
    assert fake.upserts[0]["points"][0].id == 1
    assert matches[0].record_id == "1"
    assert matches[0].metadata["owner_id"] == "C001"


def test_vector_notes_uses_cache_after_first_index_query(monkeypatch):
    from roles._retrieval import functions as retrieval

    class Embedder:
        def encode(self, _inputs, **_kwargs):
            return np.array([[0.1, 0.2]], dtype=np.float32)

    class Cache:
        values: dict[str, bytes] = {}

        def get(self, key: str):
            return self.values.get(key)

        def set(self, key: str, value: bytes, *, ttl_seconds: int | None = None):
            assert ttl_seconds == 60
            self.values[key] = value

    class Vectors:
        calls = 0

        def query(self, *_args, **_kwargs):
            self.calls += 1
            return [
                SimpleNamespace(
                    score=0.876,
                    metadata={"note_id": 7, "owner_id": "C007", "ts": "2026-01-01", "channel": "rm", "text": "note"},
                )
            ]

    cache = Cache()
    vectors = Vectors()
    monkeypatch.setattr(retrieval, "_embedder", lambda: Embedder())
    monkeypatch.setattr(retrieval, "_now", lambda: "2026-01-01T00:00:00Z")
    monkeypatch.setattr(vector_notes, "key_value_capability", lambda: cache)
    monkeypatch.setattr(vector_notes, "vector_capability", lambda: vectors)

    first = vector_notes.search_notes_from_vector_index({"query": "cash flow", "owner_id": "C007", "limit": 5})
    second = vector_notes.search_notes_from_vector_index({"query": "cash flow", "owner_id": "C007", "limit": 5})

    assert first == second
    assert first is not None and first["results"][0]["note_id"] == 7
    assert vectors.calls == 1


def test_vector_backfill_records_preserve_note_citation_metadata():
    embedding = np.array([0.1, 0.2], dtype=np.float32).tobytes()

    records = _records([(12, "C012", "2026-01-02", "call", "cash-flow follow-up", embedding)])

    assert records == [
        {
            "id": 12,
            "vector": [0.10000000149011612, 0.20000000298023224],
            "metadata": {
                "note_id": 12,
                "owner_id": "C012",
                "ts": "2026-01-02",
                "channel": "call",
                "text": "cash-flow follow-up",
            },
        }
    ]
