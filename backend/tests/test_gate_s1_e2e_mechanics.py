from __future__ import annotations

import asyncio
import contextlib

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app
from app.orch import main_session, sub_runner
from app.sse import bus

from .conftest import requires_db

pytestmark = requires_db

STUB_DSCR_RESULT = {
    "text": "## DSCR assessment — Customer C001\n\nDSCR = 3.709 (income 30m/debt payment 8,088,576)."
    "\n\nSource: credit_assess tool.",
    "tool_calls": [
        {"tool": "cust_get", "input": {"id": "C001"}},
        {"tool": "credit_assess", "input": {"owner_id": "C001", "loan_amount_vnd": 0}},
    ],
}


async def _stub_sub_runner(task) -> dict:
    """Replace run_sub_turn while preserving the text/tool_calls result shape."""
    await asyncio.sleep(0.05)  # Yield to emulate minimal I/O latency.
    return STUB_DSCR_RESULT


async def _stub_run_main_turn(conv_id: str, prompt: str, on_text=None) -> dict:
    """Replace the MAIN turn and distinguish user-message from task-done prompts.

    The dispatch turn returns a short acknowledgement without simulating an MCP tool loop.
    The test dispatches directly through the real orchestration seam. The completion turn
    returns a DSCR summary.
    """
    text = "Request received." if "User message" in prompt else STUB_DSCR_RESULT["text"]
    if on_text is not None:
        await on_text(text)
    return {"text": text, "session_id": "stub-session-id", "is_error": False}


@contextlib.asynccontextmanager
async def _override_runners_after_boot():

    orig_default_runner = sub_runner._default_runner
    orig_run_main_turn = main_session.run_main_turn
    sub_runner.set_default_runner(_stub_sub_runner)
    main_session.run_main_turn = _stub_run_main_turn
    try:
        yield
    finally:
        sub_runner.set_default_runner(orig_default_runner)
        main_session.run_main_turn = orig_run_main_turn


async def _login_and_create_conv(client: AsyncClient, title: str) -> str:
    r = await client.post("/api/auth/login", json={"username": "user", "password": "user"})
    assert r.status_code == 200, "Expected invariant was not satisfied at source line 64."
    r2 = await client.post("/api/conversations", json={"title": title})
    assert r2.status_code == 201, "Expected invariant was not satisfied at source line 66."
    return r2.json()["id"]


async def _drain(q: asyncio.Queue, n: int, timeout_s: float = 10.0) -> list[dict]:

    events: list[dict] = []
    for _ in range(n):
        events.append(await asyncio.wait_for(q.get(), timeout=timeout_s))
    return events


@pytest.mark.asyncio
async def test_sse_envelope_shape_and_task_lifecycle_mechanics():

    async with app.router.lifespan_context(app):
        async with _override_runners_after_boot():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "mechanics-dispatch")

                q = bus.subscribe(conv_id)
                try:
                    from app.orch.dispatch import orch_dispatch_impl

                    out = await orch_dispatch_impl(conv_id, "credit", "Assess C001 (mechanics)", "brief mechanics")
                    assert out["created"] is True, "Expected invariant was not satisfied at source line 91."

                    events = await _drain(q, 2, timeout_s=10.0)
                finally:
                    bus.unsubscribe(conv_id, q)

                for ev in events:
                    assert set(ev.keys()) == {"type", "conversation_id", "seq", "ts", "data"}, (
                        "Expected invariant was not satisfied at source line 98."
                    )
                    assert ev["conversation_id"] == conv_id

                types = [ev["type"] for ev in events]
                assert types == ["task.created", "task.status"], (
                    "Expected invariant was not satisfied at source line 104."
                )

                created_task = events[0]["data"]["task"]
                assert created_task["role"] == "credit"
                assert created_task["status"] == "queued"

                done_task = events[1]["data"]["task"]
                assert done_task["status"] == "done", "Expected invariant was not satisfied at source line 111."
                tool_names = [tc["tool"] for tc in done_task["result"]["tool_calls"]]
                assert "credit_assess" in tool_names, "Expected invariant was not satisfied at source line 113."
                assert "3.709" in done_task["result"]["text"]

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SELECT role, status FROM tasks WHERE conv_id=%s", (conv_id,))
        rows = cur.fetchall()
        assert len(rows) == 1 and rows[0] == ("credit", "done"), (
            "Expected invariant was not satisfied at source line 121."
        )
        cur.execute("DELETE FROM tasks WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_chat_flow_emits_conversation_status_and_chat_delta_done_mechanics():

    async with app.router.lifespan_context(app):
        async with _override_runners_after_boot():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "mechanics-chat")

                q = bus.subscribe(conv_id)
                try:
                    r = await client.post(f"/api/conversations/{conv_id}/chat", json={"content": "Mechanics question"})
                    assert r.status_code == 202
                    assert r.json().get("queued") is True

                    events = await _drain(q, 4, timeout_s=10.0)
                finally:
                    bus.unsubscribe(conv_id, q)

                for ev in events:
                    assert set(ev.keys()) == {"type", "conversation_id", "seq", "ts", "data"}

                types = [ev["type"] for ev in events]
                assert types == ["conversation.status", "chat.delta", "chat.delta", "conversation.status"], (
                    f"unexpected event order: {types}"
                )
                assert events[0]["data"]["status"] == "running"
                assert events[1]["data"]["done"] is False, "the streaming chunk must have done=False"
                assert events[2]["data"]["done"] is True, "the final Gap 1 delta must have done=True"
                assert events[2]["data"]["full_text"] == "Request received."
                assert events[3]["data"]["status"] == "idle"

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SELECT sender, content FROM messages WHERE conv_id=%s ORDER BY ts", (conv_id,))
        rows = cur.fetchall()
        senders = [r[0] for r in rows]
        assert senders == ["user", "assistant"], f"persisted messages must match Gap 1: {senders}"
        assert rows[1][1] == "Request received.", "the assistant message must match SSE full_text"
        cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_get_full_state_shape_matches_contract_after_mechanics_flow():

    async with app.router.lifespan_context(app):
        async with _override_runners_after_boot():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "mechanics-fullstate")

                q = bus.subscribe(conv_id)
                try:
                    r = await client.post(f"/api/conversations/{conv_id}/chat", json={"content": "test"})
                    assert r.status_code == 202
                    await _drain(q, 4, timeout_s=10.0)
                finally:
                    bus.unsubscribe(conv_id, q)

                state = (await client.get(f"/api/conversations/{conv_id}")).json()
                # S2 (T2-1, CONTRACT.md §3 D-30): ConversationFullState +cards[] (canvas reload).

                assert set(state.keys()) == {"conversation", "messages", "tasks", "cards"}
                assert state["conversation"]["id"] == conv_id
                assert state["conversation"]["status"] == "idle"
                assert isinstance(state["messages"], list) and len(state["messages"]) == 2
                for m in state["messages"]:
                    assert set(m.keys()) >= {"id", "conv_id", "ts", "sender", "content"}
                assert state["tasks"] == []
                assert state["cards"] == []

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()
