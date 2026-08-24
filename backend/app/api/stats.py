"""Stats + assessments read API (T13-1) — dashboard số cho Control Tower (admin). ĐỌC-THUẦN.

RÀO §2: chỉ group-by bảng sẵn (approvals/assessments/conversations), KHÔNG bảng mới, KHÔNG
cost-USD/health. Timezone UTC nhất quán (data đang UTC): "today" = UTC day. psycopg2 + to_thread.
"""

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

# D-69: window ROLLING 24h|7d|30d (thay today|7d cũ). số giờ lùi từ now.
_WINDOWS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}
_ASSESS_LIMIT_MAX = 100


def _window_bounds(window: str) -> tuple[datetime, datetime, datetime]:
    """(start, prev_start, end) UTC — ROLLING (D-69): end=now; start=now-N giờ; prev_start=start-N
    (delta kỳ trước cùng độ dài). 24h|7d|30d = 24|168|720 giờ."""
    hours = _WINDOWS[window]
    now = datetime.now(UTC)
    start = now - timedelta(hours=hours)
    prev_start = start - timedelta(hours=hours)
    return start, prev_start, now


@router.get("/stats")
async def get_stats(window: str = Query("24h"), claims: dict = Depends(require_admin)) -> dict[str, Any]:
    """Dashboard counters for Control Tower (admin) — approvals/assessments/conversations by window.

    window=24h|7d|30d rolling (D-69, khác → 400). approvals theo decided_at (auto=decided_by='auto-rule'
    đếm riêng); pending = trạng thái HIỆN TẠI (không lọc window). assessments theo lane+created_at.
    conversations: total tạo trong window + active=status='running' hiện tại. delta = kỳ này − kỳ trước.
    sparks (D-70): mỗi KPI 1 mảng 24 số (24-bucket chuẩn hoá window) — FE KpiCard vẽ sparkline. DB rỗng → zeros."""
    if window not in _WINDOWS:
        raise ApiError(
            400, "bad_window", f"window '{window}' không hỗ trợ.", "Dùng window=24h|7d|30d.", retryable=False
        )
    import asyncio

    return await asyncio.to_thread(_stats_sync, window, tenant_id_from_claims(claims))


@router.get("/stats/shadow-match")
async def get_shadow_match(claims: dict = Depends(require_admin)) -> dict[str, Any]:
    """Độ khớp snapshot hệ thống ↔ quyết định người (admin, shape cố định CONTRACT §7b)."""
    return await store_shadow.get_shadow_match(tenant_id_from_claims(claims))


def _stats_sync(window: str, tenant_id: str | None = None) -> dict[str, Any]:
    start, prev_start, end = _window_bounds(window)
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # ── approvals theo window (decided_at). approved gồm 'used' (đã thực thi). auto riêng. ──
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
            # pending = trạng thái HIỆN TẠI (không lọc window — pending là snapshot hiện tại)
            cur.execute(
                f"SELECT count(*) AS pending FROM approvals WHERE status='pending'{tenant_and}",
                (tenant_id,) if tenant_id is not None else (),
            )
            pending = cur.fetchone()["pending"]

            # ── assessments theo lane, created_at TEXT → cast timestamptz (an toàn mọi format iso) ──
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

            # ── conversations: total tạo trong window + active=running hiện tại ──
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

            # ── delta: tổng kỳ này − tổng kỳ TRƯỚC cùng độ dài ──
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
    """D-70: 24-bucket ĐỀU cho mỗi KPI (approved/rejected/green/yellow/red/conversations). generate_series
    24 bucket (width=window/24) LEFT JOIN + COALESCE 0 → LUÔN đúng 24 số (rỗng → 24 số 0). Keyed theo tên KPI."""
    width = (end - start) / 24
    keys = ("approved", "rejected", "green", "yellow", "red", "conversations")
    out: dict[str, list[int]] = {k: [0] * 24 for k in keys}
    # 1 query/nhóm, bucket theo floor((ts-start)/width). Gom về Python list 24.
    # approvals (approved gồm used, rejected)
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
    """List assessment records (admin, read-only) for the AI-reasoning panel — newest first, cap 100.

    Filter owner optional. criteria_json parse → criteria[]; JSON hỏng → criteria=[] (row vẫn trả)."""
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
    """Parse criteria_json → criteria[] (hỏng → [] + log, row VẪN trả — panel không mất record)."""
    raw = row.get("criteria_json")
    try:
        criteria = json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        log.warning("assessment id=%s criteria_json hỏng → criteria=[]", row.get("id"))
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
