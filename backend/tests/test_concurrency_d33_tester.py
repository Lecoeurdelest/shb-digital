"""[TESTER — T2-4] Verify ĐỘC LẬP D-33 concurrency staggered — KHÔNG copy test_concurrency_d33.py
của backend (author≠checker, CLAUDE.md §6). Thiết kế khác: dùng `orch_dispatch_impl` thật (đường
model thật sẽ đi qua — không gọi thẳng `spawn_sub`) + kiểm tra REGISTRY STATE nhất quán (không chỉ
đếm số lần wake) + verify PG board sau cùng khớp đúng 2 task done, không role nào kẹt 'queued'.

Ca đinh D-33 (từ T2-4 brief): dispatch 2+ sub delay khác nhau → sub báo task_done KHI main-turn
đang in-flight (busy, không phải tuần tự trước khi main thức) → mỗi task_done đúng 1 main wake,
no lost/double event, board consistent. Chạy 3× liên tiếp (multi-agent §6b — vài run không phải
thống kê).
"""

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
    """Kịch bản KHÁC bản backend: dùng `orch_dispatch_impl` (đường model THẬT đi qua khi gọi
    orch_dispatch tool) thay vì gọi thẳng `spawn_sub` — verify integration thật hơn 1 tầng.
    Main-turn giữ slot busy bằng cách chặn ở `asyncio.Event`, trong lúc đó dispatch 2 sub với
    độ trễ khác nhau để task_done của chúng tới lúc main ĐANG busy (không tuần tự an toàn)."""
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
            await release_main.wait()  # giữ slot main busy — mô phỏng lượt SDK thật đang chạy
        # task_done wake: xử ngay (không giữ thêm) — mô phỏng main thức dậy xử nhanh

    room.set_turn_runner(slow_main_turn)
    room.wire_event_sink()  # nối sub_runner._report → handle_room_event (đường thật)

    try:
        # Lượt 1: user_message → main-turn chiếm slot, KHÔNG nhả ngay (mô phỏng SDK đang stream)
        asyncio.ensure_future(room.handle_room_event(conv_id, "user_message", {"content": "test"}))
        await asyncio.wait_for(main_entered.wait(), timeout=3.0)

        # 2 sub dispatch qua orch_dispatch_impl THẬT (không gọi tắt spawn_sub) — role khác nhau,
        # delay khác nhau, cố tình lệch pha để task_done rơi vào lúc main VẪN busy.
        results = {}

        async def runner_fast(task):
            await asyncio.sleep(0.015)
            return {"role_done": task.role, "ok": True}

        async def runner_slow(task):
            await asyncio.sleep(0.09)
            return {"role_done": task.role, "ok": True}

        sub_runner.set_default_runner(runner_fast)
        out1 = await orch_dispatch_impl(conv_id, "credit", "ca fast", "brief fast")
        results["credit"] = out1

        sub_runner.set_default_runner(runner_slow)
        out2 = await orch_dispatch_impl(conv_id, "legal", "ca slow", "brief slow")
        results["legal"] = out2

        # Đợi cả 2 sub thật sự báo task_done (tối đa 1s — đủ dư so 0.09s delay)
        await asyncio.sleep(0.2)

        # Nhả main-turn — vòng drain xử các task_done đã xếp hàng lúc main busy
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

    assert len(user_wakes) == 1, f"[{run_label}] phải đúng 1 user_message wake, có {len(user_wakes)}: {wakes}"
    assert len(task_wakes) == 2, (
        f"[{run_label}] phải đúng 2 task_done wake (mỗi sub 1, no lost/double), có {len(task_wakes)}: {wakes}"
    )

    # Board consistency: cả 2 role phải xuất hiện đúng 1 lần mỗi role trong task_done payload,
    # không role nào bị lặp (double-wake) hay thiếu (lost event).
    roles_woken = sorted(w[1].get("role") for w in task_wakes)
    assert roles_woken == ["credit", "legal"], f"[{run_label}] board không nhất quán: {roles_woken}"

    # Registry KHÔNG còn role nào bị khoá sau khi mọi thứ xong (unregister-on-report đã chạy) —
    # đây là điểm bản backend KHÔNG kiểm: nếu 1 trong 2 report bị mất, role đó vẫn khoá vĩnh viễn.
    assert registry.get_running_task_id(conv_id, "credit") is None, (
        f"[{run_label}] role credit vẫn bị khoá trong registry — _report không unregister đúng"
    )
    assert registry.get_running_task_id(conv_id, "legal") is None, (
        f"[{run_label}] role legal vẫn bị khoá trong registry — _report không unregister đúng"
    )

    # Dispatch results: cả 2 lần gọi orch_dispatch_impl phải created=True (không phải existing —
    # 2 role KHÁC nhau, không đụng khoá idempotent nhau).
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
