from __future__ import annotations

import asyncio
import contextlib

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app
from app.orch import main_session, registry, sub_runner
from app.sse import bus

from .conftest import requires_db

pytestmark = requires_db

STUB_CREDIT_RESULT = {
    "text": "DSCR=27.25 (>=1.2 pass), LTV=62.5% (<=70% pass). Sources: credit_assess, credit_cic_get.",
    "tool_calls": [
        {"tool": "cust_get", "input": {"id": "B001"}},
        {"tool": "credit_assess", "input": {"owner_id": "B001", "loan_amount_vnd": 5_000_000_000}},
    ],
}
STUB_LEGAL_RESULT = {
    "text": "Collateral COL06 has clean legal status and no disputes. Source: legal_check_docs.",
    "tool_calls": [
        {"tool": "legal_check_docs", "input": {"collateral_id": "COL06"}},
    ],
}
_STUB_BY_ROLE = {"credit": STUB_CREDIT_RESULT, "legal": STUB_LEGAL_RESULT}


async def _stub_sub_runner(task) -> dict:

    await asyncio.sleep(0.05)
    return _STUB_BY_ROLE.get(task.role, {"text": "stub", "tool_calls": []})


async def _stub_run_main_turn_with_present(conv_id: str, prompt: str, on_text=None) -> dict:

    from app.orch import registry as _registry

    _registry.CTX_ACTOR.set("main")
    _registry.CTX_TASK.set("")

    if "User message" in prompt:
        text = "Dispatched work to two specialists running in parallel."
        if on_text is not None:
            await on_text(text)
        return {"text": text, "session_id": "stub-session-id", "is_error": False}

    from app.orch.common_tools import present_tool

    await present_tool.handler(
        {
            "type": "document",
            "title": "Assessment memo — B001 (mechanics)",
            "items": [
                {"section": "Credit", "content": STUB_CREDIT_RESULT["text"]},
                {"section": "Legal", "content": STUB_LEGAL_RESULT["text"]},
            ],
            "sources": ["credit_assess", "credit_cic_get", "legal_check_docs"],
        }
    )
    text = "The assessment memo was assembled on the canvas."
    if on_text is not None:
        await on_text(text)
    return {"text": text, "session_id": "stub-session-id", "is_error": False}


@contextlib.asynccontextmanager
async def _override_runners_after_boot():

    orig_default_runner = sub_runner._default_runner
    orig_run_main_turn = main_session.run_main_turn
    sub_runner.set_default_runner(_stub_sub_runner)
    main_session.run_main_turn = _stub_run_main_turn_with_present
    try:
        yield
    finally:
        sub_runner.set_default_runner(orig_default_runner)
        main_session.run_main_turn = orig_run_main_turn


async def _login_and_create_conv(client: AsyncClient, title: str) -> str:
    r = await client.post("/api/auth/login", json={"username": "user", "password": "user"})
    assert r.status_code == 200, "Expected invariant was not satisfied at source line 89."
    r2 = await client.post("/api/conversations", json={"title": title})
    assert r2.status_code == 201, "Expected invariant was not satisfied at source line 91."
    return r2.json()["id"]


async def _drain(q: asyncio.Queue, n: int, timeout_s: float = 10.0) -> list[dict]:
    events: list[dict] = []
    for _ in range(n):
        events.append(await asyncio.wait_for(q.get(), timeout=timeout_s))
    return events


def _cleanup(conv_id: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM tasks WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_two_subs_parallel_dispatch_then_main_synthesis_presents_document_mechanics():

    from app.orch import room

    async with app.router.lifespan_context(app):
        async with _override_runners_after_boot():
            room.wire_event_sink()
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "mechanics-s2-parallel")

                q = bus.subscribe(conv_id)
                try:
                    from app.orch.dispatch import orch_dispatch_impl

                    registry.CTX_CONV.set(conv_id)
                    out_credit = await orch_dispatch_impl(conv_id, "credit", "Assess B001", "brief credit")
                    out_legal = await orch_dispatch_impl(conv_id, "legal", "Review COL06", "brief legal")
                    assert out_credit["created"] is True
                    assert out_legal["created"] is True

                    events = await _drain(q, 10, timeout_s=10.0)
                finally:
                    bus.unsubscribe(conv_id, q)

                by_type: dict[str, list[dict]] = {}
                for e in events:
                    by_type.setdefault(e["type"], []).append(e)

                created = by_type.get("task.created", [])
                done = by_type.get("task.status", [])
                cards = by_type.get("card", [])
                assert len(created) == 2, "Expected invariant was not satisfied at source line 147."
                assert len(done) == 2, "Expected invariant was not satisfied at source line 148."
                assert len(cards) >= 1, "Expected invariant was not satisfied at source line 149."

                roles_created = sorted(e["data"]["task"]["role"] for e in created)
                assert roles_created == ["credit", "legal"], "Expected invariant was not satisfied at source line 152."

                for e in done:
                    task = e["data"]["task"]
                    assert task["status"] == "done", "Expected invariant was not satisfied at source line 156."
                    expected = _STUB_BY_ROLE[task["role"]]
                    assert task["result"]["text"] == expected["text"], (
                        "Expected invariant was not satisfied at source line 158."
                    )

                document_cards = [c for c in cards if c["data"]["card"]["type"] == "document"]
                assert len(document_cards) >= 1, "Expected invariant was not satisfied at source line 161."
                doc_card = document_cards[-1]["data"]["card"]
                assert doc_card["task_id"] is None, "Expected invariant was not satisfied at source line 163."

        conn = psycopg2.connect(DATABASE_URL)
        try:
            cur = conn.cursor()
            cur.execute("SELECT role, status FROM tasks WHERE conv_id=%s ORDER BY role", (conv_id,))
            rows = cur.fetchall()
            assert rows == [("credit", "done"), ("legal", "done")], (
                "Expected invariant was not satisfied at source line 173."
            )
            cur.execute("SELECT type, task_id FROM cards WHERE conv_id=%s", (conv_id,))
            card_rows = cur.fetchall()
            assert any(t == "document" and tid is None for t, tid in card_rows), (
                "Expected invariant was not satisfied at source line 176."
            )
        finally:
            conn.close()
        _cleanup(conv_id)
        room.set_turn_runner(None)


@pytest.mark.asyncio
async def test_main_present_document_task_id_null_on_inline_reentrant_path_mechanics():

    from app.orch import room

    registry.reset_room("mechanics-ctxtask-conv")
    conv_id = "mechanics-ctxtask-conv"
    seen_task_id_in_present: list[str | None] = []

    class _StopHere(Exception):
        pass

    async def _fake_connect(self):

        seen_task_id_in_present.append(registry.CTX_TASK.get() or None)
        raise _StopHere

    async def noop(*a, **k):
        return None

    import claude_agent_sdk

    orig_connect = claude_agent_sdk.ClaudeSDKClient.connect
    claude_agent_sdk.ClaudeSDKClient.connect = _fake_connect

    async def _turn_runner_catches_stophere(cid, event, data):
        try:
            await main_session.run_main_turn(cid, "mechanics synthesis prompt")
        except _StopHere:
            pass

    room.set_turn_runner(_turn_runner_catches_stophere)

    async def sink(cid, event, data):
        await room.handle_room_event(cid, event, data)

    sub_runner.set_event_sink(sink)

    import app.orch.store as store_mod

    monkeypatched = {
        "mark_running": store_mod.mark_running,
        "finish_task": store_mod.finish_task,
        "get_task": store_mod.get_task,
        "task_board": store_mod.task_board,
        "get_conv_session_id": main_session.store.get_conv_session_id,
    }
    store_mod.mark_running = noop
    store_mod.finish_task = noop
    store_mod.get_task = noop
    store_mod.task_board = lambda *a, **k: asyncio.sleep(0, result=[])
    main_session.store.get_conv_session_id = noop

    try:
        from app.orch.store import Task

        await sub_runner._run_sub(
            Task(id="mechanics-sub-task-id", conv_id=conv_id, role="credit", title="t", status="queued"),
            runner=lambda task: asyncio.sleep(0.01, result={"ok": True}),
        )
        await asyncio.sleep(0.05)

        assert seen_task_id_in_present == [None], "Expected invariant was not satisfied at source line 247."
    finally:
        claude_agent_sdk.ClaudeSDKClient.connect = orig_connect
        room.set_turn_runner(None)
        sub_runner.set_event_sink(None)
        store_mod.mark_running = monkeypatched["mark_running"]
        store_mod.finish_task = monkeypatched["finish_task"]
        store_mod.get_task = monkeypatched["get_task"]
        store_mod.task_board = monkeypatched["task_board"]
        main_session.store.get_conv_session_id = monkeypatched["get_conv_session_id"]
        registry.reset_room(conv_id)


@pytest.mark.asyncio
async def test_present_tool_id_injection_filtered_mechanics():

    from app.orch import store
    from app.orch.common_tools import present_tool

    conv_id = "mechanics-idinject-conv"
    registry.CTX_CONV.set(conv_id)
    registry.CTX_ACTOR.set("main")
    registry.CTX_TASK.set("")

    result = await present_tool.handler(
        {
            "type": "options",
            "title": "Proposal (mechanics id-inject test)",
            "items": [{"label": "Approve", "value": "approve"}],
            "sources": ["credit_assess"],
            "recommended": "approve",
            "id": "FAKE-ID-MODEL-BOM",
            "conv_id": "FAKE-CONV-BOM",
            "task_id": "FAKE-TASK-BOM",
            "ts": "1999-01-01T00:00:00Z",
        }
    )
    assert "rendered" in result["content"][0]["text"], "Expected invariant was not satisfied at source line 288."

    cards = await store.list_cards(conv_id)
    try:
        assert len(cards) == 1
        card = cards[0]
        assert card["id"] != "FAKE-ID-MODEL-BOM", "Expected invariant was not satisfied at source line 294."
        assert card["conv_id"] == conv_id, "Expected invariant was not satisfied at source line 295."
        assert card["task_id"] != "FAKE-TASK-BOM", "Expected invariant was not satisfied at source line 296."
        assert card["sources"] == ["credit_assess"], "Expected invariant was not satisfied at source line 297."
        assert card["recommended"] == "approve", "Expected invariant was not satisfied at source line 298."
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
            conn.commit()
        finally:
            conn.close()
