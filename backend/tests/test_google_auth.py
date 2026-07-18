"""Google OAuth (persona KHÁCH D-56) — providers, start (redirect+state), callback (4 nhánh),
upsert idempotent, login password với account Google-only không 500.

Không gọi Google thật: exchange_code/fetch_userinfo monkeypatch tại app.auth.google.
"""

from __future__ import annotations

import uuid

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app import config
from app.auth import google as google_oauth
from app.auth.security import decode_token
from app.config import AUTH_COOKIE
from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db

client = TestClient(app)


@pytest.fixture
def google_on(monkeypatch):
    """Bật Google OAuth giả lập qua env-config (module attr — router/google đọc lúc gọi)."""
    monkeypatch.setattr(config, "AUTH_GOOGLE_ENABLED", True)
    monkeypatch.setattr(config, "GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(config, "GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")


def _fresh_sub() -> str:
    return f"sub-{uuid.uuid4().hex[:12]}"


# ── providers ──────────────────────────────────────────────────────────────


def test_providers_default_google_off():
    r = client.get("/api/auth/providers")
    assert r.status_code == 200
    assert r.json() == {"password": True, "google": False}


def test_providers_google_on(google_on):
    assert client.get("/api/auth/providers").json()["google"] is True


# ── /google/start ──────────────────────────────────────────────────────────


def test_start_disabled_503():
    r = client.get("/api/auth/google/start", follow_redirects=False)
    assert r.status_code == 503
    body = r.json()
    assert body["code"] == "auth_provider_disabled"
    assert set(body) == {"code", "message", "hint", "retryable"}  # envelope 4-field


def test_start_redirects_google_with_state_cookie(google_on):
    r = client.get("/api/auth/google/start", follow_redirects=False)
    assert r.status_code == 307
    loc = r.headers["location"]
    assert loc.startswith(google_oauth.GOOGLE_AUTH_URL)
    assert "client_id=test-client-id" in loc and "state=" in loc
    assert r.cookies.get("oauth_state")  # state cookie chống CSRF


# ── /google/callback ───────────────────────────────────────────────────────


def test_callback_missing_code_400(google_on):
    r = client.get("/api/auth/google/callback?state=x", follow_redirects=False)
    assert r.status_code == 400
    assert r.json()["code"] == "oauth_malformed"


def test_callback_state_mismatch_400(google_on):
    client.cookies.set("oauth_state", "expected")
    r = client.get("/api/auth/google/callback?code=abc&state=WRONG", follow_redirects=False)
    client.cookies.delete("oauth_state")
    assert r.status_code == 400
    assert r.json()["code"] == "oauth_state_mismatch"


def test_callback_google_error_502(google_on, monkeypatch):
    def _boom(code):
        raise google_oauth.GoogleOAuthError("token exchange failed")

    monkeypatch.setattr(google_oauth, "exchange_code", _boom)
    client.cookies.set("oauth_state", "st1")
    r = client.get("/api/auth/google/callback?code=abc&state=st1", follow_redirects=False)
    client.cookies.delete("oauth_state")
    assert r.status_code == 502
    assert r.json()["code"] == "oauth_google_failed"


@requires_db
def test_callback_happy_sets_jwt_cookie_and_creates_customer(google_on, monkeypatch):
    sub = _fresh_sub()
    monkeypatch.setattr(google_oauth, "exchange_code", lambda code: "access-ok")
    monkeypatch.setattr(google_oauth, "fetch_userinfo", lambda access: {"sub": sub, "email": f"{sub}@example.com"})
    client.cookies.set("oauth_state", "st2")
    r = client.get("/api/auth/google/callback?code=abc&state=st2", follow_redirects=False)
    client.cookies.delete("oauth_state")
    assert r.status_code == 307
    assert r.headers["location"] == config.FRONTEND_URL
    token = r.cookies.get(AUTH_COOKIE)
    assert token, "JWT cookie phải được set như login thường"
    claims = decode_token(token)
    assert claims and claims["role"] == "customer"  # khách MỚI → customer (D-56)
    assert claims["username"] == f"{sub}@example.com"
    # row thật trong DB: role customer, owner_id NULL (khách mới — intake S9 gắn sau), pass_hash NULL
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT role, owner_id, pass_hash FROM users WHERE google_sub=%s", (sub,))
            row = cur.fetchone()
    finally:
        conn.close()
    assert row == ("customer", None, None)


@requires_db
def test_upsert_idempotent_same_sub_same_user(google_on):
    sub = _fresh_sub()
    u1 = google_oauth.upsert_google_user(google_sub=sub, email=f"{sub}@example.com")
    u2 = google_oauth.upsert_google_user(google_sub=sub, email=f"{sub}@example.com")
    assert u1["id"] == u2["id"]
    assert u1["role"] == "customer"


@requires_db
def test_password_login_on_google_only_account_is_401_not_500(google_on):
    """Account Google-only (pass_hash NULL) mà login bằng password → 401 sạch (guard NULL)."""
    sub = _fresh_sub()
    u = google_oauth.upsert_google_user(google_sub=sub, email=f"{sub}@example.com")
    r = client.post("/api/auth/login", json={"username": u["username"], "password": "anything"})
    assert r.status_code == 401
    assert r.json()["code"] == "unauthorized"
