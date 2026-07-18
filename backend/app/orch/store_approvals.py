"""Approvals CRUD (T3-2) — tách khỏi store.py (D-34: store.py 409 LOC, decide+list vào file mới).

decide ATOMIC một chiều (UPDATE…WHERE status='pending' RETURNING) — 2 admin bấm / double-wake
đều rowcount 0 lần thứ hai. psycopg2 sync qua asyncio.to_thread (D-22). CRUD 4 bước phanh (tạo
phiếu/claim/receipt) VẪN inline trong gated._gated_txn (single-tx atomicity) — file này CHỈ lo
decide (admin) + list (render), là read/write NGOÀI wrapper tx.
"""

from __future__ import annotations

import asyncio
from typing import Any

import psycopg2
import psycopg2.extras

from app.db.config import DATABASE_URL

# decision (API body) → approvals.status
_DECISION_STATUS = {"approved": "approved", "rejected": "rejected"}


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Serialize approval row cho API/SSE (resource trần). id/conv_id str; ts iso."""
    return {
        "id": str(row["id"]),
        "conv_id": str(row["conv_id"]),
        "task_id": str(row["task_id"]) if row.get("task_id") else None,
        "action": row["action"],
        "payload": row.get("payload"),
        "payload_hash": row.get("payload_hash"),
        "status": row["status"],
        "decided_by": row.get("decided_by"),
        "decided_at": row["decided_at"].isoformat() if row.get("decided_at") else None,
        "reason": row.get("reason"),
        "used_at": row["used_at"].isoformat() if row.get("used_at") else None,
        "receipt": row.get("receipt"),
    }


def _list_pending_sync(conv_id: str | None) -> list[dict[str, Any]]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if conv_id:
                cur.execute(
                    "SELECT * FROM approvals WHERE status='pending' AND conv_id=%s ORDER BY id",
                    (conv_id,),
                )
            else:
                cur.execute("SELECT * FROM approvals WHERE status='pending' ORDER BY id")
            return [_row_to_dict(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


def _decide_sync(approval_id: str, decision: str, decided_by: str, reason: str | None) -> dict[str, Any] | None:
    """ATOMIC một chiều: UPDATE…WHERE id AND status='pending' RETURNING. rowcount 0 (đã quyết/
    không tồn tại) → None. rowcount 1 → row decided (có conv_id, action để đánh thức main)."""
    status = _DECISION_STATUS[decision]  # caller validate decision trước
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "UPDATE approvals SET status=%s, decided_by=%s, decided_at=now(), reason=%s "
                "WHERE id=%s AND status='pending' RETURNING *",
                (status, decided_by, reason, approval_id),
            )
            row = cur.fetchone()
        conn.commit()
        return _row_to_dict(dict(row)) if row else None
    finally:
        conn.close()


def _exists_sync(approval_id: str) -> bool:
    """Phân biệt 404 (không tồn tại) vs 409 (đã quyết) khi decide trả None."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM approvals WHERE id=%s", (approval_id,))
            return cur.fetchone() is not None
    except psycopg2.Error:
        return False  # id sai format uuid → coi như không tồn tại
    finally:
        conn.close()


# ── async wrappers (D-22: sync qua to_thread) ───────────────────────────────
async def list_pending(conv_id: str | None = None) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_pending_sync, conv_id)


async def decide(approval_id: str, decision: str, decided_by: str, reason: str | None = None) -> dict[str, Any] | None:
    return await asyncio.to_thread(_decide_sync, approval_id, decision, decided_by, reason)


async def approval_exists(approval_id: str) -> bool:
    return await asyncio.to_thread(_exists_sync, approval_id)


def valid_decision(decision: str) -> bool:
    return decision in _DECISION_STATUS
