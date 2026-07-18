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
    """Không set env → configs/providers.yaml LOAD ĐỦ (KHÔNG rơi built-in default 1-provider).

    FIX D: built-in default (khi thiếu configs) CHỈ có claude-cli → assert ≥2 + có 'zai' bắt được
    lỗi thiếu COPY configs/ trong image (loader fallback default = 1 provider chết)."""
    names = _names(None, monkeypatch)
    assert "claude-cli" in names
    assert len(names) >= 2, f"configs không load (built-in default 1-provider?): {names}"
    assert "zai" in names  # provider yaml thật — không có trong built-in default


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


# ── effective_default: /api/models 'default' KHÔNG trỏ provider ẩn (micro-fix trước GO) ──


def _effective(env_disabled: str | None, env_provider: str | None, monkeypatch) -> str:
    for k in ("SHB_PROVIDERS_DISABLED", "SHB_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    if env_disabled is not None:
        monkeypatch.setenv("SHB_PROVIDERS_DISABLED", env_disabled)
    if env_provider is not None:
        monkeypatch.setenv("SHB_PROVIDER", env_provider)
    return Providers().effective_default()


def _view_default(monkeypatch) -> list[str]:
    return [p["name"] for p in Providers().public_view() if p["default"]]


def test_effective_default_not_disabled_provider(monkeypatch):
    """BUG VM: disable yaml-default (claude-cli) + SHB_PROVIDER=zai → effective = zai (KHÔNG claude-cli ẩn)."""
    eff = _effective("claude-cli", "zai", monkeypatch)
    assert eff == "zai"
    # /api/models 'default' đồng bộ (chỉ zai default, không claude-cli ẩn)
    assert _view_default(monkeypatch) == ["zai"]


def test_effective_default_no_env_yaml_default(monkeypatch):
    """Không disable, không env → yaml default (claude-cli)."""
    assert _effective(None, None, monkeypatch) == "claude-cli"


def test_effective_default_yaml_default_dead_first_alive(monkeypatch):
    """Disable yaml-default, không SHB_PROVIDER → provider ĐẦU TIÊN còn sống."""
    eff = _effective("claude-cli", None, monkeypatch)
    assert eff != "claude-cli"  # yaml default chết → không dùng
    assert eff in _names("claude-cli", monkeypatch)  # trong list còn sống


def test_effective_default_env_pref_dead_falls_through(monkeypatch):
    """SHB_PROVIDER trỏ provider BỊ ẨN → bỏ env pref, về yaml default (nếu sống) — không dùng provider ẩn."""
    eff = _effective("zai", "zai", monkeypatch)  # SHB_PROVIDER=zai nhưng zai disabled
    assert eff != "zai"


def test_view_default_always_matches_effective(monkeypatch):
    """1 NGUỒN SỰ THẬT: /api/models 'default' LUÔN == effective_default (mọi cấu hình env)."""
    for dis, prov in [(None, None), ("claude-cli", "zai"), ("claude-cli", None), ("zai", "zai")]:
        eff = _effective(dis, prov, monkeypatch)
        assert _view_default(monkeypatch) == [eff], f"lệch: view={_view_default(monkeypatch)} eff={eff}"


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
