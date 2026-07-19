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
from app.orch.disburse_guard import cross_owner_refusal
from app.orch.gated_types import ConnLike, Receipt
from app.orch.verdict import disburse_decision

log = logging.getLogger("orch.gated")

# Tool nào gated = whitelist config (khởi điểm: disburse). Ranh gate (§4.4): chỉ irreversible +
# ảnh-hưởng-ngoài; write reversible → write-through (không gate, friction giết tự trị).
# T12-3: + ops_disburse (LAB operations port, roles/operations/functions.py) — GATED THỨ HAI,
# ĐỘC LẬP với "disburse" (action-key khác nhau trong payload_hash/approvals/GATED_TOOLS) — KHÔNG
# đụng đường "disburse"/loans/loan_id/amount hiện có (30 money-test neo vào đó, xem test_gated.py
# + test_gate_s3_gated_disburse_tester.py). Verdict matrix (disburse_decision) đọc args["amount"]
# + args["loan_id"] — ops_disburse mang args["amount_vnd"]/["application_id"] (khác key) →
# disburse_decision tự nhiên rơi ('human', None) (amount thiếu/parse lỗi, xem verdict.py docstring)
# → ops_disburse LUÔN qua _branch_human (chờ người), KHÔNG qua tầng auto — cố ý, KHÔNG phải bug
# (verdict matrix chưa hiểu schema applications, siết chặt an toàn hơn nới lỏng). cross_owner_refusal
# cũng chỉ áp action=="disburse" → ops_disburse chưa có owner-scope khách (bảng applications chưa
# tồn tại T12-2 — ghi seam, KHÔNG tự vá ở đây).
GATED_WHITELIST = {"disburse", "ops_disburse"}

# Field phi-nghiệp-vụ bỏ khỏi payload_hash (ts/ghi chú không đổi danh tính hành động).
NON_BIZ_FIELDS = {"ts", "timestamp", "note", "ghi_chu", "ghi_chú", "_meta"}

# T5-2'→T7-3 phanh PHÂN TẦNG (D-52/D-56): điều kiện auto = verdict-aware MA TRẬN 3 TẦNG ở
# app/orch/verdict.py (AUTO_APPROVE_THRESHOLD + disburse_decision import ở trên). gated giữ nguyên
# cấu trúc 4-step tx + advisory lock — CHỈ đổi điều kiện auto (nhánh 4a). assessments rỗng → như cũ.


# MA TRẬN 3 TẦNG verdict-aware (T7-3) tách sang app/orch/verdict.py (chuẩn PROD ≤400 LOC).
# gated._gated_txn nhánh 4a gọi disburse_decision(conn, args) → ('auto', reason) | ('human', None).


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
def disburse(conn: ConnLike, loan_id: str, amount: float = 0) -> Receipt:
    """[STUB vỏ] Giải ngân = ghi loans.status='disbursed' (D-21 write-back). Nhận conn wrapper
    cấp (SAME tx với claim). raw %s. Trả biên nhận {disbursed, loan_id, amount, asOf}."""
    with conn.cursor() as cur:
        cur.execute("UPDATE loans SET status='disbursed' WHERE loan_id=%s", (loan_id,))
        if cur.rowcount == 0:
            raise ValueError(f"loan '{loan_id}' không tồn tại")
    return {"disbursed": True, "loan_id": loan_id, "amount": amount, "asOf": _now()}


def _ops_disburse_inner(conn: ConnLike, **args: Any) -> Receipt:
    """[T12-3] Cầu nối GATED_TOOLS["ops_disburse"] → LAB `roles.operations.functions.ops_disburse`
    nguyên trạng (N1 — 0 sửa logic LAB). Lazy import (tránh vòng import module-level app.orch↔roles).

    KHÔNG cast/convert conn — LAB fn nhận `conn` gated cấp (ConnLike, `.cursor()`/`.commit()`/
    `.rollback()`), gọi y hệt interface D-18 `fn(conn, **kwargs)`. Bảng applications/disbursements
    CHƯA tồn tại (T12-2) → psycopg2 raise "relation does not exist" ngay câu SELECT applications
    ĐẦU TIÊN (TRƯỚC khi chạm BEGIN IMMEDIATE/commit nội bộ LAB) → gated._gated_txn bắt ở except
    cửa-cuối → rollback + gated_error 4-field. KHÔNG bypass phanh (xem seam note trong
    roles/operations/functions.py — LAB tx-model cần T12-2 portable-hoá trước khi chạy THẬT)."""
    from roles.operations.functions import ops_disburse

    return ops_disburse(conn, **args)  # type: ignore[return-value]


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
# except cửa-cuối GIỮ ở _gated_txn (helper KHÔNG bắt). SQL text 0 đổi (pure refactor).


def _save_receipt(cur: Any, out: Receipt, approval_id: Any, *, set_used_at: bool) -> None:
    """UPDATE receipt CÙNG tx (INVARIANT status='used' ⟺ receipt present — tách tx = money-doubling).

    KHÁC BIỆT giữ nguyên (advisor #1): `set_used_at` — claim ĐÃ set used_at lúc claim atomic (step-2)
    → False (chỉ SET receipt); auto INSERT set decided_at, used_at set ở ĐÂY → True. inner-run + enrich
    do CALLER (claim: raw out; auto: enrich auto_approved...) — KHÔNG flatten khác biệt vào core."""
    sql = (
        "UPDATE approvals SET receipt=%s, used_at=now() WHERE id=%s"
        if set_used_at
        else "UPDATE approvals SET receipt=%s WHERE id=%s"
    )
    cur.execute(sql, (json.dumps(out), approval_id))


def _branch_receipt_replay(conn: ConnLike, cur: Any, ctx: dict[str, Any]) -> _GatedResult | None:
    """1. Biên nhận cũ? → trả biên nhận, KHÔNG chạy lại (chống thực-thi-đôi §4.4). None = chưa từng."""
    cur.execute(
        "SELECT receipt FROM approvals WHERE conv_id=%s AND action=%s AND payload_hash=%s AND status='used' LIMIT 1",
        (ctx["conv_id"], ctx["action"], ctx["ph"]),
    )
    row = cur.fetchone()
    if row and row["receipt"] is not None:
        conn.commit()
        return _GatedResult({**row["receipt"], "hint": "Hành động này ĐÃ thực thi trước đó — đây là biên nhận."})
    return None


def _branch_claim(conn: ConnLike, cur: Any, ctx: dict[str, Any]) -> _GatedResult | None:
    """2. Phiếu approved? → CLAIM ATOMIC (used+used_at) rồi chạy (1 phiếu = đúng 1 lần). None = không claim."""
    cur.execute(
        "UPDATE approvals SET status='used', used_at=now() "
        "WHERE conv_id=%s AND action=%s AND payload_hash=%s AND status='approved' RETURNING id",
        (ctx["conv_id"], ctx["action"], ctx["ph"]),
    )
    claimed = cur.fetchone()  # rowcount 1 = claim được; None = không có/đã bị claim
    if not claimed:
        return None
    # inner chạy THẬT trên SAME conn (SAME tx) — ghi loans.status. claim ĐÃ set used_at lúc atomic
    # → _save_receipt set_used_at=False. out RAW (claim KHÔNG enrich — khác auto, advisor #1).
    out = GATED_TOOLS[ctx["action"]](conn, **ctx["args"])
    _save_receipt(cur, out, claimed["id"], set_used_at=False)
    conn.commit()  # claim + inner-write + receipt cùng COMMIT
    return _GatedResult(out, fresh_disburse=True)  # vừa giải ngân THẬT (claim) → mail hook b


def _branch_pending(conn: ConnLike, cur: Any, ctx: dict[str, Any]) -> _GatedResult | None:
    """3. Phiếu pending? → báo chờ, KHÔNG đẻ phiếu/card mới (idempotent). None = chưa có pending."""
    cur.execute(
        "SELECT id FROM approvals WHERE conv_id=%s AND action=%s AND payload_hash=%s AND status='pending' LIMIT 1",
        (ctx["conv_id"], ctx["action"], ctx["ph"]),
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


def _branch_auto(conn: ConnLike, cur: Any, ctx: dict[str, Any], reason: str) -> _GatedResult:
    """4a. AUTO-DUYỆT CÓ KIỂM SOÁT (T7-3): phiếu 'used' decided_by='auto-rule' + inner + receipt + card
    THÔNG BÁO CÙNG tx → chạy NGAY. Terminal (luôn trả result)."""
    conv_id, action, task_id, args, ph = ctx["conv_id"], ctx["action"], ctx["task_id"], ctx["args"], ctx["ph"]
    cur.execute(
        "INSERT INTO approvals (conv_id, task_id, action, payload, payload_hash, status, "
        "decided_by, decided_at, reason) "
        "VALUES (%s, %s, %s, %s, %s, 'used', 'auto-rule', now(), %s) RETURNING id",
        (conv_id, task_id or None, action, json.dumps(args), ph, reason),
    )
    auto_id = str(cur.fetchone()["id"])
    # ENRICH TRƯỚC gọi core (advisor #1 — auto out khác claim). auto set decided_at ở INSERT trên →
    # _run_and_receipt set_used_at=True (used_at set lúc receipt). Nhưng enrich phải TRÊN out của inner:
    inner_out = GATED_TOOLS[action](conn, **args)  # chạy THẬT (SAME tx) — ghi loans.status
    out: Receipt = {**inner_out, "auto_approved": True, "approved_by": "auto-rule", "note": reason}
    _save_receipt(cur, out, auto_id, set_used_at=True)  # auto set used_at ở đây (INSERT set decided_at)
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
    cur.execute(
        "INSERT INTO approvals (conv_id, task_id, action, payload, payload_hash, status) "
        "VALUES (%s, %s, %s, %s, %s, 'pending') RETURNING id",
        (conv_id, task_id or None, action, json.dumps(args), ph),
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


def _gated_txn(action: str, conv_id: str, task_id: str | None, args: dict[str, Any]) -> _GatedResult:
    """LÕI ĐỒNG BỘ — 1 conn, 1 tx, 4 bước, KHÔNG await bên trong (advisor #1). commit/rollback/close.

    T11-2 refactor: tách 5 nhánh → helper (0 đổi hành vi). GIỮ NGUYÊN: cross-owner guard TRƯỚC lock,
    advisory-lock đầu tx, thứ tự nhánh 1→2→3→auto/human, except cửa-cuối rollback. 33 money-test guard.
    """
    ph = payload_hash(action, args)
    conn = psycopg2.connect(DATABASE_URL)  # conn RIÊNG (mirror store/D-34 — KHÔNG mount pool adapter)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # GUARD CROSS-OWNER (T9-4, money-adjacent): ca creator KHÁCH → loan PHẢI thuộc hồ sơ creator.
            # TRƯỚC advisory-lock + 4-step (không phí lock/phiếu cho ca bị chặn). fail-closed. Ca bank →
            # qua như cũ. Chỉ disburse. (KHÔNG phải 1 trong 5 nhánh — early-exit thứ 6 giữ tại chỗ.)
            if action == "disburse":
                refusal = cross_owner_refusal(cur, conv_id, args.get("loan_id"))
                if refusal is not None:
                    conn.rollback()  # chưa ghi gì — rollback sạch, không giữ lock
                    return _GatedResult(refusal)

            # SERIALIZE per-key (chống race phiếu-rác): advisory-xact-lock deterministic (sha256, KHÔNG
            # hash() Python — PYTHONHASHSEED). tx-scoped → release ở commit/rollback. Chi tiết D-40.
            lock_key = int(hashlib.sha256(f"{conv_id}:{ph}".encode()).hexdigest()[:15], 16) & 0x7FFFFFFFFFFFFFFF
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))

            ctx = {"action": action, "conv_id": conv_id, "task_id": task_id, "args": args, "ph": ph}
            # Nhánh 1→2→3 điều-kiện (None = fall-through). Nhánh nào commit+return trong helper.
            for branch in (_branch_receipt_replay, _branch_claim, _branch_pending):
                result = branch(conn, cur, ctx)
                if result is not None:
                    return result

            # 4. MA TRẬN 3 TẦNG (T7-3): auto (dưới ngưỡng không-xấu / hồ-sơ XANH) vs human (còn lại).
            decision, reason = disburse_decision(conn, args)
            if decision == "auto":
                return _branch_auto(conn, cur, ctx, reason)
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
            result: _GatedResult = await asyncio.to_thread(_gated_txn, action, conv_id, task_id, args)
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
        # HOOK b (T9-2): mail giải ngân thành công — CHỈ khi vừa giải ngân THẬT (claim/auto), KHÔNG
        # replay. 1 điểm CHUNG cả 2 nhánh (handler post-commit) → không dup mail cho 1 receipt.
        # Chạy trên loop (handler async — to_thread trong _gated_txn không có loop cho create_task).
        if action == "disburse" and result.fresh_disburse:
            _notify_disbursed(conv_id, result.payload)
        return _text(result.payload)

    return handler


def _notify_disbursed(conv_id: str, receipt: dict[str, Any]) -> None:
    """Mail HOOK b (T9-2 + addendum HTML brand): giải ngân thành công. Plain fallback + HTML multipart.
    best-effort async (không chặn)."""
    from app.notify.email import render_email_html
    from app.notify.hooks import app_url, notify_conv_owner, owner_greeting

    amount = int(float(receipt.get("amount"))) if receipt.get("amount") else 0
    loan = receipt.get("loan_id", "")
    amount_str = f" số tiền {amount:,} VND" if amount else ""
    body = (
        f"Kính gửi anh/chị,\n\nKhoản vay {loan}{amount_str} của anh/chị đã được GIẢI NGÂN thành "
        f"công.\n\nTrân trọng,\nBANK Digital."
    )
    d = {
        "greeting_name": owner_greeting(conv_id),
        "loan_id": loan,
        "amount_vnd": amount,
        "decided_by": receipt.get("approved_by"),  # 'auto-rule' nếu auto-duyệt
        "ref": loan,
        "app_url": app_url(),
    }
    html_body = render_email_html("disbursed", d)
    amount_disp = f"{amount:,}".replace(",", ".")
    subject = f"💸 Giải ngân thành công {amount_disp} ₫ — BANK Digital"
    notify_conv_owner(conv_id, subject, body, html_body)


def _emit_approval(emit_data: dict[str, Any]) -> None:
    """SSE bước 4 (canvas-present §6). 2 path:
    - AUTO (T5-2', emit_data['auto']): CHỈ emit card thông báo (document) — ĐÃ chạy, KHÔNG
      approval.pending, KHÔNG waiting_approval (không chờ).
    - PENDING (S3): card approval + approval.pending + conversation.status=waiting_approval.
    Lazy import (SSE ≠ tx). Lỗi SSE KHÔNG fail (phiếu đã commit — fire-and-forget)."""
    try:
        from app.orch.store import _card_to_dict
        from app.sse.emit import emit, emit_conversation_status

        card = _card_to_dict(emit_data["card"])
        emit(emit_data["conv_id"], "card", {"card": card})
        if emit_data.get("auto"):
            return  # auto-path: đã chạy xong — chỉ card thông báo, không tín hiệu chờ duyệt
        emit(
            emit_data["conv_id"],
            "approval.pending",
            {"phieu": {"id": emit_data["approval_id"], "action": emit_data["action"], "status": "pending"}},
        )
        emit_conversation_status(emit_data["conv_id"], "waiting_approval")
    except Exception:  # noqa: BLE001
        log.exception("emit approval lỗi (bỏ qua)")  # T11-2: full traceback (fire-and-forget, không fail)


def _text(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}
