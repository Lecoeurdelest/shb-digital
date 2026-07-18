"""[BACKEND] Test D-56 persona: authz đảo + scoping + /api/me owner_id + MAIN identity inject.

Customer decide→403 · get/chat ca người khác→404 (hide) · admin thấy hết · /api/me shape ·
MAIN-inject block khách CÓ ở ca customer, KHÔNG ở ca bank (build-prompt trực tiếp, no live SDK).
"""

from __future__ import annotations

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db

client = TestClient(app)


def _login(username: str, password: str):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def _mk_conv(user_id: str, title: str = "t") -> str:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (user_id, title, status, created_at) "
                "VALUES (%s,%s,'idle',now()) RETURNING id::text",
                (user_id, title),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def _rm_conv(cid: str):
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM messages WHERE conv_id=%s", (cid,))
        cur.execute("DELETE FROM conversations WHERE id::text=%s", (cid,))
    conn.close()


# ── authz đảo D-56: customer decide/audit → 403 ─────────────────────────────


@requires_db
def test_customer_decide_forbidden_403():
    r = _login("c001", "c001")
    if r.status_code != 200:
        pytest.skip("seed c001 chưa có")
    r2 = client.post("/api/approvals/x/decide", json={"decision": "approved"}, cookies=r.cookies)
    assert r2.status_code == 403
    assert r2.json()["code"] == "forbidden"


@requires_db
def test_customer_audit_forbidden_403():
    r = _login("c001", "c001")
    if r.status_code != 200:
        pytest.skip("seed c001 chưa có")
    r2 = client.get("/api/audit", cookies=r.cookies)
    assert r2.status_code == 403


@requires_db
def test_admin_decide_reaches_logic_not_403():
    """admin (ngân hàng) → KHÔNG 403 (qua authz; 404/400 tuỳ id — không phải forbidden)."""
    r = _login("admin", "admin")
    r2 = client.post(
        "/api/approvals/00000000-0000-0000-0000-000000000000/decide", json={"decision": "approved"}, cookies=r.cookies
    )
    assert r2.status_code != 403  # admin qua authz (404 not_found do id giả)


# ── scoping: get/chat ca người khác → 404 (hide) · admin thấy hết ────────────


@requires_db
def test_customer_get_others_conv_404():
    """customer get ca của người khác → 404 (hide existence, KHÔNG 403)."""
    other = _mk_conv("b001")  # ca của khách khác
    try:
        r = _login("c001", "c001")
        if r.status_code != 200:
            pytest.skip("seed chưa có")
        r2 = client.get(f"/api/conversations/{other}", cookies=r.cookies)
        assert r2.status_code == 404
        assert r2.json()["code"] == "not_found"
    finally:
        _rm_conv(other)


@requires_db
def test_customer_get_own_conv_200():
    own = _mk_conv("c001")
    try:
        r = _login("c001", "c001")
        if r.status_code != 200:
            pytest.skip("seed chưa có")
        r2 = client.get(f"/api/conversations/{own}", cookies=r.cookies)
        assert r2.status_code == 200
    finally:
        _rm_conv(own)


@requires_db
def test_admin_sees_others_conv_200():
    """admin → thấy MỌI ca (giám sát ngân hàng)."""
    cust = _mk_conv("c001")
    try:
        r = _login("admin", "admin")
        r2 = client.get(f"/api/conversations/{cust}", cookies=r.cookies)
        assert r2.status_code == 200
    finally:
        _rm_conv(cust)


# ── /api/me shape ───────────────────────────────────────────────────────────


@requires_db
def test_api_me_customer_owner_id():
    r = _login("c001", "c001")
    if r.status_code != 200:
        pytest.skip("seed c001 chưa có")
    r2 = client.get("/api/me", cookies=r.cookies)
    assert r2.status_code == 200
    body = r2.json()
    assert body["role"] == "customer"
    assert body["owner_id"] == "C001"  # owner_id của REQUESTER
    assert body["username"] == "c001"


@requires_db
def test_api_me_admin_owner_id_null():
    r = _login("admin", "admin")
    r2 = client.get("/api/me", cookies=r.cookies)
    assert r2.json()["role"] == "admin"
    assert r2.json()["owner_id"] is None  # ngân hàng không map owner


# ── MAIN identity inject (build-prompt trực tiếp, no live SDK) ───────────────


@requires_db
def test_main_inject_customer_conv_has_block():
    """ca creator=customer → _customer_prompt_block có '## KHÁCH HÀNG HIỆN TẠI' + owner_id + xưng anh/chị."""
    from app.orch.main_prompts import _customer_prompt_block

    conv = _mk_conv("c001")  # creator = khách c001 → owner C001
    try:
        block = _customer_prompt_block(conv)
        assert "KHÁCH HÀNG HIỆN TẠI" in block
        assert "C001" in block  # owner_id CREATOR
        assert "anh/chị" in block
        assert "KHÔNG tra cứu hồ sơ người khác" in block
    finally:
        _rm_conv(conv)


@requires_db
def test_main_inject_bank_conv_no_block():
    """ca creator=bank (admin/user) → block RỖNG (không inject — landmine DEV/bank unchanged)."""
    from app.orch.main_prompts import _customer_prompt_block

    conv = _mk_conv("admin")  # creator = ngân hàng
    try:
        assert _customer_prompt_block(conv) == ""
    finally:
        _rm_conv(conv)


@requires_db
def test_main_inject_missing_owner_fallback():
    """owner_id trỏ owner KHÔNG có trong seed → fallback chỉ owner_id (không crash), vẫn có block."""
    from app.orch.main_prompts import _customer_prompt_block

    # tạo user customer owner_id lạ + conv của user đó
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, pass_hash, role, owner_id) VALUES "
            "('ztest','x','customer','ZZZ999') ON CONFLICT (username) DO UPDATE SET owner_id='ZZZ999'"
        )
    conn.close()
    conv = _mk_conv("ztest")
    try:
        block = _customer_prompt_block(conv)
        assert "ZZZ999" in block  # fallback owner_id (không tên) — không crash
    finally:
        _rm_conv(conv)
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM users WHERE username='ztest'")
        conn.close()
