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
        "exec_attempts": row.get("exec_attempts", 0),  # T4-0 loop-bound
    }


# DF-B-01: enrich hàng chờ duyệt lúc ĐỌC — cán bộ thấy TÊN KHÁCH + số tiền + lane, không chỉ UUID.
# JOIN read-time (KHÔNG đổi schema/payload GHI — money-path gated đóng băng). fail-soft tuyệt đối:
# lookup miss → field null; payload rác → display toàn null; KHÔNG BAO GIỜ 500 hàng chờ.
#
# Chuỗi resolve owner (1 query, LEFT JOIN) — hỗ trợ CẢ 2 dạng action (T12-5 FAIL C):
#   · disburse cũ: payload {loan_id, amount} → loans.loan_id → owner_id
#   · ops_disburse (Products/Ops): payload {application_id, amount_vnd} → applications.id → owner_id
#   ref_id = COALESCE(loan_id, application_id) — 1 field hiển thị. amount = COALESCE(amount, amount_vnd).
#   FALLBACK (edge: MAIN nhét owner vào loan_id, vd "C902") → customers.id=ref_id.
#   eff_owner = COALESCE(loans.owner, applications.owner, customers.id=ref_id). customer_name theo eff_owner.
#   lane = assessments MỚI NHẤT của eff_owner. amount KHÔNG cast SQL (::bigint THROW rác) — cast Python.
_ENRICH_SELECT = (
    "SELECT a.*, "
    "  COALESCE(a.payload->>'loan_id', a.payload->>'application_id') AS _disp_loan_id, "
    "  COALESCE(a.payload->>'amount', a.payload->>'amount_vnd') AS _disp_amount_raw, "
    "  COALESCE(l.owner_id, ap.owner_id, cf.id) AS _disp_owner_id, "
    "  COALESCE(cl.full_name, ca.full_name, cf.full_name) AS _disp_customer_name, "
    "  (SELECT s.lane FROM assessments s WHERE s.owner_id = COALESCE(l.owner_id, ap.owner_id, cf.id) "
    "     ORDER BY s.id DESC LIMIT 1) AS _disp_lane "
    "FROM approvals a "
    "LEFT JOIN loans l ON l.loan_id = a.payload->>'loan_id' "
    "LEFT JOIN customers cl ON cl.id = l.owner_id "
    "LEFT JOIN applications ap ON ap.id = a.payload->>'application_id' "
    "LEFT JOIN customers ca ON ca.id = ap.owner_id "
    "LEFT JOIN customers cf ON cf.id = COALESCE(a.payload->>'loan_id', a.payload->>'application_id') "
    "WHERE a.status='pending'"
)


def _safe_int(raw: Any) -> int | None:
    """Cast amount → int fail-soft (float-then-int như _notify_decided). Rác/None → None."""
    if raw is None:
        return None
    try:
        return int(float(raw))
    except (ValueError, TypeError):
        return None


def _display_of(row: dict[str, Any]) -> dict[str, Any]:
    """Object `display` (contract FE DF-B-01) — 5 field, mọi miss = null. Không phá field cũ."""
    return {
        "customer_name": row.get("_disp_customer_name"),
        "owner_id": row.get("_disp_owner_id"),
        "loan_id": row.get("_disp_loan_id"),
        "amount_vnd": _safe_int(row.get("_disp_amount_raw")),
        "lane": row.get("_disp_lane"),
    }


def _list_pending_sync(conv_id: str | None) -> list[dict[str, Any]]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if conv_id:
                cur.execute(_ENRICH_SELECT + " AND a.conv_id=%s ORDER BY a.id", (conv_id,))
            else:
                cur.execute(_ENRICH_SELECT + " ORDER BY a.id")
            out = []
            for r in cur.fetchall():
                r = dict(r)
                base = _row_to_dict(r)  # mọi field cũ giữ nguyên (payload/status/receipt...)
                base["display"] = _display_of(r)  # DF-B-01: thêm display, KHÔNG đổi field cũ
                out.append(base)
            return out
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
    except psycopg2.errors.InvalidTextRepresentation:
        # approval_id KHÔNG phải UUID hợp lệ (input user malformed) → None → API check _exists (cũng
        # catch → False) → 404, KHÔNG để psycopg2 DataError lọt ra 500 (nhất quán _get_task/_exists).
        # tester/architect rà 3 API nhận uuid ngoài (T4-3): decide malformed → 500 → giờ 404.
        return None
    finally:
        conn.close()


# T4-0 loop-bound: trần số lần guard-B re-dispatch ops#2 claim 1 phiếu approved. Vượt = fail BỀN
# (loan xoá/lỗi logic lặp) → dừng re-dispatch (chống task-storm) + báo main. =3: cho retry fail-TẠM
# (DB gián đoạn 1-2 lần) nhưng chặn loop. Spec im lặng → decide-and-log (đảo được: đổi số).
MAX_EXEC_ATTEMPTS = 3


def _peek_grant_sync(conv_id: str) -> dict[str, Any] | None:
    """T3-4/T4-0 — PEEK grant treo (approved-chưa-used) cũ nhất của conv, KHÔNG mutate. None = không
    có. guard-B đọc để biết role sở hữu + exec_attempts (quyết re-dispatch/vượt-trần) TRƯỚC khi tốn
    quota — increment tách riêng (claim_exec_attempt) chỉ khi chắc re-dispatch (role khớp)."""
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


def _claim_exec_attempt_sync(approval_id: str) -> int:
    """T4-0 — increment exec_attempts ATOMIC (UPDATE…RETURNING) → trả attempt MỚI. Gọi CHỈ khi guard-B
    chắc chắn re-dispatch (role khớp). Atomic (defensive #3): 2 guard-B đua → mỗi UPDATE độc lập tăng,
    không đọc-rồi-ghi (không mất increment). row_lock ngầm ở UPDATE per-row."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE approvals SET exec_attempts = exec_attempts + 1 WHERE id=%s RETURNING exec_attempts",
                (approval_id,),
            )
            row = cur.fetchone()
        conn.commit()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def _mark_exec_failed_sync(approval_id: str) -> None:
    """Vượt trần re-dispatch → phiếu status='exec_failed' (dừng grant + đánh dấu cần người kiểm).
    approved→exec_failed 1 chiều (chỉ khi chưa used — không đè phiếu đã giải ngân)."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE approvals SET status='exec_failed' WHERE id=%s AND status='approved' AND used_at IS NULL",
                (approval_id,),
            )
        conn.commit()
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


async def peek_grant(conv_id: str) -> dict[str, Any] | None:
    """PEEK grant treo (approved-chưa-used) — KHÔNG mutate. Có exec_attempts để guard-B quyết (T4-0)."""
    return await asyncio.to_thread(_peek_grant_sync, conv_id)


async def claim_exec_attempt(approval_id: str) -> int:
    """Increment exec_attempts atomic → attempt mới. Gọi khi guard-B re-dispatch (T4-0)."""
    return await asyncio.to_thread(_claim_exec_attempt_sync, approval_id)


async def mark_exec_failed(approval_id: str) -> None:
    """Vượt trần re-dispatch → phiếu 'exec_failed' (T4-0)."""
    return await asyncio.to_thread(_mark_exec_failed_sync, approval_id)


def valid_decision(decision: str) -> bool:
    return decision in _DECISION_STATUS
