from __future__ import annotations

import asyncio
import os
import time

import psycopg2
import psycopg2.extras
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db

_LIVE = os.environ.get("RUN_LIVE_SDK") == "1"

pytestmark = [
    pytest.mark.skipif(not _LIVE, reason="Optional integration prerequisite is unavailable."),
    requires_db,
]


async def _login(client: AsyncClient, username: str, password: str) -> None:
    r = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, "Expected invariant was not satisfied at source line 27."


async def _create_conversation(client: AsyncClient, title: str) -> str:
    r = await client.post("/api/conversations", json={"title": title})
    assert r.status_code == 201, "Expected invariant was not satisfied at source line 32."
    return r.json()["id"]


async def _wait_for_task_done(
    client: AsyncClient, conv_id: str, role: str = "credit", timeout_s: float = 90.0, poll_s: float = 1.0
) -> dict:

    deadline = time.monotonic() + timeout_s
    last_state: dict = {}
    while time.monotonic() < deadline:
        r = await client.get(f"/api/conversations/{conv_id}")
        assert r.status_code == 200, "Expected invariant was not satisfied at source line 44."
        last_state = r.json()
        for task in last_state.get("tasks", []):
            if task["role"] == role and task["status"] == "done":
                return last_state
        await asyncio.sleep(poll_s)
    pytest.fail("Expected condition was not met at source line 50.")


def _has_dscr(text: str) -> bool:

    return any(v in text for v in ("3.709", "3,709", "3.71", "3,71"))


async def _wait_for_message_count(client: AsyncClient, conv_id: str, n: int, timeout_s: float = 60.0) -> list[dict]:
    deadline = time.monotonic() + timeout_s
    messages: list[dict] = []
    while time.monotonic() < deadline:
        r = await client.get(f"/api/conversations/{conv_id}")
        messages = r.json()["messages"]
        if len(messages) >= n:
            return messages
        await asyncio.sleep(1.0)
    pytest.fail("Expected condition was not met at source line 67.")


@pytest.mark.asyncio
async def test_gate_s1_dscr_end_to_end_via_sse():

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _login(client, "user", "user")
            conv_id = await _create_conversation(client, "gate-s1-automated")

            r = await client.post(
                f"/api/conversations/{conv_id}/chat",
                json={
                    "content": "Customer C001 earns 30 million VND and pays 8 million monthly debt. What is the DSCR?"
                },
            )
            assert r.status_code == 202, "Expected invariant was not satisfied at source line 82."
            assert r.json().get("queued") is True

            state = await _wait_for_task_done(client, conv_id, role="credit", timeout_s=90.0)

            tasks = [t for t in state["tasks"] if t["role"] == "credit"]
            assert len(tasks) == 1 and tasks[0]["status"] == "done"
            task_result = tasks[0]["result"]
            tool_calls = task_result.get("tool_calls", [])
            tool_names = [tc["tool"] for tc in tool_calls]
            assert "credit_assess" in tool_names, "Expected invariant was not satisfied at source line 92."
            credit_call = next(tc for tc in tool_calls if tc["tool"] == "credit_assess")
            assert credit_call["input"].get("owner_id") == "C001", (
                "Expected invariant was not satisfied at source line 96."
            )

            assert _has_dscr(task_result["text"]), "Expected invariant was not satisfied at source line 98."

            messages = await _wait_for_message_count(client, conv_id, 3, timeout_s=60.0)
            senders = [m["sender"] for m in messages]
            assert senders == ["user", "assistant", "assistant"], (
                "Expected invariant was not satisfied at source line 102."
            )
            final_text = messages[-1]["content"]
            assert _has_dscr(final_text), "Expected invariant was not satisfied at source line 104."
            assert "credit_assess" in final_text or "credit" in final_text.lower(), (
                "Expected invariant was not satisfied at source line 105."
            )

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur = conn.cursor()
        cur.execute("SELECT sender FROM messages WHERE conv_id=%s ORDER BY ts", (conv_id,))
        pg_senders = [row["sender"] for row in cur.fetchall()]
        assert pg_senders == senders, "Expected invariant was not satisfied at source line 114."

        cur.execute("SELECT role, status, result FROM tasks WHERE conv_id=%s", (conv_id,))
        pg_tasks = cur.fetchall()
        assert len(pg_tasks) == 1 and pg_tasks[0]["role"] == "credit" and pg_tasks[0]["status"] == "done"
        pg_tool_names = [tc["tool"] for tc in pg_tasks[0]["result"]["tool_calls"]]
        assert "credit_assess" in pg_tool_names, "Expected invariant was not satisfied at source line 120."

        cur.execute("DELETE FROM tasks WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_gate_s1_plain_message_does_not_dispatch_credit():

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _login(client, "user", "user")
            conv_id = await _create_conversation(client, "gate-s1-plain")

            r = await client.post(f"/api/conversations/{conv_id}/chat", json={"content": "Hello, who are you?"})
            assert r.status_code == 202

            messages = await _wait_for_message_count(client, conv_id, 2, timeout_s=30.0)
            assert len(messages) >= 2, "Expected invariant was not satisfied at source line 142."

            final_state = (await client.get(f"/api/conversations/{conv_id}")).json()
            assert final_state["tasks"] == [], "Expected invariant was not satisfied at source line 145."

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM tasks WHERE conv_id=%s", (conv_id,))
        assert cur.fetchone()[0] == 0, "Expected invariant was not satisfied at source line 151."
        cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()
