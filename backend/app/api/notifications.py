from __future__ import annotations

import logging
from typing import Any

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends

from app.auth.deps import require_user
from app.storage import connect_core
from app.tenancy import tenant_id_from_claims

log = logging.getLogger("api.notifications")

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

_LIMIT = 20


@router.get("")
async def list_notifications(claims: dict = Depends(require_user)) -> list[dict[str, Any]]:

    username = claims.get("username")
    if not username:
        return []
    import asyncio

    return await asyncio.to_thread(_derive, username, tenant_id_from_claims(claims))


def _derive(username: str, tenant_id: str | None = None) -> list[dict[str, Any]]:

    try:
        conn = connect_core()
    except psycopg2.Error as e:
        log.warning("notifications database error (returning empty result): %s", e)
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT a.conv_id, a.action, a.status, a.payload, a.receipt, "
                "COALESCE(a.used_at, a.decided_at) AS ts "
                "FROM approvals a JOIN conversations c ON a.conv_id = c.id::text "
                "WHERE c.user_id = %s AND (%s IS NULL OR c.tenant_id=%s::uuid) "
                "AND a.status IN ('used', 'approved', 'rejected') "
                "ORDER BY ts DESC NULLS LAST LIMIT %s",
                (username, tenant_id, tenant_id, _LIMIT),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [_to_event(r) for r in rows]


def _to_event(row: dict[str, Any]) -> dict[str, Any]:

    status = row["status"]
    payload = row.get("payload") or {}
    amount = payload.get("amount")
    amount_str = f" ({int(float(amount)):,} VND)" if amount else ""
    if status == "used" and row.get("receipt"):
        etype, title = "disbursed", f"Disbursement completed{amount_str}"
    elif status == "rejected":
        etype, title = "approval_decided", f"Request rejected{amount_str}"
    else:
        etype, title = "approval_decided", f"Request approved{amount_str}"
    ts = row.get("ts")
    return {"type": etype, "title": title, "ts": ts.isoformat() if ts else None, "conv_id": row["conv_id"]}
