"""[BACKEND] TEST D-33 (advisor): concurrency STAGGERED — sub xong KHI main-turn in-flight.

Mục đích: test inline-await _report→handle_room_event dưới concurrency THẬT (không sequential).
2+ sub delay KHÁC NHAU → task_done tới KHI main đang chạy lượt (busy) → phải: mỗi task_done
đúng 1 main wake, no lost/double event, board consistent. GREEN đóng D-33 note; RED → §6-spawn.

Chạy 3× (test nhạy-concurrency, multi-agent §6b — vài run không phải thống kê).
"""

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
    """Kịch bản staggered: main-turn CHẬM đang chạy khi 2 sub (fast+slow) báo task_done.

    Đếm: mỗi task_done → main wake. Verify no lost (đủ N wake) / no double (không >N).
    """
    conv = "d33-conv"
    registry.reset_room(conv)
    wakes: list[str] = []
    main_running = asyncio.Event()
    release_main = asyncio.Event()

    async def slow_turn_runner(conv_id, event, data):
        # Main-turn CHẬM: giữ slot mở tới khi test cho phép → sub task_done tới lúc BUSY
        wakes.append(event)
        if event == "user_message":
            main_running.set()
            await release_main.wait()  # giữ lượt main in-flight
        else:
            await asyncio.sleep(0)  # task_done wake — xử nhanh

    room.set_turn_runner(slow_turn_runner)
    room.wire_event_sink()  # _report → handle_room_event

    try:
        # 1. user_message → main-turn CHẬM bắt đầu (giữ slot)
        asyncio.ensure_future(room.handle_room_event(conv, "user_message", {"content": "hỏi"}))
        await main_running.wait()  # main đang IN-FLIGHT (busy)

        # 2. 2 sub với DELAY khác nhau → task_done tới KHI main busy (staggered)
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
        await asyncio.gather(t_fast, t_slow)  # cả 2 sub xong (task_done ĐÃ enqueue vì main busy)

        # 3. nhả main-turn → drain xử các task_done đã queue
        release_main.set()
        await asyncio.sleep(0.1)  # cho vòng drain chạy hết

        return {"wakes": wakes}
    finally:
        room.set_turn_runner(None)
        registry.reset_room(conv)


@pytest.mark.asyncio
@pytest.mark.parametrize("run", [1, 2, 3])  # 3× — test nhạy concurrency
async def test_staggered_each_task_done_exactly_one_wake(run):
    result = await _run_staggered_scenario()
    wakes = result["wakes"]
    # 1 user_message + đúng 2 task_done (mỗi sub 1 wake, no lost/double)
    user_wakes = [w for w in wakes if w == "user_message"]
    task_wakes = [w for w in wakes if w == "task_done"]
    assert len(user_wakes) == 1, f"run{run}: 1 user_message wake, got {len(user_wakes)}"
    assert len(task_wakes) == 2, (
        f"run{run}: 2 task_done wake (mỗi sub đúng 1, no lost/double), got {len(task_wakes)}: {wakes}"
    )


@pytest.mark.asyncio
async def test_two_sub_dispatch_both_report_no_event_lost():
    """4-sub-style: nhiều sub xong gần đồng thời → mọi task_done tới main (không nuốt)."""
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
        # 4 sub → 4 task_done event, không mất role nào
        assert sorted(events) == sorted(roles), f"đủ 4 task_done, got {events}"
    finally:
        sub_runner.set_event_sink(None)
        registry.reset_room(conv)
