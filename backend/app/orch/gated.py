"""Phanh — wrapper gated + payload_hash + disburse stub (T3-1, SPEC §4.4). TÂM ĐIỂM S3.

Ẩn dụ: két tiền cần chìa giám đốc — dù nhân viên muốn/bị dụ mở, tay vặn không ra tiền. Luật
nằm ở CÁI KÉT (tầng tool), không ở lời dặn (N2).

THREAD-CONN (khác lab-joint §2.1 ở conn): gated write dùng 1 psycopg2 conn RIÊNG, 1 tx đồng bộ
BEGIN→4 bước→COMMIT, thread SAME conn vào inner(conn,args). Chạy trong `asyncio.to_thread` (D-22
— không block event loop 1-worker). Read tool giữ handler per-call (mount_role §2). CHỈ gated
whitelist thread-tx.

INVARIANT MONEY (advisor): receipt-save TRONG CÙNG tx với lock+inner → `status='used' ⟺ receipt
present + used_at`. inner throw → rollback → phiếu về 'approved' → retry sạch. receipt tách tx =
money-doubling window. SSE STRICTLY SAU commit (rollback không emit card ma).

D-40/D-76: row lock + final UPDATE `used+receipt+used_at` + biên nhận = code cơ bản;
KHÔNG crash-injection.
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

from app.orch import registry
from app.orch.disburse_guard import cross_owner_refusal
from app.orch.gated_postcommit import emit_approval as _emit_approval
from app.orch.gated_postcommit import notify_disbursed as _notify_disbursed
from app.orch.gated_postcommit import notify_pending_doorbell as _notify_pending_doorbell
from app.orch.gated_postcommit import text_payload as _text
from app.orch.gated_types import ConnLike, Receipt
from app.orch.ops_bridge import OpsDisburseBlocked
from app.orch.verdict import auto_approve_threshold, gated_decision
from app.storage import connect_core

# T12-3b: block payload passthrough (ops_bridge lazy-import roles → không cycle với gated)

log = logging.getLogger("orch.gated")

# Tool nào gated = whitelist config (khởi điểm: disburse). Ranh gate (§4.4): chỉ irreversible +
# ảnh-hưởng-ngoài; write reversible → write-through (không gate, friction giết tự trị).
# T12-3: + ops_disburse (LAB operations port, roles/operations/functions.py) — GATED THỨ HAI,
# ĐỘC LẬP với "disburse" (action-key khác nhau trong payload_hash/approvals/GATED_TOOLS) — KHÔNG
# đụng đường "disburse"/loans/loan_id/amount hiện có (30 money-test neo vào đó, xem test_gated.py
# + test_gate_s3_gated_disburse_tester.py). ops_disburse LUÔN human về mặt vận hành (không có đường
# auto), nhưng evaluator S18 hiểu application_id → applications.owner_id để snapshot lane/khuyến nghị
# phản-thực cho shadow ledger; red vẫn là reject-recommended, còn lại human-review. cross_owner_refusal
# vẫn chỉ áp action=="disburse" vì owner-scope khách của ops là seam độc lập, không thuộc T18.
GATED_WHITELIST = {"disburse", "ops_disburse"}

# Field phi-nghiệp-vụ bỏ khỏi payload_hash (ts/ghi chú không đổi danh tính hành động).
NON_BIZ_FIELDS = {"ts", "timestamp", "note", "ghi_chu", "ghi_chú", "_meta"}

# T5-2'→T7-3 phanh PHÂN TẦNG (D-52/D-56): điều kiện auto = verdict-aware MA TRẬN 3 TẦNG ở
# app/orch/verdict.py (ngưỡng assumptions + gated_decision import ở trên). gated giữ nguyên
# cấu trúc 4-step tx + advisory lock — CHỈ đổi điều kiện auto (nhánh 4a). assessments rỗng → như cũ.


# MA TRẬN 3 TẦNG verdict-aware (T7-3) tách sang app/orch/verdict.py (chuẩn PROD ≤400 LOC).
# gated._gated_txn nhánh 4a gọi gated_decision(...) → route + snapshot phản-thực cho phiếu người.


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


def approval_idempotency_key(conv_id: str, action: str, digest: str) -> str:
    """Stable business-intent key. DB trigger mirrors this for legacy/raw writers."""
    return f"idem:v1:{conv_id}:{action}:{digest}"


def _summarize(args: dict[str, Any]) -> str:
    """Tóm tắt payload cho message (mặt model — nói theo HÀNH ĐỘNG, KHÔNG phiếu-id §15)."""
    parts = [f"{k}={v}" for k, v in args.items() if k not in NON_BIZ_FIELDS and v is not None]
    return ", ".join(parts)


# ── disburse stub (vỏ viết — D-18 phanh của vỏ, LAB chưa có ops) ────────────
def disburse(conn: ConnLike, loan_id: str, amount: float = 0) -> Receipt:
    """[STUB vỏ] Giải ngân = ghi loans.status='disbursed' (D-21 write-back). Nhận conn wrapper
    cấp (SAME tx với claim). raw %s. Trả biên nhận {disbursed, loan_id, amount, asOf}."""
    with conn.cursor() as cur:
        cur.execute("UPDATE loans SET status='disbursed' WHERE loan_id=%s", (loan_id,))
        if cur.rowcount == 0:
            raise ValueError(f"loan '{loan_id}' không tồn tại")
    return {"disbursed": True, "loan_id": loan_id, "amount": amount, "asOf": _now()}


def _ops_disburse_inner(conn: ConnLike, **args: Any) -> Receipt:
    """[T12-3b] Cầu nối GATED_TOOLS["ops_disburse"] → LAB ops_disburse qua OpsConnProxy.

    LAB ops_disburse viết cho sqlite3 (`conn.execute`/`?`/BEGIN IMMEDIATE/commit nội bộ/sqlite3.Error)
    — KHÔNG chạy verbatim trên conn gated psycopg2. `run_ops_disburse` bọc proxy: `?`→`%s`, no-op
    BEGIN/commit/rollback (gated sở hữu 1 tx), map psycopg2.Error→sqlite3.*. MONEY-INVARIANT: block/
    not-found → RAISE (gated rollback → phiếu về approved, retryable — khớp contract disburse stub raise-
    on-fail); disbursement THẬT → trả receipt để finalize CÙNG tx. 0 sửa fn LAB (byte-identical)."""
    from app.orch.ops_bridge import run_ops_disburse

    return run_ops_disburse(conn, **args)  # type: ignore[return-value]


# REGISTRY tool gated (vỏ viết + T12-3 cầu nối LAB). inner(conn, **args) — nhận conn wrapper cấp (SAME tx).
GATED_TOOLS: dict[str, Callable[..., Receipt]] = {"disburse": disburse, "ops_disburse": _ops_disburse_inner}

# action → role sở hữu tool đó (dùng cho re-dispatch sau duyệt — T3-4 race fix). disburse=operations,
# ops_disburse=operations (T12-3, cùng role — LAB port).
# Khi phiếu approved cần gọi lại tool để claim bước 2, VỎ re-dispatch đúng role này.
GATED_ROLE: dict[str, str] = {"disburse": "operations", "ops_disburse": "operations"}


class _GatedResult:
    """Kết quả _gated_txn: dict trả model + optional 'to-emit' (card/approval sinh ở bước 4).
    SSE emit SAU commit ở async handler (advisor #3 — rollback không emit card ma)."""

    def __init__(
        self, payload: dict[str, Any], emit: dict[str, Any] | None = None, fresh_disburse: bool = False
    ) -> None:
        self.payload = payload
        self.emit = emit  # {card, approval, status} nếu bước 4 tạo phiếu; None nếu không
        # fresh_disburse: TRUE chỉ khi vừa THỰC THI giải ngân lần này (claim/auto) — KHÔNG replay
        # (T9-2 hook b: mail giải-ngân 1 lần/receipt, replay-branch disbursed:True nhưng KHÔNG mail lại).
        self.fresh_disburse = fresh_disburse


# ── HELPER refactor (T11-2, HÀNH VI 0 ĐỔI): tách 5 nhánh _gated_txn. GIỮ 1 tx (helper KHÔNG mở
# conn/tx riêng — nhận conn+cur từ _gated_txn), advisory-lock ĐÃ giữ trước khi gọi. HỢP ĐỒNG:
# nhánh ĐIỀU-KIỆN (receipt/claim/pending) trả None = KHÔNG-phải-ca-tao → fall-through nhánh kế;
# trả _GatedResult = terminal (đã commit trong helper). auto/human = terminal (luôn 1 trong 2).
# except cửa-cuối GIỮ ở _gated_txn (helper KHÔNG bắt).


def _finalize_receipt(cur: Any, out: Receipt, approval_id: Any) -> None:
    """Final state is one statement so the DB can enforce used iff receipt+used_at."""
    cur.execute(
        "UPDATE approvals SET status='used',receipt=%s,used_at=now() WHERE id=%s AND status='approved'",
        (json.dumps(out), approval_id),
    )
    if cur.rowcount != 1:
        raise RuntimeError("approval claim was lost before receipt finalization")


def _branch_receipt_replay(conn: ConnLike, cur: Any, ctx: dict[str, Any]) -> _GatedResult | None:
    """1. Biên nhận cũ? → trả biên nhận, KHÔNG chạy lại (chống thực-thi-đôi §4.4). None = chưa từng."""
    cur.execute(
        "SELECT receipt FROM approvals WHERE idempotency_key=%s AND status='used' LIMIT 1",
        (ctx["idempotency_key"],),
    )
    row = cur.fetchone()
    if row and row["receipt"] is not None:
        conn.commit()
        return _GatedResult({**row["receipt"], "hint": "Hành động này ĐÃ thực thi trước đó — đây là biên nhận."})
    return None


def _branch_claim(conn: ConnLike, cur: Any, ctx: dict[str, Any]) -> _GatedResult | None:
    """2. Lock approved row, run once, then atomically write used+receipt+used_at."""
    cur.execute(
        "SELECT id FROM approvals WHERE idempotency_key=%s AND status='approved' FOR UPDATE LIMIT 1",
        (ctx["idempotency_key"],),
    )
    claimed = cur.fetchone()
    if not claimed:
        return None
    # Advisory lock serializes the intent; row lock protects direct DB writers as a second layer.
    out = GATED_TOOLS[ctx["action"]](conn, **ctx["args"])
    _finalize_receipt(cur, out, claimed["id"])
    conn.commit()  # claim + inner-write + receipt cùng COMMIT
    return _GatedResult(out, fresh_disburse=True)  # vừa giải ngân THẬT (claim) → mail hook b


def _branch_pending(conn: ConnLike, cur: Any, ctx: dict[str, Any]) -> _GatedResult | None:
    """3. Phiếu pending? → báo chờ, KHÔNG đẻ phiếu/card mới (idempotent). None = chưa có pending."""
    cur.execute(
        "SELECT id FROM approvals WHERE idempotency_key=%s AND status='pending' LIMIT 1",
        (ctx["idempotency_key"],),
    )
    if not cur.fetchone():
        return None
    conn.commit()
    return _GatedResult(
        {
            "code": "approval_pending",
            "message": f"'{ctx['action']}' với đúng tham số này ĐANG chờ duyệt",
            "hint": "Báo main và kết thúc lượt — có kết quả duyệt sẽ được gọi lại.",
            "retryable": False,
        }
    )


def _branch_terminal(conn: ConnLike, cur: Any, ctx: dict[str, Any]) -> _GatedResult | None:
    """A rejected/failed intent is terminal; retry needs a changed intent instead of a duplicate row."""
    cur.execute(
        "SELECT status,reason FROM approvals WHERE idempotency_key=%s AND status IN ('rejected','exec_failed') LIMIT 1",
        (ctx["idempotency_key"],),
    )
    row = cur.fetchone()
    if row is None:
        return None
    conn.commit()
    failed = row["status"] == "exec_failed"
    return _GatedResult(
        {
            "code": "approval_execution_failed" if failed else "approval_rejected",
            "message": "Hành động này đã thất bại và cần kiểm tra thủ công."
            if failed
            else "Hành động này đã bị người duyệt từ chối.",
            "hint": row["reason"]
            or ("Liên hệ vận hành để xử lý." if failed else "Thay đổi yêu cầu trước khi gửi lại."),
            "retryable": False,
        }
    )


def _branch_auto(conn: ConnLike, cur: Any, ctx: dict[str, Any], reason: str) -> _GatedResult:
    """4a. AUTO-DUYỆT CÓ KIỂM SOÁT (T7-3): phiếu 'used' decided_by='auto-rule' + inner + receipt + card
    THÔNG BÁO CÙNG tx → chạy NGAY. Terminal (luôn trả result)."""
    conv_id, action, task_id, args, ph = ctx["conv_id"], ctx["action"], ctx["task_id"], ctx["args"], ctx["ph"]
    inner_out = GATED_TOOLS[action](conn, **args)  # chạy THẬT (SAME tx) — ghi loans.status
    out: Receipt = {**inner_out, "auto_approved": True, "approved_by": "auto-rule", "note": reason}
    cur.execute(
        "INSERT INTO approvals (conv_id,task_id,action,payload,payload_hash,idempotency_key,status,"
        "decided_by,decided_at,reason,used_at,receipt) "
        "VALUES (%s,%s,%s,%s,%s,%s,'used','auto-rule',now(),%s,now(),%s)",
        (
            conv_id,
            task_id or None,
            action,
            json.dumps(args),
            ph,
            ctx["idempotency_key"],
            reason,
            json.dumps(out),
        ),
    )
    # card THÔNG BÁO (type document — KHÔNG nút; NÓI RÕ tự duyệt — transparency #7 architect).
    notice = {
        "type": "document",
        "title": f"✅ Tự động duyệt & thực thi: {action} ({_summarize(args)})",
        "items": [
            {"section": "Cơ chế", "content": reason},
            {"section": "Kết quả", "content": json.dumps(out, ensure_ascii=False)},
        ],
        "sources": ["phanh phân tầng — auto-rule"],
    }
    cur.execute(
        "INSERT INTO cards (conv_id, task_id, type, data, ts) "
        "VALUES (%s, %s, 'document', %s, now()) RETURNING id, conv_id, task_id, type, data, ts",
        (conv_id, task_id or None, json.dumps(notice)),
    )
    card_row = dict(cur.fetchone())
    conn.commit()  # phiếu-approved + inner-write + receipt + card CÙNG COMMIT
    return _GatedResult(out, emit={"card": card_row, "conv_id": conv_id, "auto": True}, fresh_disburse=True)


def _branch_human(conn: ConnLike, cur: Any, ctx: dict[str, Any]) -> _GatedResult:
    """4b. CHỜ NGƯỜI (path S3 nguyên): tạo phiếu pending + card approval + waiting_approval. Terminal."""
    conv_id, action, task_id, args, ph = ctx["conv_id"], ctx["action"], ctx["task_id"], ctx["args"], ctx["ph"]
    snapshot = ctx["snapshot"]
    cur.execute(
        "INSERT INTO approvals (conv_id, task_id, action, payload, payload_hash, idempotency_key, status, "
        "system_assessment_id, system_lane, system_recommendation) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s) RETURNING id",
        (
            conv_id,
            task_id or None,
            action,
            json.dumps(args),
            ph,
            ctx["idempotency_key"],
            snapshot["system_assessment_id"],
            snapshot["system_lane"],
            snapshot["system_recommendation"],
        ),
    )
    approval_id = str(cur.fetchone()["id"])
    # card approval — approval_id VỎ-inject (FE decide dùng approval_id ≠ card.id). §15 VỎ-owned.
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
    cur.execute("UPDATE conversations SET status='waiting_approval' WHERE id::text=%s", (conv_id,))
    conn.commit()
    return _GatedResult(
        {
            "code": "approval_required",
            "message": f"'{action}' ({_summarize(args)}) cần người duyệt",
            "hint": "Đã gửi phiếu chờ duyệt. KẾT THÚC LƯỢT NGAY — chỉ trả 1 câu ngắn 'đã gửi "
            "chờ duyệt', KHÔNG viết thêm phân tích/tường thuật. Duyệt xong hệ thống tự gọi lại.",
            "retryable": False,
        },
        emit={"card": card_row, "approval_id": approval_id, "conv_id": conv_id, "action": action, "payload": args},
    )


def _linked_preassessment_refusal(cur: Any, conv_id: str) -> dict[str, Any] | None:
    """D-81 choke point: a tenant-consistent intake link makes every money branch unreachable."""
    cur.execute(
        "SELECT 1 FROM conversations c JOIN external_case_links e "
        "ON e.conversation_id=c.id AND e.tenant_id=c.tenant_id "
        "WHERE c.id::text=%s LIMIT 1",
        (conv_id,),
    )
    if cur.fetchone() is None:
        return None
    return {
        "code": "preassessment_only",
        "message": "Phiên intake này chỉ dùng để sơ thẩm, không được thực hiện hành động giải ngân.",
        "hint": "Bàn giao hồ sơ sang quy trình phê duyệt được ngân hàng cấu hình riêng.",
        "retryable": False,
    }


def _gated_txn(
    action: str,
    conv_id: str,
    task_id: str | None,
    args: dict[str, Any],
    threshold_vnd: float | None = None,
) -> _GatedResult:
    """LÕI ĐỒNG BỘ — preflight read + 1 money tx, 4 bước, KHÔNG await bên trong.

    D-81 preflight chặn linked case trước config read; money tx recheck để đóng race. GIỮ NGUYÊN:
    cross-owner trước lock, advisory-lock đầu money flow, thứ tự 1→2→3→auto/human và rollback cửa cuối.
    """
    # Preflight dùng lease tuần tự (không nested): linked intake return trước cả threshold loader.
    # Money transaction bên dưới kiểm LẠI để đóng race link được tạo giữa preflight và threshold.
    guard_conn = connect_core()
    try:
        with guard_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as guard_cur:
            refusal = _linked_preassessment_refusal(guard_cur, conv_id)
        guard_conn.rollback()
    finally:
        guard_conn.close()
    if refusal is not None:
        return _GatedResult(refusal)

    # D-72: config read dùng connection riêng trước money transaction để pool size=1 không bị
    # nested-acquire và lỗi config không poison transaction.
    if threshold_vnd is None:
        threshold_vnd = auto_approve_threshold()
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # D-81: SQL đầu tiên của money transaction; recheck đóng race sau preflight.
            refusal = _linked_preassessment_refusal(cur, conv_id)
            if refusal is not None:
                conn.rollback()
                return _GatedResult(refusal)

            # GUARD CROSS-OWNER (T9-4, money-adjacent): ca creator KHÁCH → loan PHẢI thuộc hồ sơ creator.
            # TRƯỚC advisory-lock + 4-step (không phí lock/phiếu cho ca bị chặn). fail-closed. Ca bank →
            # qua như cũ. Chỉ disburse. (KHÔNG phải 1 trong 5 nhánh — early-exit thứ 6 giữ tại chỗ.)
            if action == "disburse":
                refusal = cross_owner_refusal(cur, conv_id, args.get("loan_id"))
                if refusal is not None:
                    conn.rollback()  # chưa ghi gì — rollback sạch, không giữ lock
                    return _GatedResult(refusal)

            ph = payload_hash(action, args)
            # SERIALIZE per-key (chống race phiếu-rác): advisory-xact-lock deterministic (sha256, KHÔNG
            # hash() Python — PYTHONHASHSEED). tx-scoped → release ở commit/rollback. Chi tiết D-40.
            idempotency_key = approval_idempotency_key(conv_id, action, ph)
            lock_key = int(hashlib.sha256(idempotency_key.encode()).hexdigest()[:15], 16) & 0x7FFFFFFFFFFFFFFF
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))

            ctx = {
                "action": action,
                "conv_id": conv_id,
                "task_id": task_id,
                "args": args,
                "ph": ph,
                "idempotency_key": idempotency_key,
            }
            # Nhánh 1→2→3 điều-kiện (None = fall-through). Nhánh nào commit+return trong helper.
            for branch in (_branch_receipt_replay, _branch_claim, _branch_pending, _branch_terminal):
                result = branch(conn, cur, ctx)
                if result is not None:
                    return result

            # 4. MA TRẬN 3 TẦNG (T7-3): auto (dưới ngưỡng không-xấu / hồ-sơ XANH) vs human (còn lại).
            decision, reason, snapshot = gated_decision(action, conn, args, threshold_vnd)
            if decision == "auto":
                return _branch_auto(conn, cur, ctx, reason)
            ctx["snapshot"] = snapshot
            return _branch_human(conn, cur, ctx)
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
            # `_gated_txn` phải tự preflight linked-intake TRƯỚC khi đọc threshold; truyền threshold
            # từ wrapper sẽ làm production đi ngược D-81 dù direct-unit test vẫn xanh.
            result: _GatedResult = await asyncio.to_thread(_gated_txn, action, conv_id, task_id, args)
        except OpsDisburseBlocked as e:
            # T12-3b: block ops_disburse (LAB verify chặn) — _gated_txn ĐÃ rollback (except cửa-cuối
            # chạy TRƯỚC ở đây → phiếu về 'approved'). Trả THẲNG payload 4-field NGUYÊN VĂN của LAB
            # (code/message/hint/blockers) — agent + MAIN biết đúng "vì sao chặn", KHÔNG generic gated_error.
            return _text(e.payload)
        except Exception as e:  # noqa: BLE001 — cửa cuối: agent thấy error 4-field, không traceback
            log.exception("gated %s lỗi", action)  # T11-2: full traceback vào log (debug), 4-field cho agent
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
            # D-71: chuông cửa chỉ bắn cho ticket người mới, sau commit + SSE; auto bị helper skip.
            _notify_pending_doorbell(result.emit)
        # HOOK b (T9-2): mail giải ngân thành công — CHỈ khi vừa giải ngân THẬT (claim/auto), KHÔNG
        # replay. 1 điểm CHUNG cả 2 nhánh (handler post-commit) → không dup mail cho 1 receipt.
        # Chạy trên loop (handler async — to_thread trong _gated_txn không có loop cho create_task).
        if action == "disburse" and result.fresh_disburse:
            _notify_disbursed(conv_id, result.payload)
        return _text(result.payload)

    return handler
