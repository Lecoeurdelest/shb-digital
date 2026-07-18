"""[BACKEND] Test DEV_SKIP_AUTH (D-39) — flag ON→admin, OFF→auth JWT cũ. + GET /api/auth/me.

DEV_SKIP_AUTH đọc lúc import config → test monkeypatch `deps.DEV_SKIP_AUTH` (flag đã bind vào deps).
Auth test CŨ chạy flag OFF (default) — không phá.
"""

from __future__ import annotations

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
        cur.execute("SELECT count(*) FROM users")
        return cur.fetchone()[0] >= 2
    except psycopg2.Error:
        return False
    finally:
        conn.close()


@pytest.fixture
def skip_auth_on(monkeypatch):
    """Bật DEV_SKIP_AUTH cho test (bind trong deps). Reset cache admin sub."""
    monkeypatch.setattr(deps, "DEV_SKIP_AUTH", True)
    monkeypatch.setattr(deps, "_dev_admin_sub", None)
    yield
    monkeypatch.setattr(deps, "_dev_admin_sub", None)


# ── Flag ON: mọi request = admin (no cookie → 200) ──────────────────────────


@requires_db
def test_skip_auth_on_no_cookie_returns_admin(skip_auth_on):
    if not _users_seeded():
        pytest.skip("users chưa seed")
    # KHÔNG cookie → vẫn 200 (admin)
    r = client.get("/api/conversations")  # require_user
    assert r.status_code == 200


@requires_db
def test_skip_auth_on_me_returns_admin(skip_auth_on):
    if not _users_seeded():
        pytest.skip("users chưa seed")
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "admin"


def test_skip_auth_on_claims_shape(skip_auth_on):
    # _dev_admin_claims có username/role/sub (không cần DB nếu cache fail → 'dev-admin')
    claims = deps._dev_admin_claims()
    assert claims["role"] == "admin"
    assert claims["username"] == "admin"
    assert "sub" in claims


# ── Flag OFF (default): auth JWT như cũ ─────────────────────────────────────


def test_skip_auth_off_no_cookie_401():
    # default DEV_SKIP_AUTH=False → no cookie → 401 4-field
    assert deps.DEV_SKIP_AUTH is False  # default OFF (an toàn)
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    body = r.json()
    assert set(body) == {"code", "message", "hint", "retryable"}
    assert body["code"] == "unauthorized"


def test_skip_auth_off_conversations_401():
    r = client.get("/api/conversations")  # require_user, no cookie
    assert r.status_code == 401


@requires_db
def test_skip_auth_off_login_still_works():
    """Flag OFF: login flow cũ giữ nguyên (không phá auth T1-1)."""
    if not _users_seeded():
        pytest.skip("users chưa seed")
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "admin"
    # /me với cookie vừa set → 200
    me = client.get("/api/auth/me")
    assert me.status_code == 200
