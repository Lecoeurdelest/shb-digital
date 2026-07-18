"""[BACKEND] Test FIX E — READ-scope guard tầng mount (ca KHÁCH chỉ tra hồ sơ CỦA MÌNH).

Lỗ hổng PROD (tester): khách route Credit → credit_assess(owner khác) → DSCR khách khác leak.
CRITICAL: conversation ROW THẬT (conv_id giả → JOIN no-op → guard bỏ qua = false-green — như FIX A).

Ma trận ca KHÁCH (owner C901): credit_assess owner-khác REFUSE · own OK · cust_search REFUSE ·
cust_get id-khác REFUSE · loan_id người-khác REFUSE · classify chính-mình OK · calc OK ·
multi-arg (owner mình + collateral khác) REFUSE (kiểm CẢ arg) · owner-NULL REFUSE.
Ca BANK: mọi tool PASS (0 đổi). DB-lỗi → REFUSE fail-closed.
"""

from __future__ import annotations

import uuid

import psycopg2

from app.db.config import DATABASE_URL
from app.mount.read_scope import read_scope_refusal

from .conftest import requires_db


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
                "INSERT INTO customers (id, full_name, monthly_income) VALUES (%s,'T',1e7) ON CONFLICT DO NOTHING",
                (owner_id,),
            )
    conn.close()


def _cleanup(username: str, conv: str, owner_id: str | None) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv,))
        cur.execute("DELETE FROM users WHERE username=%s", (username,))
        if owner_id and owner_id.startswith("C9"):
            cur.execute("DELETE FROM customers WHERE id=%s", (owner_id,))
    conn.close()


def _chk(conv: str, tool: str, args: dict) -> str:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        r = read_scope_refusal(conn, conv, tool, args)
        return r["code"] if r else "PASS"
    finally:
        conn.close()


# ── ca KHÁCH (owner C901) ────────────────────────────────────────────────────


@requires_db
def test_customer_credit_assess_other_owner_refused():
    """REPRO tester: khách C901 → credit_assess(owner_id='C001') → not_your_data (KHÔNG leak DSCR C001)."""
    u = "t9prod1_" + uuid.uuid4().hex[:6]
    _mk_customer(u, "C901")
    conv = _real_conv(u)
    try:
        assert _chk(conv, "credit_assess", {"owner_id": "C001"}) == "not_your_data"
    finally:
        _cleanup(u, conv, "C901")


@requires_db
def test_customer_own_owner_allowed():
    """Khách tra hồ sơ CHÍNH MÌNH (owner_id=C901) → PASS."""
    u = "e_own_" + uuid.uuid4().hex[:6]
    _mk_customer(u, "C901")
    conv = _real_conv(u)
    try:
        assert _chk(conv, "credit_assess", {"owner_id": "C901"}) == "PASS"
    finally:
        _cleanup(u, conv, "C901")


@requires_db
def test_customer_cust_search_refused():
    """cust_search (liệt kê người khác) → refuse thẳng cho ca khách."""
    u = "e_srch_" + uuid.uuid4().hex[:6]
    _mk_customer(u, "C901")
    conv = _real_conv(u)
    try:
        assert _chk(conv, "cust_search", {"q": "Nguyen"}) == "not_your_data"
    finally:
        _cleanup(u, conv, "C901")


@requires_db
def test_customer_cust_get_other_id_refused():
    """cust_get(id='C001') (id khác) → refuse; id chính mình → PASS."""
    u = "e_get_" + uuid.uuid4().hex[:6]
    _mk_customer(u, "C901")
    conv = _real_conv(u)
    try:
        assert _chk(conv, "cust_get", {"id": "C001"}) == "not_your_data"
        assert _chk(conv, "cust_get", {"id": "C901"}) == "PASS"
    finally:
        _cleanup(u, conv, "C901")


@requires_db
def test_customer_loan_id_other_owner_refused():
    """loan_id thuộc owner khác → refuse (resolve loans.owner_id != C901)."""
    u = "e_loan_" + uuid.uuid4().hex[:6]
    _mk_customer(u, "C901")
    conv = _real_conv(u)
    try:
        # L006 owner=C003 (seed) ≠ C901 → refuse
        assert _chk(conv, "credit_cic_get", {"loan_id": "L006"}) == "not_your_data"
    finally:
        _cleanup(u, conv, "C901")


@requires_db
def test_customer_classify_self_allowed():
    """legal_classify_profile(owner_id=C901) chính mình → PASS (flow T9-4 khách classify mình)."""
    u = "e_cls_" + uuid.uuid4().hex[:6]
    _mk_customer(u, "C901")
    conv = _real_conv(u)
    try:
        assert _chk(conv, "legal_classify_profile", {"owner_id": "C901", "loan_amount_vnd": 1e8}) == "PASS"
    finally:
        _cleanup(u, conv, "C901")


@requires_db
def test_customer_calc_no_identifier_allowed():
    """Tool KHÔNG đụng arg định danh (calc) → PASS."""
    u = "e_calc_" + uuid.uuid4().hex[:6]
    _mk_customer(u, "C901")
    conv = _real_conv(u)
    try:
        assert _chk(conv, "calc", {"expr": "1+1"}) == "PASS"
    finally:
        _cleanup(u, conv, "C901")


@requires_db
def test_customer_multi_arg_checks_all():
    """SHIP-BREAKER #2: owner_id=C901 (mình) NHƯNG collateral_id owner khác → refuse (kiểm CẢ arg)."""
    u = "e_multi_" + uuid.uuid4().hex[:6]
    _mk_customer(u, "C901")
    conv = _real_conv(u)
    # seed 1 collateral owner khác (B001)
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    conn.cursor().execute(
        "INSERT INTO collaterals (id, owner_id, type, appraised_value, docs_status) "
        "VALUES ('COL_OTHER','B001','nhà',1e9,'complete') ON CONFLICT DO NOTHING"
    )
    conn.close()
    try:
        r = _chk(conv, "legal_check_docs", {"owner_id": "C901", "collateral_id": "COL_OTHER"})
        assert r == "not_your_data"  # owner khớp nhưng collateral khác owner → vẫn refuse
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM collaterals WHERE id='COL_OTHER'")
        conn.close()
        _cleanup(u, conv, "C901")


@requires_db
def test_customer_owner_null_refused():
    """Khách CHƯA hồ sơ (owner NULL) gọi tool định danh → refuse (MAIN inject bảo present_form)."""
    u = "e_null_" + uuid.uuid4().hex[:6]
    _mk_customer(u, None)
    conv = _real_conv(u)
    try:
        assert _chk(conv, "credit_assess", {"owner_id": "C001"}) == "not_your_data"
        assert _chk(conv, "calc", {"expr": "1"}) == "PASS"  # tool không định danh vẫn qua
    finally:
        _cleanup(u, conv, None)


# ── ca BANK → 0 đổi (regression) ─────────────────────────────────────────────


@requires_db
def test_bank_creator_all_tools_pass():
    """Ca creator = BANK (admin) → mọi tool PASS (0 đổi — bank tra mọi hồ sơ)."""
    conv = _real_conv("admin")
    try:
        assert _chk(conv, "credit_assess", {"owner_id": "C001"}) == "PASS"
        assert _chk(conv, "cust_search", {"q": "Nguyen"}) == "PASS"
        assert _chk(conv, "cust_get", {"id": "C001"}) == "PASS"
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM conversations WHERE id::text=%s", (conv,))
        conn.close()


@requires_db
def test_synthetic_conv_no_op_proves_real_row_needed():
    """conv_id GIẢ (không resolve) → PASS (guard no-op). CHỨNG MINH test cần row thật (không false-green)."""
    assert _chk("synthetic-fake-conv-xyz", "credit_assess", {"owner_id": "C001"}) == "PASS"


def test_db_error_refused():
    """DB lỗi khi guard lookup → refuse fail-closed (leak-gate không cho qua khi không chắc)."""

    class _BoomConn:
        def cursor(self):
            raise psycopg2.OperationalError("db chết")

    r = read_scope_refusal(_BoomConn(), "any", "credit_assess", {"owner_id": "C001"})
    assert r is not None and r["code"] == "not_your_data"
