"""Shadow-review ledger service (S18) — atomic insert seam + read-only aggregates.

Router không chứa SQL. ``insert_review`` nhận cursor do approval decide sở hữu để decision,
card sync và ledger cùng commit/rollback; hàm này tuyệt đối không mở conn hoặc commit riêng.
"""

from __future__ import annotations

import asyncio
from typing import Any

import psycopg2
import psycopg2.extras

from app.storage import connect_core

_DIRECTION: dict[str, str] = {
    "auto-eligible": "approved",
    "reject-recommended": "rejected",
}


def insert_review(cur: Any, approval_row: dict[str, Any]) -> None:
    """Ghi đúng một review bằng snapshot trên approval, trong transaction của caller.

    Row cũ/manual thiếu snapshot được ghi trung tính ``human-review`` để không bịa một dự đoán có
    hướng và không làm hỏng decide sau khi deploy migration giữa lúc còn phiếu pending.
    """
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
    """Admin API service wrapper; auth thuộc router."""
    return await asyncio.to_thread(_shadow_match_sync, tenant_id)
