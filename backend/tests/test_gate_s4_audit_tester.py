from __future__ import annotations

import inspect
import os

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db
from .conftest import wait_for_conversation_idle as _wait_for_conversation_idle

_LIVE = os.environ.get("RUN_LIVE_SDK") == "1"


_skip_live = pytest.mark.skipif(not _LIVE, reason="Optional integration prerequisite is unavailable.")


def test_store_audit_is_append_only_by_code():

    from app.orch import store_audit

    source = inspect.getsource(store_audit)

    sql_lines = [line for line in source.splitlines() if "cur.execute(" in line or line.strip().startswith(('"', "'"))]
    combined = " ".join(sql_lines).upper()
    assert "UPDATE TOOL_CALLS" not in combined, "Expected invariant was not satisfied at source line 30."
    assert "DELETE FROM TOOL_CALLS" not in combined, "Expected invariant was not satisfied at source line 31."
    assert "INSERT INTO TOOL_CALLS" in combined, "Expected invariant was not satisfied at source line 32."


async def _login_and_create_conv(client: AsyncClient, title: str) -> str:
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, "Expected invariant was not satisfied at source line 37."
    r2 = await client.post("/api/conversations", json={"title": title})
    assert r2.status_code == 201, "Expected invariant was not satisfied at source line 39."
    return r2.json()["id"]


def _restore_state(conv_id: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tool_calls WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM tasks WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()


@requires_db
@_skip_live
@pytest.mark.asyncio
async def test_gate_s4_audit_persists_real_tool_calls_via_chat():

    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s4-audit-real")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": "Customer B001 is applying for a loan; perform a credit assessment."},
                )
                assert r.status_code == 202

                await _wait_for_conversation_idle(client, conv_id, timeout_s=90.0)

                r_audit = await client.get(f"/api/audit?conv_id={conv_id}")
                assert r_audit.status_code == 200, "Expected invariant was not satisfied at source line 77."
                rows = r_audit.json()
                assert len(rows) >= 1, "Expected invariant was not satisfied at source line 79."

                actors = {row["actor"] for row in rows}
                assert actors, "Expected invariant was not satisfied at source line 86."
                for row in rows:
                    assert row["tool"], "Expected invariant was not satisfied at source line 88."
                    assert row["actor"] in ("main", "credit", "legal", "operations"), (
                        "Expected invariant was not satisfied at source line 89."
                    )

                credit_rows = [row for row in rows if row["actor"] == "credit"]
                if credit_rows:
                    r_filtered = await client.get(f"/api/audit?conv_id={conv_id}&actor=credit")
                    assert r_filtered.status_code == 200
                    filtered = r_filtered.json()
                    assert len(filtered) == len(credit_rows), "Expected invariant was not satisfied at source line 98."
                    assert all(row["actor"] == "credit" for row in filtered)

                _restore_state(conv_id)
    except AssertionError:
        raise
