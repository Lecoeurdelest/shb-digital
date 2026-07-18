"""[BACKEND] Test T4-4: POST /api/compare — single vs multi, partial timeout, 400 empty.

Unit mock 2 nhánh (_run_single/_run_multi) — không SDK/DB. Live integration opt-in RUN_LIVE_SDK.
"""

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


# ── shape + partial (mock 2 nhánh) ──────────────────────────────────────────


def test_compare_two_columns_shape(monkeypatch):
    async def fake_single(q):
        return {"text": "nhẩm chay", "duration_s": 3.1, "cost": 0.01}

    async def fake_multi(q):
        return {"text": "có nguồn", "duration_s": 40.0, "tool_calls": 5, "cards": 2, "conv_id": "c1", "status": "idle"}

    monkeypatch.setattr(compare_mod, "_run_single", fake_single)
    monkeypatch.setattr(compare_mod, "_run_multi", fake_multi)

    r = client.post("/api/compare", json={"question": "C001 vay 500tr được không?"}, cookies=_admin_cookie())
    assert r.status_code == 200
    body = r.json()
    assert body["question"].startswith("C001")
    assert body["single"]["text"] == "nhẩm chay"
    assert body["multi"]["tool_calls"] == 5  # multi CÓ nguồn
    assert body["multi"]["conv_id"] == "c1"  # FE link sang ca thật
    assert body["single"].get("tool_calls") is None  # single KHÔNG tool (nhẩm chay)


def test_compare_multi_timeout_partial(monkeypatch):
    """multi timeout → partial {timeout:true} nhưng single VẪN trả (không 500)."""

    async def fake_single(q):
        return {"text": "single ok", "duration_s": 2.0, "cost": 0.01}

    async def fake_multi(q):
        return {"timeout": True, "conv_id": "c2", "status": "running", "tool_calls": 1, "cards": 0}

    monkeypatch.setattr(compare_mod, "_run_single", fake_single)
    monkeypatch.setattr(compare_mod, "_run_multi", fake_multi)

    r = client.post("/api/compare", json={"question": "q"}, cookies=_admin_cookie())
    assert r.status_code == 200
    body = r.json()
    assert body["single"]["text"] == "single ok"  # single vẫn có
    assert body["multi"]["timeout"] is True
    assert body["multi"]["conv_id"] == "c2"


def test_compare_multi_raises_still_partial(monkeypatch):
    """1 nhánh NỔ (exception) → gather return_exceptions → partial, KHÔNG 500."""

    async def fake_single(q):
        return {"text": "single ok"}

    async def boom_multi(q):
        raise RuntimeError("multi nổ demo")

    monkeypatch.setattr(compare_mod, "_run_single", fake_single)
    monkeypatch.setattr(compare_mod, "_run_multi", boom_multi)

    r = client.post("/api/compare", json={"question": "q"}, cookies=_admin_cookie())
    assert r.status_code == 200  # KHÔNG 500
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
    """LIVE: câu thẩm định → single text chay (0 tool) · multi text + tool_calls>0 + conv_id."""
    r = client.post(
        "/api/compare",
        json={"question": "Khách C001 vay 500 triệu được không?"},
        cookies=_admin_cookie(),
    )
    assert r.status_code == 200
    body = r.json()
    # single: có text, KHÔNG tool_calls field (nhẩm chay)
    assert body["single"].get("text")
    # multi: có nguồn (tool_calls>0) HOẶC timeout partial
    m = body["multi"]
    if not m.get("timeout"):
        assert m["tool_calls"] > 0, "multi PHẢI gọi tool (có nguồn)"
        assert m.get("conv_id")
