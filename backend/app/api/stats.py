from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, Query

from app.auth.deps import require_admin
from app.errors import ApiError
from app.orch import store_shadow
from app.storage import connect_core
from app.tenancy import tenant_id_from_claims

log = logging.getLogger("api.stats")

router = APIRouter(prefix="/api", tags=["stats"])


_WINDOWS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}
_ASSESS_LIMIT_MAX = 100


def _window_bounds(window: str) -> tuple[datetime, datetime, datetime]:

    hours = _WINDOWS[window]
    now = datetime.now(UTC)
    start = now - timedelta(hours=hours)
    prev_start = start - timedelta(hours=hours)
    return start, prev_start, now


@router.get("/stats")
async def get_stats(window: str = Query("24h"), claims: dict = Depends(require_admin)) -> dict[str, Any]:

    if window not in _WINDOWS:
        raise ApiError(
            400, "bad_window", f"window '{window}' is not supported.", "Use window=24h|7d|30d.", retryable=False
        )
    import asyncio

    return await asyncio.to_thread(_stats_sync, window, tenant_id_from_claims(claims))


@router.get("/stats/shadow-match")
async def get_shadow_match(claims: dict = Depends(require_admin)) -> dict[str, Any]:

    return await store_shadow.get_shadow_match(tenant_id_from_claims(claims))


def _shadow_time(value: str | None, field: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(
            400,
            "bad_shadow_filter",
            f"Query '{field}' must be an ISO-8601 timestamp with a timezone.",
            f"Use {field}=2026-08-24T00:00:00Z.",
            retryable=False,
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ApiError(
            400,
            "bad_shadow_filter",
            f"Query '{field}' is missing a timezone.",
            f"Use {field}=2026-08-24T00:00:00Z.",
            retryable=False,
        )
    return parsed.astimezone(UTC)


@router.get("/stats/shadow-match/mismatches")
async def get_shadow_mismatches(
    from_: str | None = Query(None, alias="from"),
    to_: str | None = Query(None, alias="to"),
    lane: str | None = Query(None),
    limit: str = Query("50"),
    cursor: str | None = Query(None),
    claims: dict = Depends(require_admin),
) -> dict[str, Any]:

    from_at, to_at = _shadow_time(from_, "from"), _shadow_time(to_, "to")
    if from_at is not None and to_at is not None and from_at >= to_at:
        raise ApiError(
            400,
            "bad_shadow_filter",
            "The shadow time range is invalid: 'from' must be earlier than 'to'.",
            "Use a half-open interval with inclusive 'from' and exclusive 'to'.",
            retryable=False,
        )
    if lane is not None and lane not in {"green", "yellow", "red"}:
        raise ApiError(
            400,
            "bad_shadow_filter",
            f"Lane '{lane}' is invalid.",
            "Use lane=green|yellow|red or omit this query parameter.",
            retryable=False,
        )
    try:
        page_limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise ApiError(
            400,
            "bad_shadow_filter",
            "Limit must be an integer.",
            "Use a limit from 1 to 200.",
            retryable=False,
        ) from exc
    if str(page_limit) != limit or not 1 <= page_limit <= 200:
        raise ApiError(
            400,
            "bad_shadow_filter",
            "Limit is out of range or not in canonical integer form.",
            "Use a limit from 1 to 200.",
            retryable=False,
        )
    try:
        return await store_shadow.list_mismatches(
            tenant_id_from_claims(claims),
            from_at=from_at,
            to_at=to_at,
            lane=lane,
            limit=page_limit,
            cursor=cursor,
        )
    except store_shadow.ShadowCursorError as exc:
        raise ApiError(
            400,
            "invalid_cursor",
            "The shadow cursor is invalid or does not belong to the current filter set.",
            "Reload the first page with the same filters.",
            retryable=False,
        ) from exc


def _stats_sync(window: str, tenant_id: str | None = None) -> dict[str, Any]:
    start, prev_start, end = _window_bounds(window)
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            tenant_and = " AND tenant_id=%s" if tenant_id is not None else ""
            cur.execute(
                "SELECT "
                "count(*) FILTER (WHERE status IN ('approved','used')) AS approved, "
                "count(*) FILTER (WHERE status='rejected') AS rejected, "
                "count(*) FILTER (WHERE decided_by='auto-rule') AS auto "
                f"FROM approvals WHERE decided_at >= %s AND decided_at < %s{tenant_and}",
                (start, end, tenant_id) if tenant_id is not None else (start, end),
            )
            appr = cur.fetchone()

            cur.execute(
                f"SELECT count(*) AS pending FROM approvals WHERE status='pending'{tenant_and}",
                (tenant_id,) if tenant_id is not None else (),
            )
            pending = cur.fetchone()["pending"]

            cur.execute(
                "SELECT "
                "count(*) FILTER (WHERE lane='green') AS green, "
                "count(*) FILTER (WHERE lane='yellow') AS yellow, "
                "count(*) FILTER (WHERE lane='red') AS red "
                f"FROM assessments WHERE created_at::timestamptz >= %s "
                f"AND created_at::timestamptz < %s{tenant_and}",
                (start, end, tenant_id) if tenant_id is not None else (start, end),
            )
            assess = cur.fetchone()

            cur.execute(
                f"SELECT count(*) AS total FROM conversations WHERE created_at >= %s AND created_at < %s{tenant_and}",
                (start, end, tenant_id) if tenant_id is not None else (start, end),
            )
            conv_total = cur.fetchone()["total"]
            cur.execute(
                f"SELECT count(*) AS active FROM conversations WHERE status='running'{tenant_and}",
                (tenant_id,) if tenant_id is not None else (),
            )
            conv_active = cur.fetchone()["active"]

            cur.execute(
                "SELECT count(*) FILTER (WHERE decided_at >= %s AND decided_at < %s) AS cur_appr, "
                "count(*) FILTER (WHERE decided_at >= %s AND decided_at < %s) AS prev_appr "
                f"FROM approvals{' WHERE tenant_id=%s' if tenant_id is not None else ''}",
                (start, end, prev_start, start, tenant_id)
                if tenant_id is not None
                else (start, end, prev_start, start),
            )
            d_appr = cur.fetchone()
            cur.execute(
                "SELECT "
                "count(*) FILTER (WHERE created_at::timestamptz >= %s AND created_at::timestamptz < %s) AS cur_ass, "
                "count(*) FILTER (WHERE created_at::timestamptz >= %s AND created_at::timestamptz < %s) AS prev_ass "
                f"FROM assessments{' WHERE tenant_id=%s' if tenant_id is not None else ''}",
                (start, end, prev_start, start, tenant_id)
                if tenant_id is not None
                else (start, end, prev_start, start),
            )
            d_ass = cur.fetchone()
            sparks = _sparks(cur, start, end, tenant_id)
    finally:
        conn.close()

    return {
        "window": window,
        "approvals": {
            "approved": appr["approved"],
            "rejected": appr["rejected"],
            "pending": pending,
            "auto": appr["auto"],
        },
        "assessments": {"green": assess["green"], "yellow": assess["yellow"], "red": assess["red"]},
        "conversations": {"total": conv_total, "active": conv_active},
        "delta": {
            "approvals_total": d_appr["cur_appr"] - d_appr["prev_appr"],
            "assessments_total": d_ass["cur_ass"] - d_ass["prev_ass"],
        },
        "sparks": sparks,  # D-70: {<kpiKey>: number[24]} — KpiCard optional sparkline
    }


def _sparks(cur: Any, start: datetime, end: datetime, tenant_id: str | None = None) -> dict[str, list[int]]:

    width = (end - start) / 24
    keys = ("approved", "rejected", "green", "yellow", "red", "conversations")
    out: dict[str, list[int]] = {k: [0] * 24 for k in keys}

    cur.execute(
        "SELECT floor(extract(epoch FROM (decided_at - %s)) / extract(epoch FROM %s::interval))::int AS b, "
        "count(*) FILTER (WHERE status IN ('approved','used')) AS approved, "
        "count(*) FILTER (WHERE status='rejected') AS rejected "
        "FROM approvals WHERE decided_at >= %s AND decided_at < %s"
        + (" AND tenant_id=%s" if tenant_id is not None else "")
        + " GROUP BY b",
        (start, width, start, end, tenant_id) if tenant_id is not None else (start, width, start, end),
    )
    for r in cur.fetchall():
        b = r["b"]
        if 0 <= b < 24:
            out["approved"][b] = r["approved"]
            out["rejected"][b] = r["rejected"]
    # assessments (green/yellow/red)
    cur.execute(
        "SELECT floor(extract(epoch FROM (created_at::timestamptz - %s)) "
        "/ extract(epoch FROM %s::interval))::int AS b, "
        "count(*) FILTER (WHERE lane='green') AS green, count(*) FILTER (WHERE lane='yellow') AS yellow, "
        "count(*) FILTER (WHERE lane='red') AS red "
        "FROM assessments WHERE created_at::timestamptz >= %s AND created_at::timestamptz < %s"
        + (" AND tenant_id=%s" if tenant_id is not None else "")
        + " GROUP BY b",
        (start, width, start, end, tenant_id) if tenant_id is not None else (start, width, start, end),
    )
    for r in cur.fetchall():
        b = r["b"]
        if 0 <= b < 24:
            out["green"][b], out["yellow"][b], out["red"][b] = r["green"], r["yellow"], r["red"]
    # conversations total
    cur.execute(
        "SELECT floor(extract(epoch FROM (created_at - %s)) / extract(epoch FROM %s::interval))::int AS b, "
        "count(*) AS total FROM conversations WHERE created_at >= %s AND created_at < %s"
        + (" AND tenant_id=%s" if tenant_id is not None else "")
        + " GROUP BY b",
        (start, width, start, end, tenant_id) if tenant_id is not None else (start, width, start, end),
    )
    for r in cur.fetchall():
        b = r["b"]
        if 0 <= b < 24:
            out["conversations"][b] = r["total"]
    return out


@router.get("/assessments")
async def list_assessments(
    owner: str | None = Query(None),
    limit: int = Query(50, ge=1, le=_ASSESS_LIMIT_MAX),
    claims: dict = Depends(require_admin),
) -> list[dict[str, Any]]:

    import asyncio

    return await asyncio.to_thread(_assessments_sync, owner, limit, tenant_id_from_claims(claims))


def _assessments_sync(owner: str | None, limit: int, tenant_id: str | None = None) -> list[dict[str, Any]]:
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if owner:
                tenant_clause = " AND tenant_id=%s" if tenant_id is not None else ""
                params = (owner, tenant_id, limit) if tenant_id is not None else (owner, limit)
                cur.execute(
                    "SELECT id, owner_id, loan_type, loan_amount_vnd, lane, criteria_json, basis, created_at "
                    f"FROM assessments WHERE owner_id=%s{tenant_clause} ORDER BY created_at DESC, id DESC LIMIT %s",
                    params,
                )
            else:
                tenant_where = " WHERE tenant_id=%s" if tenant_id is not None else ""
                params = (tenant_id, limit) if tenant_id is not None else (limit,)
                cur.execute(
                    "SELECT id, owner_id, loan_type, loan_amount_vnd, lane, criteria_json, basis, created_at "
                    f"FROM assessments{tenant_where} ORDER BY created_at DESC, id DESC LIMIT %s",
                    params,
                )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [_assessment_to_dict(r) for r in rows]


def _assessment_to_dict(row: dict[str, Any]) -> dict[str, Any]:

    raw = row.get("criteria_json")
    try:
        criteria = json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        log.warning("assessment id=%s has invalid criteria_json; using criteria=[]", row.get("id"))
        criteria = []
    return {
        "id": row["id"],
        "owner_id": row["owner_id"],
        "loan_type": row["loan_type"],
        "loan_amount_vnd": row["loan_amount_vnd"],
        "lane": row["lane"],
        "criteria": criteria,
        "basis": row["basis"],
        "created_at": row["created_at"],
    }
