from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg2
import psycopg2.extras

from app.config import JWT_SECRET
from app.storage import connect_core

_DIRECTION: dict[str, str] = {
    "auto-eligible": "approved",
    "reject-recommended": "rejected",
}


def insert_review(cur: Any, approval_row: dict[str, Any]) -> None:

    recommendation = approval_row.get("system_recommendation") or "human-review"
    human_decision = approval_row["status"]
    expected = _DIRECTION.get(recommendation)
    match = human_decision == expected if expected is not None else None
    cur.execute(
        "INSERT INTO shadow_reviews (tenant_id, approval_id, conv_id, system_lane, system_recommendation, "
        "human_decision, human_reason, decided_at, match) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            approval_row["tenant_id"],
            approval_row["id"],
            str(approval_row["conv_id"]),
            approval_row.get("system_lane"),
            recommendation,
            human_decision,
            approval_row.get("reason"),
            approval_row["decided_at"],
            match,
        ),
    )


def _counts(row: dict[str, Any]) -> dict[str, int | float]:
    total = int(row["total"])
    comparable = int(row["comparable"])
    matched = int(row["matched"])
    return {
        "total": total,
        "comparable": comparable,
        "matched": matched,
        "rate": matched / comparable if comparable else 0.0,
    }


_AGG = "count(*) AS total, count(match) AS comparable, count(*) FILTER (WHERE match IS TRUE) AS matched"

_CURSOR_VERSION = 1


class ShadowCursorError(ValueError):
    pass


def _utc_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _cursor_filters(
    tenant_id: str,
    from_at: datetime | None,
    to_at: datetime | None,
    lane: str | None,
) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "from": _utc_text(from_at),
        "to": _utc_text(to_at),
        "lane": lane,
    }


def _encode_cursor(
    *,
    tenant_id: str,
    from_at: datetime | None,
    to_at: datetime | None,
    lane: str | None,
    decided_at: datetime,
    approval_id: str,
) -> str:
    payload = {
        "v": _CURSOR_VERSION,
        "filters": _cursor_filters(tenant_id, from_at, to_at, lane),
        "after": {"decided_at": _utc_text(decided_at), "approval_id": approval_id},
    }
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = _b64encode(raw)
    signature = _b64encode(hmac.new(JWT_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def _decode_cursor(
    cursor: str,
    *,
    tenant_id: str,
    from_at: datetime | None,
    to_at: datetime | None,
    lane: str | None,
) -> tuple[datetime, str]:
    try:
        if not cursor or len(cursor) > 4096:
            raise ValueError("bad cursor length")
        body, signature = cursor.split(".", 1)
        expected = _b64encode(hmac.new(JWT_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad cursor signature")
        payload = json.loads(_b64decode(body))
        if not isinstance(payload, dict) or set(payload) != {"v", "filters", "after"}:
            raise ValueError("bad cursor payload")
        if payload["v"] != _CURSOR_VERSION or payload["filters"] != _cursor_filters(tenant_id, from_at, to_at, lane):
            raise ValueError("cursor context changed")
        after = payload["after"]
        if not isinstance(after, dict) or set(after) != {"decided_at", "approval_id"}:
            raise ValueError("bad cursor keyset")
        decided_at = datetime.fromisoformat(after["decided_at"])
        if decided_at.tzinfo is None:
            raise ValueError("cursor timestamp has no timezone")
        approval_id = str(UUID(after["approval_id"]))
    except (ValueError, TypeError, KeyError, binascii.Error, UnicodeError) as exc:
        raise ShadowCursorError("invalid shadow mismatch cursor") from exc
    return decided_at.astimezone(UTC), approval_id


def _shadow_match_sync(tenant_id: str | None = None) -> dict[str, Any]:
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            where = " WHERE tenant_id=%s" if tenant_id is not None else ""
            params = (tenant_id,) if tenant_id is not None else ()
            cur.execute(f"SELECT {_AGG} FROM shadow_reviews{where}", params)
            total = _counts(dict(cur.fetchone()))

            cur.execute(
                f"SELECT system_lane AS lane, {_AGG} FROM shadow_reviews{where} GROUP BY system_lane "
                "ORDER BY CASE system_lane WHEN 'green' THEN 1 WHEN 'yellow' THEN 2 "
                "WHEN 'red' THEN 3 ELSE 4 END",
                params,
            )
            by_lane = [{"lane": row["lane"], **_counts(dict(row))} for row in cur.fetchall()]

            cur.execute(
                f"SELECT (decided_at AT TIME ZONE 'UTC')::date AS day, {_AGG} "
                f"FROM shadow_reviews{where} GROUP BY day ORDER BY day",
                params,
            )
            by_day = [{"date": row["day"].isoformat(), **_counts(dict(row))} for row in cur.fetchall()]
    finally:
        conn.close()
    return {**total, "by_lane": by_lane, "by_day": by_day}


async def get_shadow_match(tenant_id: str | None = None) -> dict[str, Any]:

    return await asyncio.to_thread(_shadow_match_sync, tenant_id)


def _mismatches_sync(
    tenant_id: str,
    from_at: datetime | None,
    to_at: datetime | None,
    lane: str | None,
    limit: int,
    cursor: str | None,
) -> dict[str, Any]:
    after = (
        _decode_cursor(cursor, tenant_id=tenant_id, from_at=from_at, to_at=to_at, lane=lane)
        if cursor is not None
        else None
    )
    clauses = ["tenant_id=%s", "match IS FALSE"]
    params: list[Any] = [tenant_id]
    if from_at is not None:
        clauses.append("decided_at >= %s")
        params.append(from_at)
    if to_at is not None:
        clauses.append("decided_at < %s")
        params.append(to_at)
    if lane is not None:
        clauses.append("system_lane = %s")
        params.append(lane)
    if after is not None:
        clauses.append("(decided_at, approval_id) < (%s, %s::uuid)")
        params.extend(after)
    params.append(limit + 1)

    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT approval_id::text, conv_id, system_lane, system_recommendation, "
                "human_decision, human_reason, decided_at FROM shadow_reviews WHERE "
                + " AND ".join(clauses)
                + " ORDER BY decided_at DESC, approval_id DESC LIMIT %s",
                params,
            )
            rows = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [
        {
            "approval_id": row["approval_id"],
            "conv_id": str(row["conv_id"]),
            "system_lane": row["system_lane"],
            "system_recommendation": row["system_recommendation"],
            "human_decision": row["human_decision"],
            "human_reason": row["human_reason"],
            "decided_at": _utc_text(row["decided_at"]),
        }
        for row in page_rows
    ]
    next_cursor = None
    if has_more and page_rows:
        anchor = page_rows[-1]
        next_cursor = _encode_cursor(
            tenant_id=tenant_id,
            from_at=from_at,
            to_at=to_at,
            lane=lane,
            decided_at=anchor["decided_at"],
            approval_id=anchor["approval_id"],
        )
    return {"items": items, "next_cursor": next_cursor}


async def list_mismatches(
    tenant_id: str,
    *,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    lane: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Read-only keyset page of comparable disagreements for one JWT-owned tenant."""
    return await asyncio.to_thread(_mismatches_sync, tenant_id, from_at, to_at, lane, limit, cursor)
