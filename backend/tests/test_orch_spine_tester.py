from __future__ import annotations

import asyncio
import importlib.util

import pytest

_ORCH_AVAILABLE = importlib.util.find_spec("app.orch") is not None

pytestmark = pytest.mark.skipif(
    not _ORCH_AVAILABLE,
    reason="Optional integration prerequisite is unavailable.",
)


# ─────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_idempotent_same_role_twice_returns_existing():
    from app.orch.dispatch import create_task_guarded

    conv_id = "tester-case-a-conv"
    role = "credit"

    task1, existing1 = await create_task_guarded(conv_id, role, "First assessment", "input A")
    assert task1 is not None, "Expected invariant was not satisfied at source line 32."
    assert existing1 is None

    task2, existing2 = await create_task_guarded(conv_id, role, "Duplicate second assessment", "input B")
    assert task2 is None, "Expected invariant was not satisfied at source line 36."
    assert existing2 is not None
    assert existing2.id == task1.id, "Expected invariant was not satisfied at source line 38."


@pytest.mark.asyncio
async def test_dispatch_idempotent_race_two_near_simultaneous_calls():

    from app.orch.dispatch import create_task_guarded

    conv_id = "tester-case-a-race-conv"
    role = "credit"

    results = await asyncio.gather(
        create_task_guarded(conv_id, role, "race-1", "in1"),
        create_task_guarded(conv_id, role, "race-2", "in2"),
    )
    created_count = sum(1 for task, _ in results if task is not None)
    assert created_count == 1, "Expected invariant was not satisfied at source line 54."


# ─────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────


def _tester_task(conv_id: str, role: str = "credit", tid: str = "tester-task-1"):

    from app.orch.store import Task

    return Task(id=tid, conv_id=conv_id, role=role, title="tester case invariant", status="queued")


@pytest.fixture
def _isolated_store(monkeypatch):

    from app.orch import store

    calls = {"mark_running": 0, "finish_task": 0}

    async def fake_mark_running(task_id):
        calls["mark_running"] += 1

    async def fake_finish_task(task_id, status, result):
        calls["finish_task"] += 1

    async def fake_board(conv_id):
        return []

    monkeypatch.setattr(store, "mark_running", fake_mark_running)
    monkeypatch.setattr(store, "finish_task", fake_finish_task)
    monkeypatch.setattr(store, "task_board", fake_board)
    return calls


async def _sink_counter():

    events = []

    async def sink(conv_id, event, data):
        events.append({"conv_id": conv_id, "event": event, "data": data})

    from app.orch import sub_runner

    sub_runner.set_event_sink(sink)
    return events


@pytest.mark.asyncio
async def test_sub_outcome_done_emits_exactly_one_event(_isolated_store):
    from app.orch import registry, sub_runner

    registry.reset_room("tester-inv-done")
    events = await _sink_counter()

    async def runner_done(task):
        return {"item": {"metrics": {"dscr": 3.709}}}

    await sub_runner._run_sub(_tester_task("tester-inv-done", tid="t-done"), runner=runner_done)

    assert len(events) == 1, "Expected invariant was not satisfied at source line 117."
    assert events[0]["event"] == "task_done"
    assert events[0]["data"]["outcome"] == "done"
    assert events[0]["data"]["role"] == "credit"

    assert events[0]["data"]["task_id"] == "t-done"
    registry.reset_room("tester-inv-done")


@pytest.mark.asyncio
async def test_sub_outcome_failed_emits_exactly_one_event(_isolated_store):
    from app.orch import registry, sub_runner

    registry.reset_room("tester-inv-failed")
    events = await _sink_counter()

    async def runner_raise(task):
        raise ValueError("simulated tool failure for the exception branch")

    await sub_runner._run_sub(_tester_task("tester-inv-failed", tid="t-failed"), runner=runner_raise)

    assert len(events) == 1, "Expected invariant was not satisfied at source line 138."
    assert events[0]["data"]["outcome"] == "failed"
    assert "simulated tool failure" in events[0]["data"]["result_summary"], (
        "Expected invariant was not satisfied at source line 140."
    )
    registry.reset_room("tester-inv-failed")


@pytest.mark.asyncio
async def test_sub_outcome_timeout_emits_exactly_one_event(_isolated_store):

    from app.orch import registry, sub_runner

    registry.reset_room("tester-inv-timeout")
    events = await _sink_counter()

    async def runner_timeout(task):
        raise sub_runner.IdleTimeout()

    await sub_runner._run_sub(_tester_task("tester-inv-timeout", tid="t-timeout"), runner=runner_timeout)

    assert len(events) == 1, "Expected invariant was not satisfied at source line 157."
    assert events[0]["data"]["outcome"] == "timeout"
    registry.reset_room("tester-inv-timeout")


@pytest.mark.asyncio
async def test_sub_outcome_cancel_emits_exactly_one_event_not_swallowed(_isolated_store):

    from app.orch import registry, sub_runner

    registry.reset_room("tester-inv-cancel")
    events = await _sink_counter()
    sub_is_running = asyncio.Event()

    async def runner_hang_forever(task):
        sub_is_running.set()
        await asyncio.sleep(3600)

    t = sub_runner.spawn_sub(_tester_task("tester-inv-cancel", tid="t-cancel"), runner=runner_hang_forever)
    await asyncio.wait_for(sub_is_running.wait(), timeout=2.0)

    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t

    assert len(events) == 1, "Expected invariant was not satisfied at source line 182."
    assert events[0]["data"]["outcome"] == "failed", "Expected invariant was not satisfied at source line 187."
    assert "cancelled" in events[0]["data"]["result_summary"], (
        "Expected invariant was not satisfied at source line 188."
    )
    registry.reset_room("tester-inv-cancel")


# ─────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_room_busy_one_runs_one_queues():
    from app.orch import registry, room

    conv_id = "tester-case-c-conv"
    registry.reset_room(conv_id) if hasattr(registry, "reset_room") else None

    acquired1 = await room.try_acquire(conv_id, "user_message", {"content": "message 1"})
    assert acquired1 is True, "Expected invariant was not satisfied at source line 206."

    acquired2 = await room.try_acquire(conv_id, "user_message", {"content": "message 2"})
    assert acquired2 is False, "Expected invariant was not satisfied at source line 209."


@pytest.mark.asyncio
async def test_two_user_messages_while_busy_both_reach_main_no_dedup():

    from app.orch import registry, room

    conv_id = "tester-case-c-nodedup-conv"
    registry.reset_room(conv_id)

    acquired0 = await room.try_acquire(conv_id, "user_message", {"content": "message in progress"})
    assert acquired0 is True
    acquired1 = await room.try_acquire(conv_id, "user_message", {"content": "message 1"})
    acquired2 = await room.try_acquire(conv_id, "user_message", {"content": "message 2"})
    assert acquired1 is False and acquired2 is False, "Expected invariant was not satisfied at source line 224."

    first = await room.release(conv_id)
    assert first is not None
    contents_seen = [first[1]["content"]]
    remaining = registry.queue_for(conv_id)
    contents_seen += [data["content"] for _evt, data in remaining if "content" in data]

    assert "message 1" in contents_seen, "Expected invariant was not satisfied at source line 232."
    assert "message 2" in contents_seen, "Expected invariant was not satisfied at source line 233."
    registry.reset_room(conv_id)


@pytest.mark.asyncio
async def test_release_does_not_reacquire_ghost_slot():

    from app.orch import room

    conv_id = "tester-case-c-ghostslot-conv"
    await room.try_acquire(conv_id, "user_message", {"content": "message 1"})
    await room.release(conv_id)

    acquired_after_release = await room.try_acquire(conv_id, "user_message", {"content": "new message"})
    assert acquired_after_release is True, "Expected invariant was not satisfied at source line 247."
