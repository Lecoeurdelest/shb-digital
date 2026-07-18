"""Integration test auth — login (đúng/sai), JWT, cookie, deps (CONTRACT §1). Cần DB seed users."""

from __future__ import annotations

import psycopg2
from fastapi.testclient import TestClient

from app.auth.security import decode_token, hash_password, verify_password
from app.config import AUTH_COOKIE
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


# ── security primitives (không cần DB) ──────────────────────────────────────


def test_hash_verify_roundtrip():
    h = hash_password("secret123")
    assert verify_password("secret123", h) is True
    assert verify_password("wrong", h) is False


def test_verify_bad_hash_returns_false():
    assert verify_password("x", "not-a-bcrypt-hash") is False


def test_token_roundtrip():
    from app.auth.security import make_token

    tok = make_token(user_id="u1", username="user", role="user")
    claims = decode_token(tok)
    assert claims["sub"] == "u1"
    assert claims["username"] == "user"
    assert claims["role"] == "user"


def test_decode_bad_token():
    assert decode_token("garbage.token.here") is None


# ── login endpoint (cần DB seed) ────────────────────────────────────────────


@requires_db
def test_login_success_user():
    if not _users_seeded():
        import pytest

        pytest.skip("users chưa seed — uv run python -m app.db.seed_users")
    r = client.post("/api/auth/login", json={"username": "user", "password": "user"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["username"] == "user"
    assert body["user"]["role"] == "user"
    assert "token" in body
    # cookie set
    assert AUTH_COOKIE in r.cookies
    # token trong body decode được
    assert decode_token(body["token"])["role"] == "user"


@requires_db
def test_login_success_admin():
    if not _users_seeded():
        import pytest

        pytest.skip("users chưa seed")
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "admin"


@requires_db
def test_login_wrong_password_401_envelope():
    if not _users_seeded():
        import pytest

        pytest.skip("users chưa seed")
    r = client.post("/api/auth/login", json={"username": "user", "password": "WRONG"})
    assert r.status_code == 401
    body = r.json()
    # envelope 4-field TRẦN (không bọc {detail})
    assert set(body) == {"code", "message", "hint", "retryable"}
    assert body["code"] == "unauthorized"


@requires_db
def test_login_unknown_user_401():
    if not _users_seeded():
        import pytest

        pytest.skip("users chưa seed")
    r = client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
    assert r.status_code == 401
    assert r.json()["code"] == "unauthorized"


def test_login_missing_field_400_envelope():
    r = client.post("/api/auth/login", json={"username": "user"})  # thiếu password
    assert r.status_code == 400
    body = r.json()
    assert set(body) == {"code", "message", "hint", "retryable"}
    assert body["code"] == "bad_request"


# ── logout endpoint (S11 micro — clear cookie thật) ─────────────────────────


@requires_db
def test_logout_clears_cookie_me_401():
    """login → /api/me 200 → logout → /api/me 401 (cookie chết THẬT, không re-auth khi reload)."""
    fresh = TestClient(app)
    r = fresh.post("/api/auth/login", json={"username": "user", "password": "user"})
    assert r.status_code == 200
    assert fresh.get("/api/me").status_code == 200  # cookie sống → authed
    lo = fresh.post("/api/auth/logout")
    assert lo.status_code == 200
    assert lo.json() == {"ok": True}
    # cookie đã bị xoá (delete_cookie khớp attributes) → /api/me 401
    assert fresh.get("/api/me").status_code == 401


def test_logout_idempotent_when_not_logged_in():
    """logout khi CHƯA login → vẫn 200 {ok:true} (idempotent — gọi là xoá, không cần auth)."""
    fresh = TestClient(app)
    r = fresh.post("/api/auth/logout")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
