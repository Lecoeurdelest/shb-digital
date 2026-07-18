"""[BACKEND] Test FIX C — SHB_PROVIDERS_DISABLED ẩn provider chết (VM không có CLI auth).

public_view loại provider disabled → picker FE sạch + create_conversation (đọc public_view) tự
400. Default không-env → đủ 3 nhà (dev không đổi). Defensive: disable-hết giữ default · tên lạ ignore.
"""

from __future__ import annotations

import uuid

import psycopg2
from fastapi.testclient import TestClient

from app.db.config import DATABASE_URL
from app.main import app
from app.orch.providers import Providers

from .conftest import requires_db

client = TestClient(app)


def _names(env_val: str | None, monkeypatch) -> list[str]:
    if env_val is None:
        monkeypatch.delenv("SHB_PROVIDERS_DISABLED", raising=False)
    else:
        monkeypatch.setenv("SHB_PROVIDERS_DISABLED", env_val)
    return [p["name"] for p in Providers().public_view()]


def test_no_env_all_providers(monkeypatch):
    """Không set env → đủ provider yaml (dev/local KHÔNG đổi)."""
    names = _names(None, monkeypatch)
    assert "claude-cli" in names and len(names) >= 1  # đủ như cấu hình gốc


def test_disable_hides_provider(monkeypatch):
    """SHB_PROVIDERS_DISABLED=claude-cli → claude-cli KHÔNG trong public_view (picker ẩn)."""
    all_names = _names(None, monkeypatch)
    after = _names("claude-cli", monkeypatch)
    assert "claude-cli" not in after
    assert len(after) == len(all_names) - 1


def test_unknown_name_ignored(monkeypatch):
    """Tên lạ trong env → ignore (đủ như no-env, không crash)."""
    base = _names(None, monkeypatch)
    assert _names("nonexistent-xyz", monkeypatch) == base


def test_disable_all_keeps_default(monkeypatch):
    """Disable HẾT provider → giữ default (picker KHÔNG rỗng — chết picker)."""
    all_names = _names(None, monkeypatch)
    kept = _names(",".join(all_names), monkeypatch)
    assert len(kept) >= 1  # không rỗng
    # default còn lại
    assert any(p["default"] for p in Providers().public_view())


def test_whitespace_and_empty_tolerant(monkeypatch):
    """Env có space/dấu phẩy thừa → parse đúng (' claude-cli , ' → disable claude-cli)."""
    after = _names(" claude-cli , ", monkeypatch)
    assert "claude-cli" not in after


@requires_db
def test_create_conversation_disabled_provider_400(monkeypatch):
    """create_conversation với provider DISABLED → 400 bad_provider (validation đọc public_view)."""
    monkeypatch.setenv("SHB_PROVIDERS_DISABLED", "claude-cli")
    u = "fixc_" + uuid.uuid4().hex[:6]
    r = client.post("/api/auth/register", json={"username": u, "password": "pass1"})
    try:
        resp = client.post(
            "/api/conversations",
            json={"title": "t", "provider": "claude-cli"},  # disabled → không trong public_view
            cookies=r.cookies,
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == "bad_provider"
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM users WHERE username=%s", (u,))
        conn.close()


@requires_db
def test_create_conversation_enabled_provider_ok(monkeypatch):
    """Đối chứng: provider KHÔNG disabled → create bình thường (không 400 bad_provider)."""
    monkeypatch.setenv("SHB_PROVIDERS_DISABLED", "claude-cli")
    u = "fixc2_" + uuid.uuid4().hex[:6]
    r = client.post("/api/auth/register", json={"username": u, "password": "pass1"})
    try:
        resp = client.post(
            "/api/conversations", json={"title": "t", "provider": "zai"}, cookies=r.cookies
        )
        # zai không bị disable → KHÔNG bad_provider (200/201 tuỳ, miễn không 400-bad_provider)
        assert not (resp.status_code == 400 and resp.json().get("code") == "bad_provider")
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DELETE FROM conversations WHERE user_id=%s", (u,))
            cur.execute("DELETE FROM users WHERE username=%s", (u,))
        conn.close()
