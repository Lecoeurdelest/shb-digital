from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.api import compare as compare_mod
from app.main import app

client = TestClient(app)

_LIVE = os.environ.get("RUN_LIVE_SDK") == "1"


def _admin_cookie():
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    return r.cookies


def test_compare_two_columns_shape(monkeypatch):
    async def fake_single(q):
        return {"text": "mental arithmetic", "duration_s": 3.1, "cost": 0.01}

    async def fake_multi(q):
        return {
            "text": "sourced result",
            "duration_s": 40.0,
            "tool_calls": 5,
            "cards": 2,
            "conv_id": "c1",
            "status": "idle",
        }

    monkeypatch.setattr(compare_mod, "_run_single", fake_single)
    monkeypatch.setattr(compare_mod, "_run_multi", fake_multi)

    r = client.post(
        "/api/compare", json={"question": "C001: can this customer borrow 500 million VND?"}, cookies=_admin_cookie()
    )
    assert r.status_code == 200
    body = r.json()
    assert body["question"].startswith("C001")
    assert body["single"]["text"] == "mental arithmetic"
    assert body["multi"]["tool_calls"] == 5
    assert body["multi"]["conv_id"] == "c1"
    assert body["single"].get("tool_calls") is None


def test_compare_multi_timeout_partial(monkeypatch):

    async def fake_single(q):
        return {"text": "single ok", "duration_s": 2.0, "cost": 0.01}

    async def fake_multi(q):
        return {"timeout": True, "conv_id": "c2", "status": "running", "tool_calls": 1, "cards": 0}

    monkeypatch.setattr(compare_mod, "_run_single", fake_single)
    monkeypatch.setattr(compare_mod, "_run_multi", fake_multi)

    r = client.post("/api/compare", json={"question": "q"}, cookies=_admin_cookie())
    assert r.status_code == 200
    body = r.json()
    assert body["single"]["text"] == "single ok"
    assert body["multi"]["timeout"] is True
    assert body["multi"]["conv_id"] == "c2"


def test_compare_single_timeout_partial(monkeypatch):

    import asyncio

    async def hang_single(q):
        await asyncio.sleep(10)
        return {"text": "never reached"}

    async def fake_multi(q):
        return {"text": "sourced multi-agent result", "tool_calls": 5, "cards": 2, "conv_id": "c1"}

    monkeypatch.setattr(compare_mod, "_SINGLE_TIMEOUT_S", 0.2)
    monkeypatch.setattr(compare_mod, "_run_single", hang_single)
    monkeypatch.setattr(compare_mod, "_run_multi", fake_multi)

    r = client.post("/api/compare", json={"question": "q"}, cookies=_admin_cookie())
    assert r.status_code == 200
    body = r.json()
    assert body["single"]["timeout"] is True
    assert "did not respond" in body["single"]["text"]
    assert body["multi"]["tool_calls"] == 5
    assert body["multi"]["conv_id"] == "c1"


def test_compare_multi_raises_still_partial(monkeypatch):

    async def fake_single(q):
        return {"text": "single ok"}

    async def boom_multi(q):
        raise RuntimeError("demo multi-agent failure")

    monkeypatch.setattr(compare_mod, "_run_single", fake_single)
    monkeypatch.setattr(compare_mod, "_run_multi", boom_multi)

    r = client.post("/api/compare", json={"question": "q"}, cookies=_admin_cookie())
    assert r.status_code == 200
    body = r.json()
    assert body["single"]["text"] == "single ok"
    assert body["multi"].get("timeout") or body["multi"].get("error")


def test_compare_empty_question_400():
    r = client.post("/api/compare", json={"question": "  "}, cookies=_admin_cookie())
    assert r.status_code == 400
    assert r.json()["code"] == "empty_question"


def test_compare_requires_admin():
    fresh = TestClient(app)
    r = fresh.post("/api/compare", json={"question": "q"})
    assert r.status_code == 401


# ── live integration (opt-in) ───────────────────────────────────────────────


@pytest.mark.skipif(not _LIVE, reason="live SDK opt-in: RUN_LIVE_SDK=1")
def test_compare_live_single_chay_multi_nguon():

    r = client.post(
        "/api/compare",
        json={"question": "Can customer C001 borrow 500 million VND?"},
        cookies=_admin_cookie(),
    )
    assert r.status_code == 200
    body = r.json()

    assert body["single"].get("text")

    m = body["multi"]
    if not m.get("timeout"):
        assert m["tool_calls"] > 0, "Expected invariant was not satisfied at source line 132."
        assert m.get("conv_id")
