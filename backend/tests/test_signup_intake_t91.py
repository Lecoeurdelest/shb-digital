"""[BACKEND] Test T9-1 — khách MỚI: register + present_form + form-submit + tạo hồ sơ C9xx (D-57).

- register: happy (201 auto-login) · username trùng 409 · validate (username/password/email) 400.
- present_form: card shape (type form, fields server-side, status pending).
- form-submit: happy (C9xx sinh + users link + card submitted + wake) · 404 ca người khác · card
  không tồn tại 404 · thiếu field 400 · income không số 400 · double-submit 409 idempotent.
- MAIN inject: ca owner_id NULL → block present_form (KHÁC set-but-missing fallback T8).
- reset_demo: wipe C9xx + users.owner_id C9xx → NULL (demo lặp).
- integration: khách mới classify → yellow honest-null (T7-2 tự lo — verify không sửa).
"""

from __future__ import annotations

import uuid

import psycopg2
import psycopg2.extras
from fastapi.testclient import TestClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db, requires_test_db

client = TestClient(app)


def _rm_user(username: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT owner_id FROM users WHERE username=%s", (username,))
        row = cur.fetchone()
        if row and row[0]:
            cur.execute("DELETE FROM customers WHERE id=%s", (row[0],))
        cur.execute("DELETE FROM users WHERE username=%s", (username,))
    conn.close()


def _uniq() -> str:
    return "t91_" + uuid.uuid4().hex[:8]


# ── register ─────────────────────────────────────────────────────────────────


@requires_db
def test_register_happy_auto_login():
    u = _uniq()
    try:
        r = client.post("/api/auth/register", json={"username": u, "password": "pass1", "email": f"{u}@x.com"})
        assert r.status_code == 201
        assert set(r.json().keys()) == {"token", "user"}
        assert r.json()["user"]["role"] == "customer"
        # auto-login: cookie set → /api/me owner_id None (chưa hồ sơ)
        me = client.get("/api/me", cookies=r.cookies)
        assert me.status_code == 200
        assert me.json()["owner_id"] is None
    finally:
        _rm_user(u)


@requires_db
def test_register_duplicate_409():
    u = _uniq()
    try:
        client.post("/api/auth/register", json={"username": u, "password": "pass1"})
        r2 = client.post("/api/auth/register", json={"username": u, "password": "pass2"})
        assert r2.status_code == 409
        assert r2.json()["code"] == "username_taken"
    finally:
        _rm_user(u)


@requires_db
def test_register_validation_400():
    assert client.post("/api/auth/register", json={"username": "ab", "password": "pass1"}).status_code == 400
    assert client.post("/api/auth/register", json={"username": "abcd", "password": "x"}).status_code == 400
    r = client.post("/api/auth/register", json={"username": "abcd2", "password": "pass1", "email": "bad"})
    assert r.status_code == 400
    assert r.json()["code"] == "bad_email"


# ── present_form card ────────────────────────────────────────────────────────


def test_present_form_card_shape():
    """present_form → card type 'form', fields server-side (6), status pending. Model KHÔNG bơm fields."""
    from app.orch.common_tools import FORM_FIELDS, FORM_REQUIRED

    assert len(FORM_FIELDS) == 6
    names = {f["name"] for f in FORM_FIELDS}
    assert names == {"full_name", "id_number", "address", "occupation", "monthly_income", "loan_purpose"}
    assert FORM_REQUIRED == [f["name"] for f in FORM_FIELDS]  # tất cả required
    # input_schema RỖNG (model không truyền field — server-side)
    from app.orch.common_tools import present_form_tool

    assert present_form_tool.input_schema.get("properties") == {}


# ── form-submit ──────────────────────────────────────────────────────────────


def _register_and_conv() -> tuple[str, dict, str]:
    """register khách mới + tạo conv của họ. Trả (username, cookies, conv_id)."""
    u = _uniq()
    r = client.post("/api/auth/register", json={"username": u, "password": "pass1"})
    ck = r.cookies
    conv = client.post("/api/conversations", json={"title": "vay"}, cookies=ck).json()["id"]
    return u, ck, conv


def _mk_form_card(conv_id: str) -> str:
    """Tạo form card pending cho conv (mô phỏng present_form đã chạy)."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    from app.orch.common_tools import FORM_FIELDS

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO cards (conv_id, type, data, ts) VALUES (%s, 'form', %s, now()) RETURNING id::text",
            (conv_id, psycopg2.extras.Json({"type": "form", "fields": FORM_FIELDS, "status": "pending"})),
        )
        return cur.fetchone()[0]


_GOOD_VALUES = {
    "full_name": "Nguyễn Văn Test",
    "id_number": "012345678901",
    "address": "123 Test",
    "occupation": "Kỹ sư",
    "monthly_income": "25000000",
    "loan_purpose": "mua nhà",
}


def _submit(conv: str, card_id: str, cookies: dict, values: dict | None = None):
    """POST form-submit — gói cho gọn dòng."""
    return client.post(
        f"/api/conversations/{conv}/form-submit",
        cookies=cookies,
        json={"card_id": card_id, "values": values if values is not None else _GOOD_VALUES},
    )


@requires_db
def test_form_submit_happy_creates_c9xx_and_links():
    u, ck, conv = _register_and_conv()
    try:
        card_id = _mk_form_card(conv)
        r = _submit(conv, card_id, ck)
        assert r.status_code == 200
        owner_id = r.json()["owner_id"]
        assert owner_id.startswith("C9")
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute("SELECT full_name, monthly_income FROM customers WHERE id=%s", (owner_id,))
            cust = cur.fetchone()
            assert cust[0] == "Nguyễn Văn Test" and cust[1] == 25000000
            cur.execute("SELECT owner_id FROM users WHERE username=%s", (u,))
            assert cur.fetchone()[0] == owner_id  # account linked
            cur.execute("SELECT data->>'status' FROM cards WHERE id::text=%s", (card_id,))
            assert cur.fetchone()[0] == "submitted"  # card flipped
        conn.close()
        # /api/me phản ánh owner_id mới KHÔNG re-login
        assert client.get("/api/me", cookies=ck).json()["owner_id"] == owner_id
    finally:
        _rm_user(u)


@requires_db
def test_form_submit_double_409_idempotent():
    u, ck, conv = _register_and_conv()
    try:
        card_id = _mk_form_card(conv)
        r1 = _submit(conv, card_id, ck)
        assert r1.status_code == 200
        r2 = _submit(conv, card_id, ck)
        assert r2.status_code == 409
        assert r2.json()["code"] == "form_already_submitted"
    finally:
        _rm_user(u)


@requires_db
def test_form_submit_missing_field_400():
    u, ck, conv = _register_and_conv()
    try:
        card_id = _mk_form_card(conv)
        bad = {**_GOOD_VALUES, "full_name": ""}
        r = _submit(conv, card_id, ck, bad)
        assert r.status_code == 400
        assert r.json()["code"] == "missing_fields"
    finally:
        _rm_user(u)


@requires_db
def test_form_submit_bad_income_400():
    u, ck, conv = _register_and_conv()
    try:
        card_id = _mk_form_card(conv)
        bad = {**_GOOD_VALUES, "monthly_income": "không phải số"}
        r = _submit(conv, card_id, ck, bad)
        assert r.status_code == 400
        assert r.json()["code"] == "bad_income"
    finally:
        _rm_user(u)


@requires_db
def test_form_submit_card_not_found_404():
    u, ck, conv = _register_and_conv()
    try:
        fake = str(uuid.uuid4())
        r = _submit(conv, fake, ck)
        assert r.status_code == 404
    finally:
        _rm_user(u)


@requires_db
def test_form_submit_others_conv_404_hide():
    """form-submit ca người khác → 404-hide (can_access_conv)."""
    u1, ck1, conv1 = _register_and_conv()
    u2, ck2, _ = _register_and_conv()
    try:
        card_id = _mk_form_card(conv1)
        # u2 cố submit vào conv1 (của u1) → 404
        r = _submit(conv1, card_id, ck2)
        assert r.status_code == 404
    finally:
        _rm_user(u1)
        _rm_user(u2)


# ── MAIN inject NULL branch ──────────────────────────────────────────────────


@requires_db
def test_main_inject_null_owner_present_form_block():
    """ca creator=customer owner_id NULL → block bảo dùng present_form (KHÁC set-but-missing T8)."""
    from app.orch.main_prompts import _customer_prompt_block

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    u = _uniq()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO users (username, pass_hash, role, owner_id) VALUES (%s,'x','customer',NULL)", (u,))
        cur.execute(
            "INSERT INTO conversations (user_id, title, status, created_at) "
            "VALUES (%s,'t','idle',now()) RETURNING id::text",
            (u,),
        )
        conv = cur.fetchone()[0]
    conn.close()
    try:
        block = _customer_prompt_block(conv)
        assert "CHƯA CÓ HỒ SƠ" in block
        assert "present_form" in block
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv,))
            cur.execute("DELETE FROM users WHERE username=%s", (u,))
        conn.close()


# ── integration: khách mới classify → yellow honest-null (T7-2 tự lo) ─────────


@requires_test_db  # GHI assessments (classify) → chỉ test-db (siết architect)
def test_new_customer_classify_yellow_honest_null():
    """Khách MỚI (C9xx, KHÔNG police/employment/cic record) → classify lane yellow (honest-null,
    KHÔNG red — không suy đoán xấu). Verify T7-2 code tự lo, không sửa gì."""
    from roles.legal.functions import REGISTRY

    from app.mount.pg_adapter import PGConnAdapter, acquire, release

    # tạo 1 khách C9xx trần (không bản ghi 3 trụ)
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO customers (id, full_name, monthly_income) VALUES ('C990','Khách Mới T91',20000000) "
            "ON CONFLICT (id) DO NOTHING"
        )
    conn.close()
    pg = acquire()
    a = PGConnAdapter(pg)
    try:
        r = REGISTRY["legal_classify_profile"](a, owner_id="C990", loan_amount_vnd=300_000_000)
        assert r["found"] is True
        assert r["item"]["lane"] == "yellow", f"khách mới không bản ghi → yellow honest-null: {r['item']['lane']}"
    finally:
        a.close_cursors()
        release(pg)
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DELETE FROM assessments WHERE owner_id='C990'")
            cur.execute("DELETE FROM customers WHERE id='C990'")
        conn.close()


# ── reset_demo C9xx (destructive → requires_test_db) ─────────────────────────


@requires_test_db
def test_reset_demo_wipes_c9xx_and_nulls_owner():
    """reset_demo: wipe customers C9xx + users.owner_id 'C9%' → NULL (demo lặp lại từ đầu)."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    u = _uniq()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO customers (id, full_name, monthly_income) VALUES ('C909','Reg T91',1e7)")
        cur.execute("INSERT INTO users (username, pass_hash, role, owner_id) VALUES (%s,'x','customer','C909')", (u,))
    conn.close()
    from app.db.reset_demo import reset_demo

    reset_demo(DATABASE_URL)
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM customers WHERE id='C909'")
            assert cur.fetchone()[0] == 0  # C9xx wiped
            cur.execute("SELECT owner_id FROM users WHERE username=%s", (u,))
            assert cur.fetchone()[0] is None  # owner_id reset NULL
    finally:
        conn.close()
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM users WHERE username=%s", (u,))
        conn.close()
