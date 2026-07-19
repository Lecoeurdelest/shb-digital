"""[BACKEND] Test D-45b (b): GET /api/models — dropdown FE. require_user + KHÔNG lộ key.

Integration qua TestClient. flag OFF → require_user cần cookie (login). SỐNG CÒN: response
KHÔNG BAO GIỜ chứa api_key (chỉ has_key bool) — luật bí mật port battle.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _user_cookie():
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    return r.cookies


def test_models_requires_auth():
    """flag OFF → không cookie → 401 (client sạch, tránh cookie persist giữa test)."""
    fresh = TestClient(app)
    r = fresh.get("/api/models")
    assert r.status_code == 401


def test_models_returns_providers_and_default():
    cookies = _user_cookie()
    r = client.get("/api/models", cookies=cookies)
    assert r.status_code == 200
    body = r.json()
    assert "providers" in body and "default" in body
    assert isinstance(body["providers"], list) and len(body["providers"]) >= 1
    names = [p["name"] for p in body["providers"]]
    assert body["default"] in names  # default phải là 1 provider tồn tại


def test_models_default_is_effective_not_disabled(monkeypatch):
    """T15-4 (BUG prod): PROVIDERS_DISABLED=claude-cli → top-level default KHÔNG được là claude-cli
    (đã disable, không nằm trong list) mà phải là effective (zai). Invariant: default LUÔN ∈ providers."""
    monkeypatch.setenv("SHB_PROVIDERS_DISABLED", "claude-cli")
    r = client.get("/api/models", cookies=_user_cookie())
    assert r.status_code == 200
    body = r.json()
    names = [p["name"] for p in body["providers"]]
    assert "claude-cli" not in names  # disabled → ẩn khỏi list
    assert body["default"] != "claude-cli"  # top-level default KHÔNG trỏ provider ẩn (bug cũ)
    assert body["default"] in names  # INVARIANT: default luôn nằm trong providers khả dụng
    # per-provider default flag phải KHỚP top-level (1 nguồn sự thật)
    flagged = [p["name"] for p in body["providers"] if p["default"]]
    assert flagged == [body["default"]]


def test_models_never_leaks_key():
    """SỐNG CÒN: raw response body KHÔNG chứa key nào + không field api_key."""
    cookies = _user_cookie()
    r = client.get("/api/models", cookies=cookies)
    assert r.status_code == 200
    raw = r.text  # raw JSON text — bắt mọi key rò rỉ
    for p in r.json()["providers"]:
        assert "api_key" not in p, "field api_key LỘ trong /api/models!"
        assert isinstance(p["has_key"], bool)
        # shape FE cần
        assert set(p) >= {"name", "kind", "models", "default", "has_key"}
    # nếu .env có zai key thật → giá trị key KHÔNG được xuất hiện trong text
    # (test không biết key value; kiểm gián tiếp: không field nào tên api_key/token)
    assert "ANTHROPIC_AUTH_TOKEN" not in raw
    assert "api_key" not in raw
