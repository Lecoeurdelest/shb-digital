"""[BACKEND] Test T12-3b — ops_disburse chạy THẬT dưới gated (bridge OpsConnProxy + money-invariant).

Money-path: phiếu → approve → claim → disbursements ghi ĐÚNG 1 lần + phiếu 'used' ⟺ receipt.
Replay sau success → KHÔNG ghi lần 2. BLOCKED (app rejected) → phiếu KHÔNG 'used' (raise→rollback→
retryable), 0 disbursement row. disburse (đường cũ) 43 money-test giữ (test riêng).
@requires_test_db: ghi applications/disbursements (destructive) → gate test-db riêng.
"""

from __future__ import annotations

import json
from uuid import uuid4

import psycopg2
import psycopg2.extras
import pytest

from app.db.config import DATABASE_URL
from app.orch import registry
from app.orch.gated import gated, payload_hash
from app.sse import bus
from app.sse import emit as emit_mod

from .conftest import requires_test_db


def _payload(env: dict) -> dict:
    return json.loads(env["content"][0]["text"])


@pytest.fixture
def _reset_sse():
    bus.reset()
    emit_mod.reset()
    yield
    bus.reset()
    emit_mod.reset()


def _raw(sql: str, args: tuple = ()) -> list:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, args)
            return cur.fetchall() if cur.description else []
    finally:
        conn.close()


def _mk_app(app_id: str, *, status="ready_to_disburse", credit=1, legal=1, human="not_required", amount=400_000_000):
    _raw(
        "INSERT INTO applications (id, owner_id, product_id, loan_amount_vnd, loan_type, status, "
        "credit_ok, legal_ok, human_approval, created_at) "
        "VALUES (%s,'C004','P1',%s,'consumer',%s,%s,%s,%s,now()::text) "
        "ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, credit_ok=EXCLUDED.credit_ok, "
        "legal_ok=EXCLUDED.legal_ok, human_approval=EXCLUDED.human_approval, loan_amount_vnd=EXCLUDED.loan_amount_vnd",
        (app_id, amount, status, credit, legal, human),
    )


def _rm_app(app_id: str, conv: str) -> None:
    _raw("DELETE FROM disbursements WHERE application_id=%s", (app_id,))
    _raw("DELETE FROM applications WHERE id=%s", (app_id,))
    _raw("DELETE FROM approvals WHERE conv_id=%s", (conv,))


def _approve(conv: str, ph: str) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE approvals SET status='approved' WHERE conv_id=%s AND action='ops_disburse' "
            "AND payload_hash=%s AND status='pending'",
            (conv, ph),
        )
        n = cur.rowcount
    conn.close()
    return n


@requires_test_db
@pytest.mark.asyncio
async def test_ops_disburse_approve_claim_writes_once_invariant(_reset_sse):
    """phiếu → approve → claim → disbursements ghi 1 row + phiếu 'used' + receipt (invariant)."""
    conv = f"opsd-{uuid4()}"
    app_id = f"APPT{uuid4().hex[:6]}"
    _mk_app(app_id, amount=400_000_000)
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    h = gated("ops_disburse", None)
    args = {"application_id": app_id, "amount_vnd": 400_000_000}
    ph = payload_hash("ops_disburse", args)
    try:
        out1 = _payload(await h(args))
        assert out1["code"] == "approval_required"  # LUÔN human (không auto)
        assert _approve(conv, ph) == 1
        out2 = _payload(await h(args))  # claim → chạy THẬT
        assert out2.get("found") is True
        assert out2["item"]["disbursementId"]  # disbursement THẬT
        # disbursements ghi ĐÚNG 1 row
        dsb = _raw("SELECT * FROM disbursements WHERE application_id=%s AND status='executed'", (app_id,))
        assert len(dsb) == 1
        # invariant: phiếu 'used' ⟺ receipt present
        appr = _raw("SELECT status, receipt FROM approvals WHERE conv_id=%s AND payload_hash=%s", (conv, ph))
        assert appr[0]["status"] == "used" and appr[0]["receipt"] is not None
    finally:
        _rm_app(app_id, conv)


@requires_test_db
@pytest.mark.asyncio
async def test_ops_disburse_replay_no_second_row(_reset_sse):
    """Gọi lại SAU success → receipt-replay, KHÔNG ghi disbursement lần 2 (chống chi đôi)."""
    conv = f"opsd-r-{uuid4()}"
    app_id = f"APPR{uuid4().hex[:6]}"
    _mk_app(app_id, amount=400_000_000)
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    h = gated("ops_disburse", None)
    args = {"application_id": app_id, "amount_vnd": 400_000_000}
    ph = payload_hash("ops_disburse", args)
    try:
        await h(args)
        _approve(conv, ph)
        await h(args)  # chạy thật
        await h(args)  # gọi LẠI → replay (không ghi lần 2)
        dsb = _raw("SELECT * FROM disbursements WHERE application_id=%s AND status='executed'", (app_id,))
        assert len(dsb) == 1  # vẫn ĐÚNG 1 row (không chi đôi)
    finally:
        _rm_app(app_id, conv)


@requires_test_db
@pytest.mark.asyncio
async def test_ops_disburse_blocked_app_phieu_not_used_retryable(_reset_sse):
    """MONEY-INVARIANT: app rejected → claim chạy inner → block → RAISE → gated rollback →
    phiếu KHÔNG 'used' (về 'approved', retry được), 0 disbursement row. KHÔNG consume phiếu oan."""
    conv = f"opsd-b-{uuid4()}"
    app_id = f"APPB{uuid4().hex[:6]}"
    _mk_app(app_id, status="rejected", credit=0, legal=0, human="denied", amount=200_000_000)
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    h = gated("ops_disburse", None)
    args = {"application_id": app_id, "amount_vnd": 200_000_000}
    ph = payload_hash("ops_disburse", args)
    try:
        await h(args)  # pending
        _approve(conv, ph)  # admin lỡ duyệt phiếu (nhưng app vẫn rejected)
        out = _payload(await h(args))  # claim → inner block → RAISE → rollback
        assert out["code"] == "gated_error"  # raise → wrapper 4-field (message = lý do chặn)
        assert out["retryable"] is True
        # phiếu KHÔNG bị consume (rollback → về 'approved'), 0 disbursement
        appr = _raw("SELECT status FROM approvals WHERE conv_id=%s AND payload_hash=%s", (conv, ph))
        assert appr[0]["status"] == "approved"  # KHÔNG 'used' — money-invariant giữ
        dsb = _raw("SELECT * FROM disbursements WHERE application_id=%s", (app_id,))
        assert len(dsb) == 0  # KHÔNG ghi gì
    finally:
        _rm_app(app_id, conv)


@requires_test_db
@pytest.mark.asyncio
async def test_ops_disburse_dup_check_fires_through_proxy_no_double_pay(_reset_sse):
    """MONEY (advisor): LAB dup-check `already_disbursed` là lá chắn DUY NHẤT chống chi-đôi CROSS-CONV
    (gated replay chỉ conv-scoped). Pre-insert 1 disbursement 'executed' cho app → chạy trọn gated flow
    (pending→approve→claim) từ conv KHÁC → inner dup-check qua PROXY (RealDictCursor) phải fire →
    disburse_blocked → bridge RAISE → rollback → 0 row MỚI + phiếu KHÔNG 'used'. Chứng minh proxy đọc
    đúng + exception-map + raise-on-blocked compose trên lớp idempotency THỨ HAI."""
    conv = f"opsd-dup-{uuid4()}"
    app_id = f"APPD{uuid4().hex[:6]}"
    _mk_app(app_id, amount=400_000_000)
    # đã có 1 disbursement executed (như thể conv khác đã chi trước)
    _raw(
        "INSERT INTO disbursements (id, application_id, amount_vnd, beneficiary, status, executed_at, receipt_code) "
        "VALUES (%s,%s,%s,'X','executed',now()::text,'RC-PRE')",
        (f"DSBPRE{uuid4().hex[:4]}", app_id, 400_000_000),
    )
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    h = gated("ops_disburse", None)
    args = {"application_id": app_id, "amount_vnd": 400_000_000}
    ph = payload_hash("ops_disburse", args)
    try:
        await h(args)  # pending (conv này chưa có receipt → không replay)
        _approve(conv, ph)
        out = _payload(await h(args))  # claim → inner dup-check fire → raise → rollback
        assert out["code"] == "gated_error"  # raise (already_disbursed) → 4-field
        # KHÔNG ghi row MỚI (vẫn đúng 1 = row pre-insert), phiếu KHÔNG 'used'
        dsb = _raw("SELECT * FROM disbursements WHERE application_id=%s AND status='executed'", (app_id,))
        assert len(dsb) == 1  # chỉ row pre-insert, KHÔNG chi đôi
        appr = _raw("SELECT status FROM approvals WHERE conv_id=%s AND payload_hash=%s", (conv, ph))
        assert appr[0]["status"] == "approved"  # phiếu KHÔNG consume → không double-pay
    finally:
        _rm_app(app_id, conv)


# ── read-scope (c): khách chỉ tra application CỦA MÌNH ───────────────────────


@requires_test_db
def test_ops_read_scope_customer_blocks_other_application():
    """T12-3b (c): ca khách C001 tra ops_app_get application của owner KHÁC (C004) → refuse
    not_your_data (read_scope application_id → applications.owner). Tightening lỗ pipeline."""
    import inspect

    from roles.operations import functions as O

    from app.mount.mount_role import _sig_hint, _text, run_labpack_fn

    app_id = f"APPX{uuid4().hex[:6]}"
    _mk_app(app_id)  # owner C004
    # ca khách C001 — conversations.id là uuid → dùng str(uuid4())
    conv = str(uuid4())
    _raw(
        "INSERT INTO conversations (id, user_id, title, status, created_at) VALUES (%s,'c001','t','idle',now())",
        (conv,),
    )
    registry.CTX_CONV.set(conv)
    fn = O.REGISTRY["ops_app_get"]
    known = set(inspect.signature(fn).parameters) - {"conn"}
    hint = _sig_hint(O.SCHEMAS, "ops_app_get")
    try:
        out = _payload(
            _text(run_labpack_fn(fn, "ops_app_get", {"application_id": app_id}, known, hint, apply_read_scope=True))
        )
        assert out["code"] == "not_your_data"  # C001 tra app của C004 → chặn
    finally:
        _raw("DELETE FROM conversations WHERE id::text=%s", (conv,))
        _rm_app(app_id, conv)
