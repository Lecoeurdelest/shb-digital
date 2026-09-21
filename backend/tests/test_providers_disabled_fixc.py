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

    names = _names(None, monkeypatch)
    assert "claude-cli" in names
    assert len(names) >= 2, "Expected invariant was not satisfied at source line 29."
    assert "zai" in names


def test_disable_hides_provider(monkeypatch):

    all_names = _names(None, monkeypatch)
    after = _names("claude-cli", monkeypatch)
    assert "claude-cli" not in after
    assert len(after) == len(all_names) - 1


def test_unknown_name_ignored(monkeypatch):

    base = _names(None, monkeypatch)
    assert _names("nonexistent-xyz", monkeypatch) == base


def test_disable_all_keeps_default(monkeypatch):

    all_names = _names(None, monkeypatch)
    kept = _names(",".join(all_names), monkeypatch)
    assert len(kept) >= 1

    assert any(p["default"] for p in Providers().public_view())


def test_whitespace_and_empty_tolerant(monkeypatch):

    after = _names(" claude-cli , ", monkeypatch)
    assert "claude-cli" not in after


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

    eff = _effective("claude-cli", "zai", monkeypatch)
    assert eff == "zai"

    assert _view_default(monkeypatch) == ["zai"]


def test_effective_default_no_env_yaml_default(monkeypatch):

    assert _effective(None, None, monkeypatch) == "claude-cli"


def test_effective_default_yaml_default_dead_first_alive(monkeypatch):

    eff = _effective("claude-cli", None, monkeypatch)
    assert eff != "claude-cli"
    assert eff in _names("claude-cli", monkeypatch)


def test_effective_default_env_pref_dead_falls_through(monkeypatch):

    eff = _effective("zai", "zai", monkeypatch)
    assert eff != "zai"


def test_view_default_always_matches_effective(monkeypatch):

    for dis, prov in [(None, None), ("claude-cli", "zai"), ("claude-cli", None), ("zai", "zai")]:
        eff = _effective(dis, prov, monkeypatch)
        assert _view_default(monkeypatch) == [eff], "Expected invariant was not satisfied at source line 106."


@requires_db
def test_create_conversation_disabled_provider_400(monkeypatch):

    monkeypatch.setenv("SHB_PROVIDERS_DISABLED", "claude-cli")
    u = "fixc_" + uuid.uuid4().hex[:6]
    r = client.post("/api/auth/register", json={"username": u, "password": "pass1"})
    try:
        resp = client.post(
            "/api/conversations",
            json={"title": "t", "provider": "claude-cli"},
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

    monkeypatch.setenv("SHB_PROVIDERS_DISABLED", "claude-cli")
    u = "fixc2_" + uuid.uuid4().hex[:6]
    r = client.post("/api/auth/register", json={"username": u, "password": "pass1"})
    try:
        resp = client.post("/api/conversations", json={"title": "t", "provider": "zai"}, cookies=r.cookies)

        assert not (resp.status_code == 400 and resp.json().get("code") == "bad_provider")
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DELETE FROM conversations WHERE user_id=%s", (u,))
            cur.execute("DELETE FROM users WHERE username=%s", (u,))
        conn.close()
