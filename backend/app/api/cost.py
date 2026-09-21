from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, Query

from app.auth.deps import require_admin
from app.errors import ApiError
from app.storage import connect_core
from app.tenancy import tenant_id_from_claims

log = logging.getLogger("api.cost")

router = APIRouter(prefix="/api/stats", tags=["cost"])


_WINDOW_HOURS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}
_Z_THRESHOLD = 2.0


# %(start)s/%(end)s bind window. messages jsonb: meta->'metrics'->>'x' → numeric cast.
_UNIFIED_CTE = """
WITH unified AS (
    SELECT conv_id, role, model,
           (cost->>'cost_usd')::numeric AS cost_usd,
           input_tokens, output_tokens, cache_read_tokens, cache_create_tokens
    FROM tasks
    WHERE cost->>'cost_usd' IS NOT NULL AND ended_at >= %(start)s AND ended_at < %(end)s
      AND (%(tenant_id)s IS NULL OR tenant_id=%(tenant_id)s::uuid)
    UNION ALL
    SELECT conv_id, 'main' AS role, meta->'metrics'->>'model' AS model,
           (meta->'metrics'->>'cost_usd')::numeric AS cost_usd,
           (meta->'metrics'->>'input_tokens')::bigint,
           (meta->'metrics'->>'output_tokens')::bigint,
           (meta->'metrics'->>'cache_read_tokens')::bigint,
           (meta->'metrics'->>'cache_create_tokens')::bigint
    FROM messages
    WHERE sender='assistant' AND meta->'metrics'->>'cost_usd' IS NOT NULL
      AND ts >= %(start)s AND ts < %(end)s
      AND (%(tenant_id)s IS NULL OR tenant_id=%(tenant_id)s::uuid)
)
"""


def _bounds(window: str) -> tuple[datetime, datetime, datetime]:

    hours = _WINDOW_HOURS[window]
    now = datetime.now(UTC)
    start = now - timedelta(hours=hours)
    prev_start = start - timedelta(hours=hours)
    return start, prev_start, now


@router.get("/cost")
async def get_cost(window: str = Query("24h"), claims: dict = Depends(require_admin)) -> dict[str, Any]:

    if window not in _WINDOW_HOURS:
        raise ApiError(400, "bad_window", f"window '{window}' is not supported.", "Use 24h|7d|30d.", retryable=False)
    import asyncio

    return await asyncio.to_thread(_cost_sync, window, tenant_id_from_claims(claims))


def _cost_sync(window: str, tenant_id: str | None = None) -> dict[str, Any]:
    start, prev_start, end = _bounds(window)
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            p = {"start": start, "end": end, "tenant_id": tenant_id}
            # total + breakdown 4-token
            cur.execute(
                _UNIFIED_CTE + "SELECT COALESCE(SUM(cost_usd),0) AS total, "
                "COALESCE(SUM(input_tokens),0) AS input_tokens, COALESCE(SUM(output_tokens),0) AS output_tokens, "
                "COALESCE(SUM(cache_read_tokens),0) AS cache_read_tokens, "
                "COALESCE(SUM(cache_create_tokens),0) AS cache_create_tokens FROM unified",
                p,
            )
            tot = cur.fetchone()
            # by_model
            cur.execute(
                _UNIFIED_CTE + "SELECT model, SUM(cost_usd) AS cost_usd, count(*) AS turns, "
                "COALESCE(SUM(input_tokens+output_tokens+cache_read_tokens+cache_create_tokens),0) AS total_tokens "
                "FROM unified WHERE model IS NOT NULL GROUP BY model ORDER BY cost_usd DESC",
                p,
            )
            by_model = [
                {
                    "model": r["model"],
                    "cost_usd": float(r["cost_usd"] or 0),
                    "turns": r["turns"],
                    "total_tokens": int(r["total_tokens"] or 0),
                }
                for r in cur.fetchall()
            ]
            # by_role
            cur.execute(
                _UNIFIED_CTE + "SELECT role, SUM(cost_usd) AS cost_usd, count(*) AS turns "
                "FROM unified GROUP BY role ORDER BY cost_usd DESC",
                p,
            )
            by_role = [
                {"role": r["role"], "cost_usd": float(r["cost_usd"] or 0), "turns": r["turns"]} for r in cur.fetchall()
            ]
            # anomalies: agg cost/conv → mean+STDDEV_SAMP → z=(c-mean)/stddev (guard stddev=0/n<2), z≥2
            cur.execute(
                _UNIFIED_CTE
                + """,
                per_conv AS (SELECT conv_id, SUM(cost_usd) AS c FROM unified GROUP BY conv_id),
                stats AS (SELECT AVG(c) AS mean, STDDEV_SAMP(c) AS sd, count(*) AS n FROM per_conv)
                SELECT pc.conv_id, pc.c AS cost_usd, s.mean, s.sd,
                       CASE WHEN s.sd > 0 THEN (pc.c - s.mean) / s.sd ELSE 0 END AS z_score
                FROM per_conv pc CROSS JOIN stats s
                WHERE s.n >= 2 AND s.sd > 0 AND (pc.c - s.mean) / s.sd >= %(z)s
                ORDER BY z_score DESC""",
                {**p, "z": _Z_THRESHOLD},
            )
            anomalies = [
                {
                    "conv_id": r["conv_id"],
                    "title": _conv_title(cur, r["conv_id"], tenant_id),
                    "cost_usd": float(r["cost_usd"] or 0),
                    "mean": float(r["mean"] or 0),
                    "stddev": float(r["sd"] or 0),
                    "z_score": round(float(r["z_score"] or 0), 3),
                }
                for r in cur.fetchall()
            ]

            cur.execute(
                """SELECT
                   COALESCE(SUM(cost_usd) FILTER (WHERE t >= %(start)s AND t < %(end)s),0) AS cur,
                   COALESCE(SUM(cost_usd) FILTER (WHERE t >= %(prev)s AND t < %(start)s),0) AS prev
                   FROM (
                     SELECT (cost->>'cost_usd')::numeric AS cost_usd, ended_at AS t FROM tasks
                       WHERE cost->>'cost_usd' IS NOT NULL AND ended_at >= %(prev)s AND ended_at < %(end)s
                         AND (%(tenant_id)s IS NULL OR tenant_id=%(tenant_id)s::uuid)
                     UNION ALL
                     SELECT (meta->'metrics'->>'cost_usd')::numeric, ts FROM messages
                       WHERE sender='assistant' AND meta->'metrics'->>'cost_usd' IS NOT NULL
                         AND ts >= %(prev)s AND ts < %(end)s
                         AND (%(tenant_id)s IS NULL OR tenant_id=%(tenant_id)s::uuid)
                   ) u""",
                {"start": start, "end": end, "prev": prev_start, "tenant_id": tenant_id},
            )
            d = cur.fetchone()
    finally:
        conn.close()

    cur_c, prev_c = float(d["cur"] or 0), float(d["prev"] or 0)
    delta_pct = None if prev_c == 0 else round((cur_c - prev_c) / prev_c * 100, 1)
    return {
        "window": window,
        "total_cost_usd": float(tot["total"] or 0),
        "cost_estimated": True,
        "breakdown": {
            "input_tokens": int(tot["input_tokens"] or 0),
            "output_tokens": int(tot["output_tokens"] or 0),
            "cache_read_tokens": int(tot["cache_read_tokens"] or 0),
            "cache_create_tokens": int(tot["cache_create_tokens"] or 0),
        },
        "by_model": by_model,
        "by_role": by_role,
        "anomalies": anomalies,
        "delta": {"total_cost_pct": delta_pct},
    }


def _conv_title(cur: Any, conv_id: str, tenant_id: str | None = None) -> str | None:
    tenant_clause = " AND tenant_id=%s" if tenant_id is not None else ""
    params = (conv_id, tenant_id) if tenant_id is not None else (conv_id,)
    cur.execute(f"SELECT title FROM conversations WHERE id::text=%s{tenant_clause}", params)
    r = cur.fetchone()
    return r["title"] if r else None


@router.get("/cost-trend")
async def get_cost_trend(
    window: str = Query("7d"),
    bucket: str = Query("day"),
    group_by: str = Query("model"),
    claims: dict = Depends(require_admin),
) -> dict[str, Any]:

    if window not in _WINDOW_HOURS:
        raise ApiError(400, "bad_window", f"window '{window}' is not supported.", "Use 24h|7d|30d.", retryable=False)
    if bucket not in ("hour", "day"):
        raise ApiError(400, "bad_bucket", f"bucket '{bucket}' is not supported.", "Use hour|day.", retryable=False)
    if group_by not in ("model", "role"):
        raise ApiError(
            400, "bad_group_by", f"group_by '{group_by}' is not supported.", "Use model|role.", retryable=False
        )
    import asyncio

    return await asyncio.to_thread(
        _cost_trend_sync,
        window,
        bucket,
        group_by,
        tenant_id_from_claims(claims),
    )


_TREND_CTE = """
WITH unified AS (
    SELECT role, model, (cost->>'cost_usd')::numeric AS cost_usd, ended_at AS ts
    FROM tasks WHERE cost->>'cost_usd' IS NOT NULL AND ended_at >= %(start)s AND ended_at < %(end)s
      AND (%(tenant_id)s IS NULL OR tenant_id=%(tenant_id)s::uuid)
    UNION ALL
    SELECT 'main' AS role, meta->'metrics'->>'model' AS model,
           (meta->'metrics'->>'cost_usd')::numeric AS cost_usd, ts
    FROM messages WHERE sender='assistant' AND meta->'metrics'->>'cost_usd' IS NOT NULL
      AND ts >= %(start)s AND ts < %(end)s
      AND (%(tenant_id)s IS NULL OR tenant_id=%(tenant_id)s::uuid)
)
"""


def _cost_trend_sync(
    window: str,
    bucket: str,
    group_by: str,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    start, _, end = _bounds(window)
    grp = "model" if group_by == "model" else "role"
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                _TREND_CTE + f"SELECT date_trunc(%(bucket)s, ts) AS b, COALESCE({grp}, 'unknown') AS name, "  # noqa: S608
                "SUM(cost_usd) AS cost FROM unified GROUP BY b, name ORDER BY b",
                {"start": start, "end": end, "bucket": bucket, "tenant_id": tenant_id},
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    # pivot long → {ts, series:{name:cost}}
    buckets: dict[str, dict[str, float]] = {}
    for r in rows:
        ts_iso = r["b"].isoformat()
        buckets.setdefault(ts_iso, {})[r["name"]] = float(r["cost"] or 0)
    return {"buckets": [{"ts": ts, "series": s} for ts, s in sorted(buckets.items())]}
