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

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            return cross_owner_refusal(cur, conv_id, loan_id)
    finally:
        conn.close()


@requires_db
def test_cross_owner_customer_refused():

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
        assert _guard(conv, lid) is None
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM loans WHERE loan_id=%s", (lid,))
        conn.close()
        _cleanup(u, conv, "C901")


@requires_db
def test_bank_creator_any_loan_allowed():

    conv = _real_conv("admin")  # admin = bank, role='admin'
    try:
        assert _guard(conv, "L007") is None
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM conversations WHERE id::text=%s", (conv,))
        conn.close()


@requires_db
def test_creator_owner_null_refused():

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

    u = "c9nx_" + uuid.uuid4().hex[:6]
    _mk_customer(u, "C901")
    conv = _real_conv(u)
    try:
        r = _guard(conv, "LNOEXIST999")
        assert r is not None and r["code"] == "not_your_loan"
    finally:
        _cleanup(u, conv, "C901")


def test_db_error_refused(monkeypatch):

    class _BoomCur:
        def execute(self, *a):
            raise psycopg2.OperationalError("database failure")

    r = cross_owner_refusal(_BoomCur(), "any-conv", "L007")
    assert r is not None and r["code"] == "not_your_loan"


@requires_test_db
def test_gated_txn_cross_owner_no_ticket():

    u = "c9gtx_" + uuid.uuid4().hex[:6]
    _mk_customer(u, "C901")
    conv = _real_conv(u)
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    try:
        result = _gated_txn("disburse", conv, None, {"loan_id": "L007", "amount": 100_000_000})
        payload = result.payload
        assert payload["code"] == "not_your_loan"

        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM approvals WHERE conv_id=%s", (conv,))
            assert cur.fetchone()[0] == 0
        conn.close()
    finally:
        _cleanup(u, conv, "C901")


@requires_test_db
def test_gated_txn_bank_disburse_unchanged():

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

        assert result.payload.get("code") != "not_your_loan"
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("UPDATE loans SET status=%s WHERE loan_id=%s", (orig_status, lid))
            cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv,))
            cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv,))
            cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv,))
        conn.close()
