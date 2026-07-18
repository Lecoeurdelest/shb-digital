"""Approvals CRUD (T3-2) — tách khỏi store.py (D-34: store.py 409 LOC, decide+list vào file mới).

decide ATOMIC một chiều (UPDATE…WHERE status='pending' RETURNING) — 2 admin bấm / double-wake
đều rowcount 0 lần thứ hai. psycopg2 sync qua asyncio.to_thread (D-22). CRUD 4 bước phanh (tạo
phiếu/claim/receipt) VẪN inline trong gated._gated_txn (single-tx atomicity) — file này CHỈ lo
decide (admin) + list (render), là read/write NGOÀI wrapper tx.
"""

from __future__ import annotations

import asyncio
import json
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
    không tồn tại) → None. rowcount 1 → row decided (có conv_id, action để đánh thức main).

    T3-2 gap (FE+architect): card.data.status nằm JSONB riêng, KHÔNG tự đổi khi decide → reload ca
    sau duyệt thấy card 'pending' (sai, 2 nguồn sự thật lệch). Fix: sync card.data trong CÙNG tx
    decide (atomic — card ⟺ approval, không window lệch). Trả kèm card_row để caller emit SSE."""
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
            if row is None:
                conn.commit()
                return None
            # sync card.data.status/decided_by/reason theo decision (CÙNG tx — card khớp approval).
            # card approval khớp qua data->>'approval_id' (T3-1 VỎ-inject approval_id vào card).
            cur.execute(
                "UPDATE cards SET data = data || %s::jsonb "
                "WHERE conv_id=%s AND type='approval' AND data->>'approval_id'=%s "
                "RETURNING id, conv_id, task_id, type, data, ts",
                (
                    json.dumps({"status": status, "decided_by": decided_by, "reason": reason}),
                    str(row["conv_id"]),
                    approval_id,
                ),
            )
            card_row = cur.fetchone()
        conn.commit()
        decided = _row_to_dict(dict(row))
        decided["_card_row"] = dict(card_row) if card_row else None  # _ prefix: nội bộ, không lên API
        return decided
    finally:
        conn.close()


def _pending_execution_sync(conv_id: str) -> dict[str, Any] | None:
    """GRANT lookup (T3-4 race fix): phiếu status='approved' CHƯA 'used' của conv → cần re-dispatch
    role gọi lại tool để claim bước 2. None = không có grant treo (path bình thường).

    Đây LÀ 'grant pending execution' — không state mới: approved-chưa-used row chính là grant
    (mang conv_id + action + payload). ops#2 claim → flip 'used' → grant tự clear (không double).
    Nhiều grant (nhiều action chờ) → lấy CŨ NHẤT (id order) — xử tuần tự.
    """
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM approvals WHERE conv_id=%s AND status='approved' AND used_at IS NULL "
                "ORDER BY id LIMIT 1",
                (conv_id,),
            )
            row = cur.fetchone()
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


async def pending_execution(conv_id: str) -> dict[str, Any] | None:
    """Grant treo (approved-chưa-used) của conv → cần re-dispatch role claim bước 2 (T3-4)."""
    return await asyncio.to_thread(_pending_execution_sync, conv_id)


def valid_decision(decision: str) -> bool:
    return decision in _DECISION_STATUS
