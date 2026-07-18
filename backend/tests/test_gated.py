"""[BACKEND] Test phanh (T3-1): payload_hash + wrapper 4 nhánh + disburse + card approval.

TÂM ĐIỂM. conv_id unique per-test (advisor — tránh pollution DB persist). Nhánh 2 (claim) set
status='approved' trực tiếp (thay admin decide — resume là T3-2).
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import psycopg2
import pytest

from app.db.config import DATABASE_URL
from app.orch import registry
from app.orch.gated import GATED_WHITELIST, gated, payload_hash
from app.sse import bus, emit

from .conftest import requires_db


def _payload(env: dict) -> dict:
    return json.loads(env["content"][0]["text"])


def _loan_status(lid: str) -> str | None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM loans WHERE loan_id=%s", (lid,))
            r = cur.fetchone()
            return r[0] if r else None
    finally:
        conn.close()


def _set_loan(lid: str, st: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE loans SET status=%s WHERE loan_id=%s", (st, lid))
        conn.commit()
    finally:
        conn.close()


def _approve(conv: str, action: str, ph: str) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE approvals SET status='approved' WHERE conv_id=%s AND action=%s "
                "AND payload_hash=%s AND status='pending'",
                (conv, action, ph),
            )
            n = cur.rowcount
        conn.commit()
        return n
    finally:
        conn.close()


def _count_approvals(conv: str) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM approvals WHERE conv_id=%s", (conv,))
            return cur.fetchone()[0]
    finally:
        conn.close()


# ── payload_hash equivalence (advisor: cả coverage) ─────────────────────────


def test_payload_hash_int_float_order_same():
    h1 = payload_hash("disburse", {"loan_id": "L001", "amount": 5000000000})
    h2 = payload_hash("disburse", {"amount": 5e9, "loan_id": "L001"})  # order + 5e9≡5000000000
    assert h1 == h2


def test_payload_hash_drops_non_biz_fields():
    h1 = payload_hash("disburse", {"loan_id": "L001", "amount": 5000000000})
    h2 = payload_hash("disburse", {"loan_id": "L001", "amount": 5000000000, "ts": "2026-01-01"})
    assert h1 == h2  # ts phi-nghiệp-vụ bị bỏ


def test_payload_hash_drops_none():
    h1 = payload_hash("disburse", {"loan_id": "L001", "amount": 5000000000})
    h2 = payload_hash("disburse", {"loan_id": "L001", "amount": 5000000000, "extra": None})
    assert h1 == h2  # None bị bỏ


def test_payload_hash_different_amount_different_hash():
    h5 = payload_hash("disburse", {"loan_id": "L001", "amount": 5000000000})  # 5 tỷ
    h1 = payload_hash("disburse", {"loan_id": "L001", "amount": 1000000000})  # 1 tỷ
    assert h5 != h1  # duyệt 1 tỷ gọi 5 tỷ → hash khác → không lách


def test_disburse_in_whitelist():
    assert "disburse" in GATED_WHITELIST


# ── wrapper 4 nhánh (cần DB) ────────────────────────────────────────────────


@pytest.fixture
def _reset_sse():
    bus.reset()
    emit.reset()
    yield
    bus.reset()
    emit.reset()


@requires_db
@pytest.mark.asyncio
async def test_branch1_first_call_creates_pending_loans_unchanged(_reset_sse):
    conv = f"gated-b1-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    h = gated("disburse", None)
    args = {"loan_id": "L001", "amount": 5000000000}
    out = _payload(await h(args))
    assert out["code"] == "approval_required"
    assert out["retryable"] is False
    assert _loan_status("L001") == "active"  # loans KHÔNG đổi (chưa duyệt)
    assert _count_approvals(conv) == 1  # 1 phiếu pending


@requires_db
@pytest.mark.asyncio
async def test_branch4_pending_idempotent_no_new(_reset_sse):
    conv = f"gated-b4-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    h = gated("disburse", None)
    args = {"loan_id": "L001", "amount": 5000000000}
    await h(args)  # tạo pending
    out = _payload(await h(args))  # gọi lại lúc pending
    assert out["code"] == "approval_pending"
    assert _count_approvals(conv) == 1  # KHÔNG đẻ phiếu mới


@requires_db
@pytest.mark.asyncio
async def test_branch2_approved_claim_executes_disbursed_receipt(_reset_sse):
    conv = f"gated-b2-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    h = gated("disburse", None)
    args = {"loan_id": "L001", "amount": 5000000000}
    ph = payload_hash("disburse", args)
    await h(args)  # pending
    assert _approve(conv, "disburse", ph) == 1  # admin duyệt (thay resume T3-2)
    out = _payload(await h(args))  # gọi lại → claim → chạy
    assert out["disbursed"] is True
    assert _loan_status("L001") == "disbursed"  # loans ghi status
    # phiếu used + receipt (invariant status='used' ⟺ receipt present)
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, receipt FROM approvals WHERE conv_id=%s AND payload_hash=%s",
                (conv, ph),
            )
            status, receipt = cur.fetchone()
    finally:
        conn.close()
    assert status == "used"
    assert receipt is not None
    _set_loan("L001", "active")


@requires_db
@pytest.mark.asyncio
async def test_branch1_receipt_no_double_execute(_reset_sse):
    """Gọi lại SAU thành công → biên nhận cũ, KHÔNG chạy lại (chống thực-thi-đôi)."""
    conv = f"gated-b1r-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    h = gated("disburse", None)
    args = {"loan_id": "L001", "amount": 5000000000}
    ph = payload_hash("disburse", args)
    await h(args)
    _approve(conv, "disburse", ph)
    await h(args)  # chạy thật → disbursed
    _set_loan("L001", "active")  # reset — nếu chạy LẠI sẽ thành disbursed
    out = _payload(await h(args))  # gọi lại sau xong → biên nhận
    assert "biên nhận" in out.get("hint", "")
    assert _loan_status("L001") == "active"  # KHÔNG chạy lại (giữ active)


# ── card approval vỏ-sinh + SSE ─────────────────────────────────────────────


@requires_db
@pytest.mark.asyncio
async def test_card_approval_vo_sinh_sse(_reset_sse):
    conv = f"gated-card-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    q = bus.subscribe(conv)
    h = gated("disburse", None)
    await h({"loan_id": "L001", "amount": 5000000000})
    evs = []
    while not q.empty():
        evs.append(q.get_nowait())
    types = [e["type"] for e in evs]
    assert "card" in types
    assert "approval.pending" in types
    assert "conversation.status" in types
    card = next(e for e in evs if e["type"] == "card")["data"]["card"]
    assert card["type"] == "approval"  # vỏ-sinh (NGOÀI present enum §6)
    assert card["id"]  # id vỏ-inject
    assert card["options"] == ["Duyệt", "Từ chối"]
    status = next(e for e in evs if e["type"] == "conversation.status")["data"]["status"]
    assert status == "waiting_approval"


@requires_db
@pytest.mark.asyncio
async def test_disburse_loan_not_found_error(_reset_sse):
    """disburse loan không tồn tại (sau approved) → error 4-field (inner raise → rollback)."""
    conv = f"gated-nf-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    h = gated("disburse", None)
    args = {"loan_id": "NONEXISTENT", "amount": 1000}
    ph = payload_hash("disburse", args)
    await h(args)  # pending
    _approve(conv, "disburse", ph)
    out = _payload(await h(args))  # claim → inner raise (loan không có) → rollback → gated_error
    assert out["code"] == "gated_error"
    # rollback: phiếu KHÔNG bị used (claim undone) → vẫn approved (retry sạch)
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM approvals WHERE conv_id=%s AND payload_hash=%s", (conv, ph))
            assert cur.fetchone()[0] == "approved"  # claim rollback → phiếu về approved
    finally:
        conn.close()


@requires_db
@pytest.mark.asyncio
async def test_concurrent_claim_no_spurious_ticket(_reset_sse):
    """RACE (architect fix advisory-lock): 2 gọi disburse ĐỒNG THỜI khi phiếu đã approved →
    ĐÚNG 1 claim (1 used) + KHÔNG phiếu-rác (0 pending giả). advisory-lock serialize per-key:
    con thua chờ con thắng commit → thấy used → không đẻ phiếu bước 4. Tester finding fixed."""
    conv = f"gated-race-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    h = gated("disburse", None)
    args = {"loan_id": "L001", "amount": 5000000000}
    ph = payload_hash("disburse", args)
    await h(args)  # pending
    _approve(conv, "disburse", ph)  # approved sẵn
    # RACE: 2 gọi đồng thời
    await asyncio.gather(h(args), h(args), return_exceptions=True)
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM approvals WHERE conv_id=%s AND status='used'", (conv,))
            used = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM approvals WHERE conv_id=%s AND status='pending'", (conv,))
            pending = cur.fetchone()[0]
    finally:
        conn.close()
    assert used == 1, f"đúng 1 claim (money invariant), got used={used}"
    assert pending == 0, f"KHÔNG phiếu-rác (advisory-lock fix), got pending={pending}"
    assert _loan_status("L001") == "disbursed"  # đúng 1 disbursed
    _set_loan("L001", "active")
