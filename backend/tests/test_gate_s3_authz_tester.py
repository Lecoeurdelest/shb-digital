from __future__ import annotations

import uuid

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.auth import deps
from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db

client = TestClient(app)


def _users_seeded() -> bool:
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=2)
    except psycopg2.Error:
        return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM users WHERE role='user'")
        has_rm = cur.fetchone()[0] >= 1
        cur.execute("SELECT count(*) FROM users WHERE role='admin'")
        has_admin = cur.fetchone()[0] >= 1
        return has_rm and has_admin
    except psycopg2.Error:
        return False
    finally:
        conn.close()


def _seed_fake_approval() -> str:

    approval_id = str(uuid.uuid4())
    conv_id = f"tester-authz-{approval_id}"
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO approvals (id, conv_id, action, payload, payload_hash, status) "
            "VALUES (%s, %s, 'disburse', %s, %s, 'pending')",
            (approval_id, conv_id, '{"loan_id":"L007","amount":5000000000}', f"authz-test-{approval_id}"),
        )
        conn.commit()
    finally:
        conn.close()
    return approval_id


def _cleanup_approval(approval_id: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM shadow_reviews WHERE approval_id=%s", (approval_id,))
        cur.execute("DELETE FROM approvals WHERE id=%s", (approval_id,))
        conn.commit()
    finally:
        conn.close()


@requires_db
def test_decide_flag_off_no_cookie_401():

    assert deps.DEV_SKIP_AUTH is False, "Expected invariant was not satisfied at source line 68."
    if not _users_seeded():
        pytest.skip("Required test prerequisite is unavailable.")
    approval_id = _seed_fake_approval()
    try:
        r = client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
        assert r.status_code == 401
        body = r.json()
        assert set(body) == {"code", "message", "hint", "retryable"}
        assert body["code"] == "unauthorized"

        conn = psycopg2.connect(DATABASE_URL)
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM approvals WHERE id=%s", (approval_id,))
            assert cur.fetchone()[0] == "pending"
        finally:
            conn.close()
    finally:
        _cleanup_approval(approval_id)


@requires_db
def test_decide_flag_off_rm_user_denied_d56():

    assert deps.DEV_SKIP_AUTH is False
    if not _users_seeded():
        pytest.skip("Required test prerequisite is unavailable.")
    approval_id = _seed_fake_approval()
    try:
        r_login = client.post("/api/auth/login", json={"username": "user", "password": "user"})
        assert r_login.status_code == 200
        assert r_login.json()["user"]["role"] == "user", "Expected invariant was not satisfied at source line 100."

        r = client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
        assert r.status_code == 403, "Expected invariant was not satisfied at source line 103."
        body = r.json()
        assert set(body) == {"code", "message", "hint", "retryable"}
        assert body["code"] == "forbidden"

        conn = psycopg2.connect(DATABASE_URL)
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM approvals WHERE id=%s", (approval_id,))
            assert cur.fetchone()[0] == "pending", "Expected invariant was not satisfied at source line 115."
        finally:
            conn.close()
    finally:
        _cleanup_approval(approval_id)


@requires_db
def test_decide_flag_off_admin_can_decide():

    assert deps.DEV_SKIP_AUTH is False
    if not _users_seeded():
        pytest.skip("Required test prerequisite is unavailable.")
    approval_id = _seed_fake_approval()
    try:
        r_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        assert r_login.status_code == 200
        assert r_login.json()["user"]["role"] == "admin"

        r = client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
        assert r.status_code == 200, "Expected invariant was not satisfied at source line 135."
        assert r.json()["status"] == "approved"
    finally:
        _cleanup_approval(approval_id)


@requires_db
def test_decide_flag_off_rm_denied_pending_list_d56():

    if not _users_seeded():
        pytest.skip("Required test prerequisite is unavailable.")
    r_login = client.post("/api/auth/login", json={"username": "user", "password": "user"})
    assert r_login.status_code == 200

    r = client.get("/api/approvals?status=pending")
    assert r.status_code == 403, "Expected invariant was not satisfied at source line 150."
    body = r.json()
    assert set(body) == {"code", "message", "hint", "retryable"}
    assert body["code"] == "forbidden"
