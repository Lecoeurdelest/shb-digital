"""[BACKEND] Test T9-4 fix — cross-owner disburse guard (money-adjacent).

Khách A KHÔNG được kích hoạt giải ngân loan khách B. Guard TRƯỚC 4-step/advisory-lock.
CRITICAL: dùng conversation ROW THẬT (conv_id giả → JOIN no-op → guard bỏ qua = false-green).

Repro tester: c9test1 (owner C901) giải ngân L007 (owner B001) → not_your_loan.
Ma trận: cross-owner khách REFUSE · own-loan khách OK · bank mọi loan OK · creator-owner-NULL
REFUSE · loan-không-tồn-tại REFUSE · DB-lỗi REFUSE (fail-closed).
"""

from __future__ import annotations

import uuid

import psycopg2
import psycopg2.extras

from app.db.config import DATABASE_URL
from app.orch import registry
from app.orch.disburse_guard import cross_owner_refusal
from app.orch.gated import _gated_txn

from .conftest import requires_db, requires_test_db


def _real_conv(user_id: str) -> str:
    """Conversation ROW THẬT (creator = user_id). Guard JOIN conversations.user_id → users → cần row thật."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (user_id, title, status, created_at) "
                "VALUES (%s,'t','idle',now()) RETURNING id::text",
                (user_id,),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def _mk_customer(username: str, owner_id: str | None) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, pass_hash, role, owner_id) VALUES (%s,'x','customer',%s) "
            "ON CONFLICT (username) DO UPDATE SET owner_id=EXCLUDED.owner_id",
            (username, owner_id),
        )
        if owner_id:
            cur.execute(
                "INSERT INTO customers (id, full_name, monthly_income) VALUES (%s,'Test',1e7) "
                "ON CONFLICT (id) DO NOTHING",
                (owner_id,),
            )
    conn.close()


def _cleanup(username: str, conv: str, owner_id: str | None) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv,))
        cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv,))
        cur.execute("DELETE FROM users WHERE username=%s", (username,))
        if owner_id and owner_id.startswith("C9"):
            cur.execute("DELETE FROM customers WHERE id=%s", (owner_id,))
    conn.close()


def _guard(conv_id: str, loan_id: str) -> dict | None:
    """Gọi guard trực tiếp qua cur thật (JOIN row thật)."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            return cross_owner_refusal(cur, conv_id, loan_id)
    finally:
        conn.close()


# ── guard logic trực tiếp (conv row THẬT) ────────────────────────────────────


@requires_db
def test_cross_owner_customer_refused():
    """REPRO tester: khách C901 giải ngân L007 (owner B001) → not_your_loan REFUSE."""
    u = "c9test1_" + uuid.uuid4().hex[:6]
    _mk_customer(u, "C901")
    conv = _real_conv(u)
    try:
        r = _guard(conv, "L007")  # L007 owner=B001 ≠ C901
        assert r is not None and r["code"] == "not_your_loan"
    finally:
        _cleanup(u, conv, "C901")


@requires_db
def test_own_loan_customer_allowed():
    """Khách giải ngân loan CỦA MÌNH → None (cho qua). Seed loan owner=C901."""
    u = "c9own_" + uuid.uuid4().hex[:6]
    _mk_customer(u, "C901")
    conv = _real_conv(u)
    lid = "L9" + uuid.uuid4().hex[:4]
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    conn.cursor().execute(
        "INSERT INTO loans (loan_id, owner_id, principal, outstanding, monthly_payment, status) "
        "VALUES (%s,'C901',1e8,1e8,1e6,'active')",
        (lid,),
    )
    conn.close()
    try:
        assert _guard(conv, lid) is None  # đúng owner → cho qua
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM loans WHERE loan_id=%s", (lid,))
        conn.close()
        _cleanup(u, conv, "C901")


@requires_db
def test_bank_creator_any_loan_allowed():
    """Ca creator = BANK (admin) → None (qua mọi loan — bank thao tác hộ mọi khách)."""
    conv = _real_conv("admin")  # admin = bank, role='admin'
    try:
        assert _guard(conv, "L007") is None  # bank → không áp guard
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM conversations WHERE id::text=%s", (conv,))
        conn.close()


@requires_db
def test_creator_owner_null_refused():
    """Khách CHƯA có hồ sơ (owner_id NULL) mà đòi giải ngân → fail-closed REFUSE."""
    u = "c9null_" + uuid.uuid4().hex[:6]
    _mk_customer(u, None)
    conv = _real_conv(u)
    try:
        r = _guard(conv, "L007")
        assert r is not None and r["code"] == "not_your_loan"
    finally:
        _cleanup(u, conv, None)


@requires_db
def test_loan_not_exist_refused():
    """Khách giải ngân loan KHÔNG tồn tại → REFUSE (không tồn tại = không thuộc hồ sơ)."""
    u = "c9nx_" + uuid.uuid4().hex[:6]
    _mk_customer(u, "C901")
    conv = _real_conv(u)
    try:
        r = _guard(conv, "LNOEXIST999")
        assert r is not None and r["code"] == "not_your_loan"
    finally:
        _cleanup(u, conv, "C901")


def test_db_error_refused(monkeypatch):
    """DB lỗi khi lookup → refuse fail-closed (money-adjacent — không cho qua khi không chắc)."""

    class _BoomCur:
        def execute(self, *a):
            raise psycopg2.OperationalError("db chết")

    r = cross_owner_refusal(_BoomCur(), "any-conv", "L007")
    assert r is not None and r["code"] == "not_your_loan"


# ── E2E qua _gated_txn: refuse KHÔNG tạo phiếu (TRƯỚC 4-step) ─────────────────


@requires_test_db  # _gated_txn disburse ghi loans.status → test-db riêng (siết money-write)
def test_gated_txn_cross_owner_no_ticket():
    """Qua _gated_txn: cross-owner → not_your_loan + KHÔNG tạo phiếu approvals (refuse trước 4-step)."""
    u = "c9gtx_" + uuid.uuid4().hex[:6]
    _mk_customer(u, "C901")
    conv = _real_conv(u)
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    try:
        result = _gated_txn("disburse", conv, None, {"loan_id": "L007", "amount": 100_000_000})
        payload = result.payload
        assert payload["code"] == "not_your_loan"
        # KHÔNG tạo phiếu (guard trước bước 4)
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM approvals WHERE conv_id=%s", (conv,))
            assert cur.fetchone()[0] == 0
        conn.close()
    finally:
        _cleanup(u, conv, "C901")


@requires_test_db
def test_gated_txn_bank_disburse_unchanged():
    """Đối chứng: ca bank giải ngân L007 qua _gated_txn → KHÔNG bị guard chặn (tạo phiếu/auto như cũ)."""
    conv = _real_conv("admin")
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    lid = "L007"
    orig_status = None
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM loans WHERE loan_id=%s", (lid,))
        orig_status = cur.fetchone()[0]
    conn.close()
    try:
        result = _gated_txn("disburse", conv, None, {"loan_id": lid, "amount": 100_000_000})
        # bank + amount<500tr → auto-duyệt (KHÔNG not_your_loan)
        assert result.payload.get("code") != "not_your_loan"
    finally:
        # teardown: khôi phục loans.status (disburse ghi 'disbursed' — không pollute seed)
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("UPDATE loans SET status=%s WHERE loan_id=%s", (orig_status, lid))
            cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv,))
            cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv,))
            cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv,))
        conn.close()
