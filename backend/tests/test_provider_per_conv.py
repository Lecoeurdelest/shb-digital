"""[BACKEND] Test D-45b (c): provider/model per-conversation — create param + store + resolve.

conv lưu provider/model · conv_provider_env(null→server-default, tên→keyed) · create validate
bad_provider→400 · get đọc lại. DB thật (requires_db). Không SDK (main_session wiring = live verify).
"""

from __future__ import annotations

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.db.config import DATABASE_URL
from app.main import app
from app.orch import store
from app.orch.providers import conv_provider_env

from .conftest import requires_db

client = TestClient(app)


def _cookie():
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    return r.cookies


def _cleanup(conv_id: str):
    c = psycopg2.connect(DATABASE_URL)
    c.autocommit = True
    c.cursor().execute("DELETE FROM conversations WHERE id::text=%s", (conv_id,))
    c.close()


# ── conv_provider_env resolve ───────────────────────────────────────────────


def test_conv_provider_env_null_server_default():
    """null → server-default (SHB_PROVIDER hoặc yaml default = claude-cli → env rỗng)."""
    env = conv_provider_env(None)
    assert env == {}  # subscription default → rỗng (SDK dùng CLI auth)


def test_conv_provider_env_keyed(monkeypatch):
    """provider keyed (zai) → 3 biến ANTHROPIC_* (env inject).

    Test chỉ kiểm SHAPE env (keys), KHÔNG gọi API → key zai chỉ cần TỒN TẠI, không cần THẬT.
    monkeypatch dummy (reload đọc os.environ merge-over .env) → chạy được cả CI KHÔNG có .env
    (test không phụ thuộc secret thật — conftest docstring)."""
    monkeypatch.setenv("zai", "dummy-ci-key")
    env = conv_provider_env("zai")
    assert set(env) == {"ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY"}


def test_conv_provider_env_unknown_raises():
    """provider không tồn tại → raise (caller turn fail LOUD, không hang)."""
    with pytest.raises(KeyError):
        conv_provider_env("khong-ton-tai-xyz")


# ── create/get lưu provider+model (DB thật) ─────────────────────────────────


@requires_db
@pytest.mark.asyncio
async def test_create_stores_provider_model():
    conv = await store.create_conversation("u", "ca", provider="zai", model="glm-4.6")
    try:
        assert conv["provider"] == "zai"
        assert conv["model"] == "glm-4.6"
        got = await store.get_conversation(conv["id"])
        assert got["provider"] == "zai"  # resume-consistency: đọc lại đúng
        assert got["model"] == "glm-4.6"
    finally:
        _cleanup(conv["id"])


@requires_db
@pytest.mark.asyncio
async def test_create_null_provider_default():
    """không truyền provider → null (server-default lúc chạy — conv cũ + không chọn không vỡ)."""
    conv = await store.create_conversation("u", "ca")
    try:
        assert conv["provider"] is None
        assert conv["model"] is None
    finally:
        _cleanup(conv["id"])


# ── API create validate ─────────────────────────────────────────────────────


@requires_db
def test_api_create_with_provider():
    cookies = _cookie()
    r = client.post("/api/conversations", json={"title": "ca", "provider": "zai", "model": "glm-4.6"}, cookies=cookies)
    assert r.status_code == 201
    body = r.json()
    assert body["provider"] == "zai"
    assert body["model"] == "glm-4.6"
    _cleanup(body["id"])


@requires_db
def test_api_create_bad_provider_400():
    """provider không có trong config → 400 bad_provider (fail loud, không lưu provider sai → hang)."""
    cookies = _cookie()
    r = client.post("/api/conversations", json={"title": "ca", "provider": "khong-ton-tai"}, cookies=cookies)
    assert r.status_code == 400
    assert r.json()["code"] == "bad_provider"


@requires_db
def test_api_create_no_provider_ok():
    """không truyền provider → 201 (default). Backward-compat conv cũ."""
    cookies = _cookie()
    r = client.post("/api/conversations", json={"title": "ca"}, cookies=cookies)
    assert r.status_code == 201
    assert r.json()["provider"] is None
    _cleanup(r.json()["id"])
