from __future__ import annotations

import asyncio

import pytest

from app.orch import registry, room, store


@pytest.fixture(autouse=True)
def _isolate_and_mock_store(monkeypatch):
    registry.reset_all()

    async def noop_mark_running(task_id):
        pass

    async def noop_finish(task_id, status, result):
        pass

    async def noop_board(conv_id):
        return []

    async def fake_create_task(conv_id, role, title, brief):
        from app.orch.store import Task

        return Task(id=f"tester-d33-{role}", conv_id=conv_id, role=role, title=title, status="queued")

    monkeypatch.setattr(store, "mark_running", noop_mark_running)
    monkeypatch.setattr(store, "finish_task", noop_finish)
    monkeypatch.setattr(store, "task_board", noop_board)
    monkeypatch.setattr(store, "create_task", fake_create_task)
    yield
    registry.reset_all()


async def _staggered_via_dispatch_impl(conv_id: str) -> dict:

    from app.orch import sub_runner
    from app.orch.dispatch import orch_dispatch_impl

    registry.reset_room(conv_id)
    wakes: list[tuple[str, dict]] = []
    main_entered = asyncio.Event()
    release_main = asyncio.Event()

    async def slow_main_turn(cid, event, data):
        wakes.append((event, dict(data)))
        if event == "user_message":
            main_entered.set()
            await release_main.wait()

    room.set_turn_runner(slow_main_turn)
    room.wire_event_sink()

    try:
        asyncio.ensure_future(room.handle_room_event(conv_id, "user_message", {"content": "test"}))
        await asyncio.wait_for(main_entered.wait(), timeout=3.0)

        results = {}

        async def runner_fast(task):
            await asyncio.sleep(0.015)
            return {"role_done": task.role, "ok": True}

        async def runner_slow(task):
            await asyncio.sleep(0.09)
            return {"role_done": task.role, "ok": True}

        sub_runner.set_default_runner(runner_fast)
        out1 = await orch_dispatch_impl(conv_id, "credit", "fast case", "brief fast")
        results["credit"] = out1

        sub_runner.set_default_runner(runner_slow)
        out2 = await orch_dispatch_impl(conv_id, "legal", "slow case", "brief slow")
        results["legal"] = out2

        await asyncio.sleep(0.2)

        release_main.set()
        await asyncio.sleep(0.15)

        return {"wakes": wakes, "dispatch_results": results}
    finally:
        room.set_turn_runner(None)
        sub_runner.set_default_runner(None)
        registry.reset_room(conv_id)


async def _run_once(run_label: str) -> None:
    conv_id = f"tester-d33-{run_label}"
    result = await _staggered_via_dispatch_impl(conv_id)
    wakes = result["wakes"]

    user_wakes = [w for w in wakes if w[0] == "user_message"]
    task_wakes = [w for w in wakes if w[0] == "task_done"]

    assert len(user_wakes) == 1, "Expected invariant was not satisfied at source line 97."
    assert len(task_wakes) == 2, "Expected invariant was not satisfied at source line 98."

    roles_woken = sorted(w[1].get("role") for w in task_wakes)
    assert roles_woken == ["credit", "legal"], "Expected invariant was not satisfied at source line 103."

    assert registry.get_running_task_id(conv_id, "credit") is None, (
        "Expected invariant was not satisfied at source line 105."
    )
    assert registry.get_running_task_id(conv_id, "legal") is None, (
        "Expected invariant was not satisfied at source line 108."
    )

    assert result["dispatch_results"]["credit"]["created"] is True
    assert result["dispatch_results"]["legal"]["created"] is True


@pytest.mark.asyncio
async def test_staggered_concurrency_run_1():
    await _run_once("run1")


@pytest.mark.asyncio
async def test_staggered_concurrency_run_2():
    await _run_once("run2")


@pytest.mark.asyncio
async def test_staggered_concurrency_run_3():
    await _run_once("run3")
