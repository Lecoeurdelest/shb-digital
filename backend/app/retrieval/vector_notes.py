"""Serve notes_search from the derived vector index when the scale profile is configured."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.storage import StoreConfigurationError, key_value_capability, vector_capability

log = logging.getLogger("app.retrieval.vector_notes")
_NAMESPACE = "interaction_notes_v1"
_CACHE_TTL_SECONDS = 60


def _limit(value: Any) -> int:
    try:
        return max(1, min(int(value or 5), 20))
    except (TypeError, ValueError):
        return 5


def _cache_key(query: str, owner_id: str | None, limit: int) -> str:
    payload = json.dumps([query, owner_id, limit], ensure_ascii=False, separators=(",", ":"))
    return f"notes-search:v1:{hashlib.sha256(payload.encode()).hexdigest()}"


def _cache_get(key: str) -> dict[str, Any] | None:
    try:
        value = key_value_capability().get(key)
        return json.loads(value) if value else None
    except (StoreConfigurationError, OSError, ValueError):
        return None


def _cache_set(key: str, payload: dict[str, Any]) -> None:
    try:
        key_value_capability().set(
            key,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(),
            ttl_seconds=_CACHE_TTL_SECONDS,
        )
    except (StoreConfigurationError, OSError, ValueError):
        # Cache không được biến truy hồi thành single point of failure.
        return


def search_notes_from_vector_index(args: dict[str, Any]) -> dict[str, Any] | None:
    """Trả None khi scale store chưa sẵn sàng để caller giữ nguyên LAB/PG fallback."""
    query = args.get("query")
    owner_id = args.get("owner_id")
    if not isinstance(query, str) or not query.strip() or (owner_id is not None and not isinstance(owner_id, str)):
        return None

    from roles._retrieval import functions as retrieval

    if retrieval.np is None:
        return None
    limit = _limit(args.get("limit"))
    key = _cache_key(query.strip(), owner_id, limit)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    try:
        # Không tải model embedding nếu scale profile chưa cấu hình Qdrant.
        store = vector_capability()
        from pyvi.ViTokenizer import tokenize

        vector = retrieval._embedder().encode([tokenize(query.strip())], normalize_embeddings=True)[0].tolist()
        matches = store.query(
            _NAMESPACE,
            vector,
            limit=limit,
            filters={"owner_id": owner_id} if owner_id else None,
        )
    except Exception as exc:  # noqa: BLE001 - index is derived; preserve the established PG fallback
        log.warning("vector notes retrieval unavailable exception=%s", type(exc).__name__)
        return None

    # Index chưa backfill đủ cũng quay về PG để không trả "không có" sai cho cán bộ.
    if not matches:
        return None
    result = {
        "found": True,
        "asOf": retrieval._now(),
        "scope": owner_id or "all",
        "results": [
            {
                "note_id": match.metadata["note_id"],
                "owner_id": match.metadata["owner_id"],
                "ts": match.metadata["ts"],
                "channel": match.metadata["channel"],
                "score": round(match.score, 3),
                "text": match.metadata["text"],
            }
            for match in matches
        ],
        "hint": "score = cosine; mọi trích dẫn ghi kèm note_id làm nguồn",
    }
    _cache_set(key, result)
    return result
