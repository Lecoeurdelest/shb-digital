"""Notifications (T9-2) — GET /api/notifications: bell khách. KHÔNG bảng mới — DERIVE từ approvals
⋈ conversations của CHÍNH mình. Khách thấy sự kiện ca mình: khoản duyệt/từ chối + giải ngân.

status='used' + receipt → 'disbursed' (giải ngân xong); status IN (rejected) → 'approval_decided'
từ chối; status='used' cũng ngụ ý đã duyệt. Mỗi phiếu → 1 dòng sự kiện MỚI NHẤT (decided_at desc).
Admin gọi → ca mình tạo (như customer — Control Tower có queue riêng, notifications = view cá nhân).
"""

from __future__ import annotations

import logging
from typing import Any

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends

from app.auth.deps import require_user
from app.db.config import DATABASE_URL

log = logging.getLogger("api.notifications")

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

_LIMIT = 20


@router.get("")
async def list_notifications(claims: dict = Depends(require_user)) -> list[dict[str, Any]]:
    """List the caller's own notifications (approval-decided / disbursed), newest first, cap 20.

    Sự kiện ca của CHÍNH mình (JOIN conversations.user_id = username), mới nhất trước, cap 20.
    Ca 0 sự kiện → [] (không 404). Derive — không bảng notifications riêng."""
    username = claims.get("username")
    if not username:
        return []
    import asyncio

    return await asyncio.to_thread(_derive, username)


def _derive(username: str) -> list[dict[str, Any]]:
    """SELECT approvals đã quyết JOIN conversations của user → list sự kiện. Best-effort (DB lỗi → [])."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
    except psycopg2.Error as e:
        log.warning("notifications DB lỗi (trả rỗng): %s", e)
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT a.conv_id, a.action, a.status, a.payload, a.receipt, "
                "COALESCE(a.used_at, a.decided_at) AS ts "
                "FROM approvals a JOIN conversations c ON a.conv_id = c.id::text "
                "WHERE c.user_id = %s AND a.status IN ('used', 'approved', 'rejected') "
                "ORDER BY ts DESC NULLS LAST LIMIT %s",
                (username, _LIMIT),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [_to_event(r) for r in rows]


def _to_event(row: dict[str, Any]) -> dict[str, Any]:
    """1 approval row → {type, title, ts, conv_id}. used+receipt=disbursed; rejected=từ chối."""
    status = row["status"]
    payload = row.get("payload") or {}
    amount = payload.get("amount")
    amount_str = f" ({int(float(amount)):,} VND)" if amount else ""
    if status == "used" and row.get("receipt"):
        etype, title = "disbursed", f"Giải ngân thành công{amount_str}"
    elif status == "rejected":
        etype, title = "approval_decided", f"Yêu cầu bị từ chối{amount_str}"
    else:  # used (không receipt) / approved → đã duyệt
        etype, title = "approval_decided", f"Yêu cầu đã được phê duyệt{amount_str}"
    ts = row.get("ts")
    return {"type": etype, "title": title, "ts": ts.isoformat() if ts else None, "conv_id": row["conv_id"]}
