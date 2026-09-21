from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _user_cookie():
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    return r.cookies


def test_models_requires_auth():

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
    assert body["default"] in names


def test_models_default_is_effective_not_disabled(monkeypatch):

    monkeypatch.setenv("SHB_PROVIDERS_DISABLED", "claude-cli")
    r = client.get("/api/models", cookies=_user_cookie())
    assert r.status_code == 200
    body = r.json()
    names = [p["name"] for p in body["providers"]]
    assert "claude-cli" not in names
    assert body["default"] != "claude-cli"
    assert body["default"] in names

    flagged = [p["name"] for p in body["providers"] if p["default"]]
    assert flagged == [body["default"]]


def test_models_never_leaks_key():

    cookies = _user_cookie()
    r = client.get("/api/models", cookies=cookies)
    assert r.status_code == 200
    raw = r.text
    for p in r.json()["providers"]:
        assert "api_key" not in p, "Expected invariant was not satisfied at source line 55."
        assert isinstance(p["has_key"], bool)

        assert set(p) >= {"name", "kind", "models", "default", "has_key"}

    assert "ANTHROPIC_AUTH_TOKEN" not in raw
    assert "api_key" not in raw
