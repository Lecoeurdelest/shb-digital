"""Phanh — wrapper gated + payload_hash + disburse stub (T3-1, SPEC §4.4). TÂM ĐIỂM S3.

Ẩn dụ: két tiền cần chìa giám đốc — dù nhân viên muốn/bị dụ mở, tay vặn không ra tiền. Luật
nằm ở CÁI KÉT (tầng tool), không ở lời dặn (N2).

THREAD-CONN (khác lab-joint §2.1 ở conn): gated write dùng 1 psycopg2 conn RIÊNG, 1 tx đồng bộ
BEGIN→4 bước→COMMIT, thread SAME conn vào inner(conn,args). Chạy trong `asyncio.to_thread` (D-22
— không block event loop 1-worker). Read tool giữ handler per-call (mount_role §2). CHỈ gated
whitelist thread-tx.

INVARIANT MONEY (advisor): receipt-save TRONG CÙNG tx với claim+inner → `status='used' ⟺ receipt
present`. inner throw → rollback → phiếu về 'approved' → retry sạch. receipt tách tx = money-doubling
window (used+receipt=NULL → retry mint phiếu mới). SSE STRICTLY SAU commit (rollback không emit card ma).

D-40: atomic claim (UPDATE…WHERE status='approved') + biên nhận = code cơ bản; KHÔNG crash-injection.
Gated path = raw psycopg2 + %s (KHÔNG PGConnAdapter — adapter chỉ cho LAB read tool `?`).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import psycopg2
import psycopg2.extras

from app.db.config import DATABASE_URL
from app.orch import registry

log = logging.getLogger("orch.gated")

# Tool nào gated = whitelist config (khởi điểm: disburse). Ranh gate (§4.4): chỉ irreversible +
# ảnh-hưởng-ngoài; write reversible → write-through (không gate, friction giết tự trị).
GATED_WHITELIST = {"disburse"}

# Field phi-nghiệp-vụ bỏ khỏi payload_hash (ts/ghi chú không đổi danh tính hành động).
NON_BIZ_FIELDS = {"ts", "timestamp", "note", "ghi_chu", "ghi_chú", "_meta"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def payload_hash(action: str, args: dict[str, Any]) -> str:
    """1 HÀM DUY NHẤT — dùng chung tạo phiếu LẪN verify (2 hàm lệch = phanh chết âm thầm).
    Chuẩn hoá: bỏ None/phi-nghiệp-vụ · số về 1 dạng float (5e9≡5000000000) · sort key."""
    biz = {
        k: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
        for k, v in sorted(args.items())
        if v is not None and k not in NON_BIZ_FIELDS
    }
    canon = json.dumps({"action": action, **biz}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:16]


def _summarize(args: dict[str, Any]) -> str:
    """Tóm tắt payload cho message (mặt model — nói theo HÀNH ĐỘNG, KHÔNG phiếu-id §15)."""
    parts = [f"{k}={v}" for k, v in args.items() if k not in NON_BIZ_FIELDS and v is not None]
    return ", ".join(parts)


# ── disburse stub (vỏ viết — D-18 phanh của vỏ, LAB chưa có ops) ────────────
def disburse(conn: Any, loan_id: str, amount: float = 0) -> dict[str, Any]:
    """[STUB vỏ] Giải ngân = ghi loans.status='disbursed' (D-21 write-back). Nhận conn wrapper
    cấp (SAME tx với claim). raw %s. Trả biên nhận {disbursed, loan_id, amount, asOf}."""
    with conn.cursor() as cur:
        cur.execute("UPDATE loans SET status='disbursed' WHERE loan_id=%s", (loan_id,))
        if cur.rowcount == 0:
            raise ValueError(f"loan '{loan_id}' không tồn tại")
    return {"disbursed": True, "loan_id": loan_id, "amount": amount, "asOf": _now()}


# REGISTRY tool gated (vỏ viết). inner(conn, **args) — nhận conn wrapper cấp (SAME tx).
GATED_TOOLS: dict[str, Callable[..., dict[str, Any]]] = {"disburse": disburse}


class _GatedResult:
    """Kết quả _gated_txn: dict trả model + optional 'to-emit' (card/approval sinh ở bước 4).
    SSE emit SAU commit ở async handler (advisor #3 — rollback không emit card ma)."""

    def __init__(self, payload: dict[str, Any], emit: dict[str, Any] | None = None) -> None:
        self.payload = payload
        self.emit = emit  # {card, approval, status} nếu bước 4 tạo phiếu; None nếu không


def _gated_txn(action: str, conv_id: str, task_id: str | None, args: dict[str, Any]) -> _GatedResult:
    """LÕI ĐỒNG BỘ — 1 conn, 1 tx, 4 bước, KHÔNG await bên trong (advisor #1). commit/rollback/close.

    4 bước THEO THỨ TỰ (SPEC §4.4), key (conv_id, action, payload_hash) LUÔN lọc conv_id:
    """
    ph = payload_hash(action, args)
    conn = psycopg2.connect(DATABASE_URL)  # conn RIÊNG (mirror store/D-34 — KHÔNG mount pool adapter)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # SERIALIZE per-key (architect phán quyết — chống race phiếu-rác): 2 gọi đồng thời cùng
            # (conv_id, action, ph) → con thua CHỜ con thắng commit → thấy used/pending đã commit →
            # KHÔNG đẻ phiếu giả ở bước 4. tx-scoped → tự release ở commit/rollback (không rò lock).
            # Cứu CẢ 2 variant: (a) 2 gọi đầu, (b) gọi sau khi phiếu bị claim→used (partial-unique-index
            # KHÔNG đủ vì 'used' ngoài index). Block 1 thread trong to_thread (không block loop) — gated
            # hiếm + ngắn, chấp nhận. KHÔNG SERIALIZABLE/FOR UPDATE (giữ altitude D-40).
            # lock_key deterministic từ (conv_id, ph) — KHÔNG dùng hash() Python (PYTHONHASHSEED
            # đổi giữa process → 2 process lock khác key). sha256 → int ổn định mọi process/restart.
            lock_key = int(hashlib.sha256(f"{conv_id}:{ph}".encode()).hexdigest()[:15], 16) & 0x7FFFFFFFFFFFFFFF
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))

            # 1. Biên nhận cũ? → trả biên nhận, KHÔNG chạy lại (chống thực-thi-đôi §4.4)
            cur.execute(
                "SELECT receipt FROM approvals WHERE conv_id=%s AND action=%s AND payload_hash=%s "
                "AND status='used' LIMIT 1",
                (conv_id, action, ph),
            )
            row = cur.fetchone()
            if row and row["receipt"] is not None:
                conn.commit()
                return _GatedResult(
                    {**row["receipt"], "hint": "Hành động này ĐÃ thực thi trước đó — đây là biên nhận."}
                )

            # 2. Phiếu approved? → CLAIM ATOMIC rồi mới chạy (1 phiếu = đúng 1 lần chạy)
            cur.execute(
                "UPDATE approvals SET status='used', used_at=now() "
                "WHERE conv_id=%s AND action=%s AND payload_hash=%s AND status='approved' "
                "RETURNING id",
                (conv_id, action, ph),
            )
            claimed = cur.fetchone()  # rowcount 1 = claim được; None = không có/đã bị claim
            if claimed:
                inner = GATED_TOOLS[action]
                # inner chạy THẬT trên SAME conn (SAME tx) — ghi loans.status
                out = inner(conn, **args)
                # receipt-save TRONG CÙNG tx (advisor #2 — INVARIANT: status='used' ⟺ receipt present).
                # Tách tx = money-doubling window (used+receipt=NULL → retry mint phiếu mới).
                cur.execute(
                    "UPDATE approvals SET receipt=%s WHERE id=%s",
                    (json.dumps(out), claimed["id"]),
                )
                conn.commit()  # claim + inner-write + receipt cùng COMMIT
                return _GatedResult(out)

            # 3. Phiếu pending? → báo chờ, KHÔNG đẻ phiếu/card mới (idempotent bước pending)
            cur.execute(
                "SELECT id FROM approvals WHERE conv_id=%s AND action=%s AND payload_hash=%s "
                "AND status='pending' LIMIT 1",
                (conv_id, action, ph),
            )
            if cur.fetchone():
                conn.commit()
                return _GatedResult(
                    {
                        "code": "approval_pending",
                        "message": f"'{action}' với đúng tham số này ĐANG chờ duyệt",
                        "hint": "Báo main và kết thúc lượt — có kết quả duyệt sẽ được gọi lại.",
                        "retryable": False,
                    }
                )

            # 4. Chưa có gì → tạo phiếu pending TRƯỚC (có approval_id) → VỎ sinh card approval (§6).
            cur.execute(
                "INSERT INTO approvals (conv_id, task_id, action, payload, payload_hash, status) "
                "VALUES (%s, %s, %s, %s, %s, 'pending') RETURNING id",
                (conv_id, task_id or None, action, json.dumps(args), ph),
            )
            approval_id = str(cur.fetchone()["id"])
            # card approval — approval_id VỎ-inject vào card (FE decide dùng approval_id ≠ card.id).
            # id/approval_id đều VỎ-owned (§15 — model không bơm; card.id = server_default, approval_id
            # = phiếu vừa tạo). FE: POST /approvals/{card.approval_id}/decide (T3-2).
            card_data = {
                "type": "approval",
                "title": f"Duyệt: {action} ({_summarize(args)})",
                "action": action,
                "approval_id": approval_id,  # phiếu-id để FE decide (T3-2 endpoint)
                "items": [{"label": k, "value": v} for k, v in args.items() if k not in NON_BIZ_FIELDS],
                "options": ["Duyệt", "Từ chối"],
                "status": "pending",
            }
            cur.execute(
                "INSERT INTO cards (conv_id, task_id, type, data, ts) "
                "VALUES (%s, %s, 'approval', %s, now()) RETURNING id, conv_id, task_id, type, data, ts",
                (conv_id, task_id or None, json.dumps(card_data)),
            )
            card_row = dict(cur.fetchone())
            # conversation.status = waiting_approval
            cur.execute("UPDATE conversations SET status='waiting_approval' WHERE id::text=%s", (conv_id,))
            conn.commit()
            # to-emit struct — async handler emit SAU commit (advisor #3)
            emit_struct = {
                "card": card_row,
                "approval_id": approval_id,
                "conv_id": conv_id,
                "action": action,
                "payload": args,
            }
        return _GatedResult(
            {
                "code": "approval_required",
                "message": f"'{action}' ({_summarize(args)}) cần người duyệt",
                "hint": "Đã gửi chờ duyệt — báo main và kết thúc lượt.",
                "retryable": False,
            },
            emit=emit_struct,
        )
    except Exception:
        conn.rollback()  # inner throw / bất kỳ lỗi → rollback: claim undone, phiếu về approved (retry sạch)
        raise
    finally:
        conn.close()


def gated(action: str, inner_read_handler: Callable) -> Callable:
    """Wrapper gated cho 1 tool trong GATED_WHITELIST. Trả async handler (SDK gọi).
    inner_read_handler KHÔNG dùng (gated tự chạy GATED_TOOLS[action] trong tx) — giữ chữ ký
    tương thích mount loop. args → _gated_txn qua to_thread → SSE emit sau."""

    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        conv_id = registry.CTX_CONV.get()
        task_id = registry.CTX_TASK.get() or None  # Ops sub task (đúng — không leak, inside sub)
        try:
            result: _GatedResult = await asyncio.to_thread(_gated_txn, action, conv_id, task_id, args)
        except Exception as e:  # noqa: BLE001 — cửa cuối: agent thấy error 4-field, không traceback
            log.error("gated %s lỗi: %s", action, e)
            return _text(
                {
                    "code": "gated_error",
                    "message": str(e)[:200],
                    "hint": "Lỗi nội bộ phanh — thử lại 1 lần; lặp thì báo main.",
                    "retryable": True,
                }
            )
        # SSE SAU commit (advisor #3): bước 4 tạo phiếu → emit card + approval.pending + status
        if result.emit is not None:
            _emit_approval(result.emit)
        return _text(result.payload)

    return handler


def _emit_approval(emit_data: dict[str, Any]) -> None:
    """SSE 3 tín hiệu bước 4 (canvas-present §6): card + approval.pending + conversation.status.
    Lazy import (SSE ≠ tx). Lỗi SSE KHÔNG fail (phiếu đã commit — fire-and-forget)."""
    try:
        from app.orch.store import _card_to_dict
        from app.sse.emit import emit, emit_conversation_status

        card = _card_to_dict(emit_data["card"])
        emit(emit_data["conv_id"], "card", {"card": card})
        emit(
            emit_data["conv_id"],
            "approval.pending",
            {"phieu": {"id": emit_data["approval_id"], "action": emit_data["action"], "status": "pending"}},
        )
        emit_conversation_status(emit_data["conv_id"], "waiting_approval")
    except Exception as e:  # noqa: BLE001
        log.warning("emit approval lỗi (bỏ qua): %s", e)


def _text(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}
