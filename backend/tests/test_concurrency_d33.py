from __future__ import annotations

import asyncio

import pytest

from app.orch import registry, room, store, sub_runner
from app.orch.store import Task


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    registry.reset_all()

    async def noop(*a, **k):
        return []

    monkeypatch.setattr(store, "mark_running", noop)
    monkeypatch.setattr(store, "finish_task", noop)
    monkeypatch.setattr(store, "task_board", noop)
    yield
    registry.reset_all()


async def _run_staggered_scenario() -> dict:

    conv = "d33-conv"
    registry.reset_room(conv)
    wakes: list[str] = []
    main_running = asyncio.Event()
    release_main = asyncio.Event()

    async def slow_turn_runner(conv_id, event, data):

        wakes.append(event)
        if event == "user_message":
            main_running.set()
            await release_main.wait()
        else:
            await asyncio.sleep(0)

    room.set_turn_runner(slow_turn_runner)
    room.wire_event_sink()  # _report → handle_room_event

    try:
        asyncio.ensure_future(room.handle_room_event(conv, "user_message", {"content": "question"}))
        await main_running.wait()

        async def fast(task):
            await asyncio.sleep(0.02)
            return {"role": "credit", "ok": True}

        async def slow(task):
            await asyncio.sleep(0.08)
            return {"role": "legal", "ok": True}

        t_fast = sub_runner.spawn_sub(
            Task(id="tf", conv_id=conv, role="credit", title="c", status="queued"), runner=fast
        )
        t_slow = sub_runner.spawn_sub(
            Task(id="ts", conv_id=conv, role="legal", title="l", status="queued"), runner=slow
        )
        await asyncio.gather(t_fast, t_slow)

        release_main.set()
        await asyncio.sleep(0.1)

        return {"wakes": wakes}
    finally:
        room.set_turn_runner(None)
        registry.reset_room(conv)


@pytest.mark.asyncio
@pytest.mark.parametrize("run", [1, 2, 3])
async def test_staggered_each_task_done_exactly_one_wake(run):
    result = await _run_staggered_scenario()
    wakes = result["wakes"]

    user_wakes = [w for w in wakes if w == "user_message"]
    task_wakes = [w for w in wakes if w == "task_done"]
    assert len(user_wakes) == 1, f"run{run}: 1 user_message wake, got {len(user_wakes)}"
    assert len(task_wakes) == 2, "Expected invariant was not satisfied at source line 83."


@pytest.mark.asyncio
async def test_two_sub_dispatch_both_report_no_event_lost():

    conv = "d33-multi"
    registry.reset_room(conv)
    events = []

    async def sink(conv_id, event, data):
        events.append(data.get("role"))

    sub_runner.set_event_sink(sink)
    try:
        roles = ["credit", "legal", "products", "operations"]

        async def runner(task):
            await asyncio.sleep(0.01)
            return {"ok": True}

        tasks = [
            sub_runner.spawn_sub(Task(id=f"t{r}", conv_id=conv, role=r, title=r, status="queued"), runner=runner)
            for r in roles
        ]
        await asyncio.gather(*tasks)
        await asyncio.sleep(0.05)

        assert sorted(events) == sorted(roles), "Expected invariant was not satisfied at source line 113."
    finally:
        sub_runner.set_event_sink(None)
        registry.reset_room(conv)
