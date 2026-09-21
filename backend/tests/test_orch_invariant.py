from __future__ import annotations

import asyncio

import pytest

from app.orch import registry, room, store, sub_runner
from app.orch.store import Task


def _fake_task(conv_id="inv-conv", role="credit", tid="task-inv-1") -> Task:
    return Task(id=tid, conv_id=conv_id, role=role, title="t", status="queued")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):

    registry.reset_all()

    async def noop_mark_running(task_id):
        pass

    async def noop_finish(task_id, status, result):
        pass

    async def fake_board(conv_id):
        return []

    monkeypatch.setattr(store, "mark_running", noop_mark_running)
    monkeypatch.setattr(store, "finish_task", noop_finish)
    monkeypatch.setattr(store, "task_board", fake_board)
    yield
    registry.reset_all()


async def _collect_events():

    events = []

    async def sink(conv_id, event, data):
        events.append((event, data))

    sub_runner.set_event_sink(sink)
    return events


@pytest.mark.asyncio
async def test_done_emits_exactly_one_event():
    events = await _collect_events()

    async def runner_done(task):
        return {"verdict": "eligible", "dscr": 3.709}

    await sub_runner._run_sub(_fake_task(), runner=runner_done)
    assert len(events) == 1
    assert events[0][0] == "task_done"
    assert events[0][1]["outcome"] == "done"


@pytest.mark.asyncio
async def test_failed_emits_exactly_one_event():
    events = await _collect_events()

    async def runner_raise(task):
        raise RuntimeError("tool failure")

    await sub_runner._run_sub(_fake_task(), runner=runner_raise)
    assert len(events) == 1
    assert events[0][1]["outcome"] == "failed"
    assert "tool failure" in events[0][1]["result_summary"]


@pytest.mark.asyncio
async def test_timeout_emits_exactly_one_event():
    events = await _collect_events()

    async def runner_timeout(task):
        raise sub_runner.IdleTimeout()

    await sub_runner._run_sub(_fake_task(), runner=runner_timeout)
    assert len(events) == 1
    assert events[0][1]["outcome"] == "timeout"


@pytest.mark.asyncio
async def test_cancel_emits_exactly_one_event_not_swallowed():

    events = await _collect_events()
    started = asyncio.Event()

    async def runner_hang(task):
        started.set()
        await asyncio.sleep(100)

    t = sub_runner.spawn_sub(_fake_task(), runner=runner_hang)
    await started.wait()
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t

    assert len(events) == 1
    assert events[0][1]["outcome"] == "failed"
    assert events[0][1]["result_summary"].find("cancelled by user") >= 0


@pytest.mark.asyncio
async def test_report_unregisters_role_allowing_redispatch(monkeypatch):

    await _collect_events()
    conv, role = "unreg-conv", "credit"
    registry.register_running(conv, role, "task-x")
    assert registry.get_running_task_id(conv, role) == "task-x"

    async def runner_done(task):
        return {"ok": True}

    await sub_runner._run_sub(
        Task(id="task-x", conv_id=conv, role=role, title="t", status="queued"), runner=runner_done
    )

    assert registry.get_running_task_id(conv, role) is None


@pytest.mark.asyncio
async def test_drain_runs_queued_event_after_release():

    registry.reset_room("drain-conv")
    ran = []

    async def turn_runner(conv_id, event, data):
        ran.append(data.get("content"))
        await asyncio.sleep(0)

    room.set_turn_runner(turn_runner)
    try:
        await asyncio.gather(
            room.handle_room_event("drain-conv", "user_message", {"content": "message 1"}),
            room.handle_room_event("drain-conv", "user_message", {"content": "message 2"}),
        )
        await asyncio.sleep(0.05)
        assert len(ran) == 2, "Expected invariant was not satisfied at source line 141."
        assert set(ran) == {"message 1", "message 2"}
    finally:
        room.set_turn_runner(None)
        registry.reset_room("drain-conv")


@pytest.mark.asyncio
async def test_ctx_actor_not_leaked_from_sub_to_main_reentrant():

    registry.reset_room("ctx-conv")
    seen_actor = []

    async def fake_run_main_turn(conv_id, event, data):

        registry.CTX_CONV.set(conv_id)
        registry.CTX_ACTOR.set("main")
        seen_actor.append(registry.CTX_ACTOR.get())

    room.set_turn_runner(fake_run_main_turn)

    async def sink(conv_id, event, data):
        await room.handle_room_event(conv_id, event, data)

    sub_runner.set_event_sink(sink)

    async def runner_done(task):
        assert registry.CTX_ACTOR.get() == "credit", "The actor must equal the role inside a sub-task."
        return {"ok": True}

    monkeypatch_store = {}
    try:
        import app.orch.store as st

        orig = (st.mark_running, st.finish_task, st.task_board)

        async def _noop(*a, **k):
            return []

        st.mark_running = _noop
        st.finish_task = _noop
        st.task_board = _noop
        monkeypatch_store["orig"] = orig

        await sub_runner._run_sub(
            Task(id="ctx-t", conv_id="ctx-conv", role="credit", title="t", status="queued"),
            runner=runner_done,
        )
        await asyncio.sleep(0.02)
        assert seen_actor == ["main"], "Expected invariant was not satisfied at source line 190."
    finally:
        import app.orch.store as st

        if "orig" in monkeypatch_store:
            st.mark_running, st.finish_task, st.task_board = monkeypatch_store["orig"]
        room.set_turn_runner(None)
        registry.reset_room("ctx-conv")


@pytest.mark.asyncio
async def test_ctx_task_not_leaked_from_sub_to_main_reentrant(monkeypatch):

    from app.orch import main_session

    registry.reset_room("ctxt-conv")
    seen_task = []

    class _StopHere(Exception):
        pass

    def _boom(*a, **k):
        seen_task.append(registry.CTX_TASK.get() or None)
        raise _StopHere

    import claude_agent_sdk

    monkeypatch.setattr(claude_agent_sdk, "ClaudeSDKClient", _boom, raising=False)

    async def noop(*a, **k):
        return None

    monkeypatch.setattr(main_session.store, "get_conv_session_id", noop)

    async def fake_turn(conv_id, event, data):
        try:
            await main_session.run_main_turn(conv_id, "prompt")
        except _StopHere:
            pass

    room.set_turn_runner(fake_turn)

    async def sink(conv_id, event, data):
        await room.handle_room_event(conv_id, event, data)

    sub_runner.set_event_sink(sink)

    async def runner_done(task):
        assert registry.CTX_TASK.get() == "ctxt-t", "CTX_TASK must equal task.id inside a sub-task."
        return {"ok": True}

    monkeypatch.setattr(sub_runner.store, "mark_running", noop)
    monkeypatch.setattr(sub_runner.store, "finish_task", noop)
    monkeypatch.setattr(sub_runner.store, "get_task", noop)

    async def board(*a, **k):
        return []

    monkeypatch.setattr(sub_runner.store, "task_board", board)
    try:
        await sub_runner._run_sub(
            Task(id="ctxt-t", conv_id="ctxt-conv", role="products", title="t", status="queued"),
            runner=runner_done,
        )
        await asyncio.sleep(0.02)

        assert seen_task == [None], "Expected invariant was not satisfied at source line 256."
    finally:
        room.set_turn_runner(None)
        registry.reset_room("ctxt-conv")
