from __future__ import annotations

from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.db.config import DATABASE_URL
from app.main import app
from app.orch import store_audit

from .conftest import requires_db

client = TestClient(app)


def _admin_cookie():
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    return r.cookies


def _count(conv_id: str) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM tool_calls WHERE conv_id=%s", (conv_id,))
            return cur.fetchone()[0]
    finally:
        conn.close()


@requires_db
@pytest.mark.asyncio
async def test_record_tool_call_persists_row():
    conv = f"audit-{uuid4()}"
    row = await store_audit.record_tool_call(
        task_id=None,
        conv_id=conv,
        actor="operations",
        tool="disburse",
        tool_input={"loan_id": "L1", "amount": 5000000000},
        output={"disbursed": True},
        cost={"usd": 0.01},
    )
    assert row is not None
    assert row["actor"] == "operations"
    assert row["tool"] == "disburse"
    assert row["input"]["loan_id"] == "L1"
    assert row["output"]["disbursed"] is True
    assert row["cost"]["usd"] == 0.01
    assert row["task_id"] is None
    assert row["conv_id"] == conv
    assert row["id"]
    assert row["ts"]  # server now()


@requires_db
@pytest.mark.asyncio
async def test_record_output_null_ok():

    conv = f"audit-null-{uuid4()}"
    row = await store_audit.record_tool_call(task_id=None, conv_id=conv, actor="main", tool="calc", tool_input={"a": 1})
    assert row is not None
    assert row["output"] is None
    assert row["cost"] is None


@requires_db
@pytest.mark.asyncio
async def test_query_filter_by_conv_and_tool():
    conv = f"audit-q-{uuid4()}"
    await store_audit.record_tool_call(task_id=None, conv_id=conv, actor="main", tool="present", tool_input={})
    await store_audit.record_tool_call(task_id=None, conv_id=conv, actor="operations", tool="disburse", tool_input={})
    all_rows = await store_audit.query_tool_calls({"conv_id": conv})
    assert len(all_rows) == 2
    disb = await store_audit.query_tool_calls({"conv_id": conv, "tool": "disburse"})
    assert len(disb) == 1
    assert disb[0]["tool"] == "disburse"
    by_actor = await store_audit.query_tool_calls({"conv_id": conv, "actor": "main"})
    assert len(by_actor) == 1
    assert by_actor[0]["actor"] == "main"


@requires_db
@pytest.mark.asyncio
async def test_query_newest_first():
    conv = f"audit-order-{uuid4()}"
    await store_audit.record_tool_call(task_id=None, conv_id=conv, actor="main", tool="first", tool_input={})
    await store_audit.record_tool_call(task_id=None, conv_id=conv, actor="main", tool="second", tool_input={})
    rows = await store_audit.query_tool_calls({"conv_id": conv})
    assert rows[0]["tool"] == "second"


@requires_db
@pytest.mark.asyncio
async def test_filter_whitelist_ignores_unknown():

    conv = f"audit-wl-{uuid4()}"
    await store_audit.record_tool_call(task_id=None, conv_id=conv, actor="main", tool="x", tool_input={})

    rows = await store_audit.query_tool_calls({"conv_id": conv, "output": "hack"})
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_record_bad_db_returns_none_not_raise(monkeypatch):

    monkeypatch.setattr(store_audit, "DATABASE_URL", "postgresql://bad:bad@localhost:1/nope")
    row = await store_audit.record_tool_call(task_id=None, conv_id="c", actor="main", tool="x", tool_input={})
    assert row is None


# ── GET /api/audit (admin) ──────────────────────────────────────────────────


@requires_db
@pytest.mark.asyncio
async def test_api_audit_requires_admin():
    fresh = TestClient(app)
    r = fresh.get("/api/audit")
    assert r.status_code == 401


@requires_db
@pytest.mark.asyncio
async def test_api_audit_filter_returns_rows():
    conv = f"audit-api-{uuid4()}"
    await store_audit.record_tool_call(
        task_id=None, conv_id=conv, actor="operations", tool="disburse", tool_input={"loan_id": "L1"}
    )
    cookies = _admin_cookie()
    r = client.get(f"/api/audit?conv_id={conv}", cookies=cookies)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["tool"] == "disburse"
    assert rows[0]["actor"] == "operations"


@requires_db
def test_api_audit_bad_task_id_400():

    cookies = _admin_cookie()
    r = client.get("/api/audit?task_id=not-a-uuid", cookies=cookies)
    assert r.status_code == 400
    assert r.json()["code"] == "bad_filter"


@requires_db
def test_api_audit_limit_cap():

    cookies = _admin_cookie()
    r = client.get("/api/audit?limit=5000", cookies=cookies)  # > max 1000
    assert r.status_code == 400
    assert r.json()["code"] == "bad_request"


def test_emit_toolcall_shape():

    from app.orch.audit_emit import _emit_toolcall
    from app.sse import bus

    conv = f"toolcall-sse-{uuid4()}"
    q = bus.subscribe(conv)
    try:
        _emit_toolcall(
            conv,
            {"id": "tc1", "task_id": "t1", "tool": "disburse", "input": {"loan_id": "L1"}, "cost": {"usd": 0.02}},
        )
        assert not q.empty(), "Expected invariant was not satisfied at source line 171."
        ev = q.get_nowait()
        assert ev["type"] == "toolcall"
        d = ev["data"]

        assert set(d.keys()) == {"id", "task_id", "tool", "summary", "cost"}
        assert d["id"] == "tc1"
        assert d["task_id"] == "t1"
        assert d["tool"] == "disburse"
        assert "loan_id" in d["summary"]
        assert d["cost"] == {"usd": 0.02}
    finally:
        bus.unsubscribe(conv, q)


def test_emit_toolcall_null_input_empty_summary():

    from app.orch.audit_emit import _emit_toolcall
    from app.sse import bus

    conv = f"toolcall-null-{uuid4()}"
    q = bus.subscribe(conv)
    try:
        _emit_toolcall(conv, {"task_id": None, "tool": "x", "input": None, "cost": None})
        ev = q.get_nowait()
        assert ev["data"]["summary"] == ""
    finally:
        bus.unsubscribe(conv, q)


def test_safe_json_fallback_non_serializable():

    from app.orch.store_audit import _safe_json

    class Weird:
        def __repr__(self):
            return "WEIRD_BLOCK"

    out = _safe_json(Weird())
    assert out is not None
    assert "WEIRD" in out
    import json as _j

    _j.loads(out)
    assert _safe_json(None) is None
    assert _safe_json({"ok": 1}) == '{"ok": 1}'


@requires_db
@pytest.mark.asyncio
async def test_record_non_serializable_output_still_persists():

    conv = f"audit-weird-{uuid4()}"

    class Weird:
        def __repr__(self):
            return "WEIRD"

    row = await store_audit.record_tool_call(
        task_id=None, conv_id=conv, actor="main", tool="x", tool_input={"a": 1}, output=Weird()
    )
    assert row is not None
    assert row["input"] == {"a": 1}
    assert "WEIRD" in str(row["output"])
