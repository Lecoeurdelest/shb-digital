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


@requires_db
def test_customer_decide_forbidden_403():
    r = _login("c001", "c001")
    if r.status_code != 200:
        pytest.skip("seed c001 is unavailable")
    r2 = client.post("/api/approvals/x/decide", json={"decision": "approved"}, cookies=r.cookies)
    assert r2.status_code == 403
    assert r2.json()["code"] == "forbidden"


@requires_db
def test_customer_audit_forbidden_403():
    r = _login("c001", "c001")
    if r.status_code != 200:
        pytest.skip("seed c001 is unavailable")
    r2 = client.get("/api/audit", cookies=r.cookies)
    assert r2.status_code == 403


@requires_db
def test_admin_decide_reaches_logic_not_403():

    r = _login("admin", "admin")
    r2 = client.post(
        "/api/approvals/00000000-0000-0000-0000-000000000000/decide", json={"decision": "approved"}, cookies=r.cookies
    )
    assert r2.status_code != 403


@requires_db
def test_customer_get_others_conv_404():

    other = _mk_conv("b001")
    try:
        r = _login("c001", "c001")
        if r.status_code != 200:
            pytest.skip("seed data is unavailable")
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
            pytest.skip("seed data is unavailable")
        r2 = client.get(f"/api/conversations/{own}", cookies=r.cookies)
        assert r2.status_code == 200
    finally:
        _rm_conv(own)


@requires_db
def test_admin_sees_others_conv_200():

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
        pytest.skip("seed c001 is unavailable")
    r2 = client.get("/api/me", cookies=r.cookies)
    assert r2.status_code == 200
    body = r2.json()
    assert body["role"] == "customer"
    assert body["owner_id"] == "C001"
    assert body["username"] == "c001"


@requires_db
def test_api_me_admin_owner_id_null():
    r = _login("admin", "admin")
    r2 = client.get("/api/me", cookies=r.cookies)
    assert r2.json()["role"] == "admin"
    assert r2.json()["owner_id"] is None


@requires_db
def test_main_inject_customer_conv_has_block():
    """A customer-created conversation receives an owner-scoped prompt block."""
    from app.orch.main_prompts import _customer_prompt_block

    conv = _mk_conv("c001")  # Customer c001 owns C001.
    try:
        block = _customer_prompt_block(conv)
        assert "EXISTING CUSTOMER" in block
        assert "C001" in block
        assert "DO NOT look up another person's case" in block
    finally:
        _rm_conv(conv)


@requires_db
def test_main_inject_bank_conv_no_block():

    from app.orch.main_prompts import _customer_prompt_block

    conv = _mk_conv("admin")
    try:
        assert _customer_prompt_block(conv) == ""
    finally:
        _rm_conv(conv)


@requires_db
def test_main_inject_missing_owner_fallback():

    from app.orch.main_prompts import _customer_prompt_block

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
        assert "ZZZ999" in block
    finally:
        _rm_conv(conv)
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM users WHERE username='ztest'")
        conn.close()
