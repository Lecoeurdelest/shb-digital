"""[BACKEND] Test invariant _report 1-điểm-hội-tụ + seam 4 kết cục + drain thật.

Bổ sung cho tester pre-scaffold (test_orch_spine_tester.py) — phần cần seam/fixture thật.
Seam: _run_sub(task, runner=fake) → mock done/failed/timeout/cancel KHÔNG cần SDK.
"""

from __future__ import annotations

import asyncio

import pytest

from app.orch import registry, room, store, sub_runner
from app.orch.store import Task


def _fake_task(conv_id="inv-conv", role="credit", tid="task-inv-1") -> Task:
    return Task(id=tid, conv_id=conv_id, role=role, title="t", status="queued")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Cách ly DB + registry mỗi test: mock store ghi/đọc thành no-op, đếm event qua sink."""
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
    """Đăng ký sink đếm event task_done. Trả list được append (outcome, payload)."""
    events = []

    async def sink(conv_id, event, data):
        events.append((event, data))

    sub_runner.set_event_sink(sink)
    return events


# ── Invariant: mỗi kết cục → ĐÚNG 1 event ───────────────────────────────────


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
        raise RuntimeError("tool nổ")

    await sub_runner._run_sub(_fake_task(), runner=runner_raise)
    assert len(events) == 1
    assert events[0][1]["outcome"] == "failed"
    assert "tool nổ" in events[0][1]["result_summary"]


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
    """CancelledError (BaseException) → gán outcome + re-raise; finally shield _report.
    Ca THEN CHỐT: thiếu shield → 0 event → phòng treo."""
    events = await _collect_events()
    started = asyncio.Event()

    async def runner_hang(task):
        started.set()
        await asyncio.sleep(100)  # treo tới khi bị cancel

    t = sub_runner.spawn_sub(_fake_task(), runner=runner_hang)
    await started.wait()
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t
    # DÙ bị cancel, _report VẪN chạy (shield) → đúng 1 event
    assert len(events) == 1
    assert events[0][1]["outcome"] == "failed"
    assert events[0][1]["result_summary"].find("user hủy") >= 0


# ── unregister-on-report: sub xong → dispatch LẠI cùng role → created:true ──


@pytest.mark.asyncio
async def test_report_unregisters_role_allowing_redispatch(monkeypatch):
    """Advisor bug gate-không-bắt: quên unregister (conv,role) trong _report → role khoá
    vĩnh viễn. Sau _report, get_running_task_id phải None."""
    await _collect_events()
    conv, role = "unreg-conv", "credit"
    registry.register_running(conv, role, "task-x")
    assert registry.get_running_task_id(conv, role) == "task-x"

    async def runner_done(task):
        return {"ok": True}

    await sub_runner._run_sub(
        Task(id="task-x", conv_id=conv, role=role, title="t", status="queued"), runner=runner_done
    )
    # _report gỡ registry ĐẦU TIÊN → role mở lại
    assert registry.get_running_task_id(conv, role) is None


# ── drain THỰC SỰ chạy event đã queue (không chỉ xếp) ───────────────────────


@pytest.mark.asyncio
async def test_drain_runs_queued_event_after_release():
    """Ghost-slot check: 2 event tới lúc bận → 1 chạy 1 queue; sau lượt 1 xong (release),
    drain PHẢI chạy event queued. Đếm số lần _turn_runner được gọi = 2."""
    registry.reset_room("drain-conv")
    ran = []

    async def turn_runner(conv_id, event, data):
        ran.append(data.get("content"))
        await asyncio.sleep(0)  # nhường loop

    room.set_turn_runner(turn_runner)
    try:
        # 2 event gần đồng thời: cái 1 chạy, cái 2 xếp → drain chạy nốt
        await asyncio.gather(
            room.handle_room_event("drain-conv", "user_message", {"content": "tin 1"}),
            room.handle_room_event("drain-conv", "user_message", {"content": "tin 2"}),
        )
        await asyncio.sleep(0.05)  # cho vòng drain spawn chạy xong
        assert len(ran) == 2, f"cả 2 tin phải chạy (drain thật), chạy {len(ran)}: {ran}"
        assert set(ran) == {"tin 1", "tin 2"}
    finally:
        room.set_turn_runner(None)
        registry.reset_room("drain-conv")


@pytest.mark.asyncio
async def test_ctx_actor_not_leaked_from_sub_to_main_reentrant():
    """Brief §E: CTX_ACTOR phải set 'main' đầu run_main_turn — nếu không, re-entrant path
    (sub done → _report → _event_sink → handle_room_event → run_main_turn CHẠY TRONG task sub)
    leak CTX_ACTOR = role sub → audit mis-attribute lượt main. Mock turn_runner đọc CTX lúc chạy."""

    registry.reset_room("ctx-conv")
    seen_actor = []

    async def fake_run_main_turn(conv_id, event, data):
        # main_session._turn_runner thật gọi run_main_turn (set CTX). Ở đây mô phỏng đúng thứ tự:
        registry.CTX_CONV.set(conv_id)
        registry.CTX_ACTOR.set("main")
        seen_actor.append(registry.CTX_ACTOR.get())

    room.set_turn_runner(fake_run_main_turn)

    async def sink(conv_id, event, data):
        await room.handle_room_event(conv_id, event, data)

    sub_runner.set_event_sink(sink)

    # runner sub set actor=role; sau _report → sink → turn_runner phải thấy 'main' (không leak 'credit')
    async def runner_done(task):
        assert registry.CTX_ACTOR.get() == "credit", "trong sub, actor=role"
        return {"ok": True}

    monkeypatch_store = {}
    try:
        # store no-op để không chạm DB
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
        assert seen_actor == ["main"], f"lượt main phải thấy actor='main', thấy {seen_actor}"
    finally:
        import app.orch.store as st

        if "orig" in monkeypatch_store:
            st.mark_running, st.finish_task, st.task_board = monkeypatch_store["orig"]
        room.set_turn_runner(None)
        registry.reset_room("ctx-conv")


@pytest.mark.asyncio
async def test_ctx_task_not_leaked_from_sub_to_main_reentrant(monkeypatch):
    """Tester T2-4 bug: CTX_TASK phải reset '' đầu run_main_turn — nếu không, re-entrant D-33 inline
    (sub set CTX_TASK=task.id → _report → sink → run_main_turn TRONG task sub) leak CTX_TASK = sub
    task.id → MAIN present bị stamp task_id sub thay vì null (vi phạm T2-1 N5).

    Test đường THẬT: sub _run_sub (set CTX_TASK=task.id) → _report → sink → _turn_runner THẬT →
    run_main_turn THẬT. Monkeypatch phần SDK của run_main_turn (chặn TRƯỚC ClaudeSDKClient) để đọc
    CTX_TASK NGAY SAU 3 dòng reset — verify DÒNG FIX thật, không mirror tự-xác-nhận."""
    from app.orch import main_session

    registry.reset_room("ctxt-conv")
    seen_task = []

    # Chặn run_main_turn tại ClaudeSDKClient: dòng reset CTX (đầu hàm) ĐÃ chạy → đọc CTX_TASK thật.
    class _StopHere(Exception):
        pass

    def _boom(*a, **k):
        seen_task.append(registry.CTX_TASK.get() or None)  # đọc SAU 3 dòng reset thật
        raise _StopHere

    # run_main_turn LOCAL-import ClaudeSDKClient từ claude_agent_sdk → monkeypatch tại nguồn
    import claude_agent_sdk

    monkeypatch.setattr(claude_agent_sdk, "ClaudeSDKClient", _boom, raising=False)

    async def noop(*a, **k):
        return None

    monkeypatch.setattr(main_session.store, "get_conv_session_id", noop)

    async def fake_turn(conv_id, event, data):
        try:
            await main_session.run_main_turn(conv_id, "prompt")  # THẬT — chạy 3 dòng reset rồi _boom
        except _StopHere:
            pass

    room.set_turn_runner(fake_turn)

    async def sink(conv_id, event, data):
        await room.handle_room_event(conv_id, event, data)

    sub_runner.set_event_sink(sink)

    async def runner_done(task):
        assert registry.CTX_TASK.get() == "ctxt-t", "trong sub, CTX_TASK=task.id"
        return {"ok": True}

    monkeypatch.setattr(sub_runner.store, "mark_running", noop)
    monkeypatch.setattr(sub_runner.store, "finish_task", noop)
    monkeypatch.setattr(sub_runner.store, "get_task", noop)  # _emit_task_status (T2-1 SSE) không chạm DB

    async def board(*a, **k):
        return []

    monkeypatch.setattr(sub_runner.store, "task_board", board)
    try:
        await sub_runner._run_sub(
            Task(id="ctxt-t", conv_id="ctxt-conv", role="products", title="t", status="queued"),
            runner=runner_done,
        )
        await asyncio.sleep(0.02)
        # run_main_turn THẬT reset CTX_TASK='' → MAIN present thấy None (không leak 'ctxt-t')
        assert seen_task == [None], f"MAIN present phải thấy task_id=None (dòng reset thật), thấy {seen_task}"
    finally:
        room.set_turn_runner(None)
        registry.reset_room("ctxt-conv")
