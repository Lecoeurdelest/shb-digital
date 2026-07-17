"""[TESTER pre-scaffold — T1-5 nhánh 2] 3 ca đinh spine T1-2 + ca DSCR gate.

SỞ HỮU: tester (Test ownership T1-4/T1-5 brief). KHÔNG phải test do backend viết —
đây là bài test ĐỘC LẬP viết từ Exports cam kết trong dispatch T1-2 (Cairn #2), trước khi
code hạ cánh. Cấm backend sửa file này để "cho pass" — sai thì báo tester qua [FAIL], không
tự sửa test (author != checker, CLAUDE.md §6).

Tới khi `app/orch/` tồn tại, mọi test ở đây SKIP có lý do rõ ràng (không lỗi import mập mờ).
Khi T1-2 hạ cánh, tester gỡ skip-guard, chạy thật, verify theo tester.md.

Nguồn ca đinh: Cairn #2 (T1-2) mục "## Verification (gate T1-2)" + multi-agent.md §2/§4/§5.
"""

from __future__ import annotations

import asyncio
import importlib.util

import pytest

_ORCH_AVAILABLE = importlib.util.find_spec("app.orch") is not None

pytestmark = pytest.mark.skipif(
    not _ORCH_AVAILABLE,
    reason="app/orch/ chưa hạ cánh (T1-2 in_progress) — pre-scaffold chờ Exports thật. "
    "Xem Cairn #2 Exports: orch.dispatch.orch_dispatch/create_task_guarded, "
    "orch.room.handle_room_event, orch.sub_runner._report, orch.registry, orch.main_session.",
)


# ─────────────────────────────────────────────────────────────────────────
# Ca đinh (a) — Idempotent dispatch: 2 lần cùng role sát nhau → 1 task,
# lần 2 created:false + registry chỉ có 1 entry (multi-agent §4, spec §4.1/§15).
# Đường tắt (KHÔNG check registry trong lock, chỉ check DB status) sẽ FAIL ca này
# khi 2 lệnh lách qua khe await gần như đồng thời.
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_idempotent_same_role_twice_returns_existing():
    from app.orch.dispatch import create_task_guarded

    conv_id = "tester-ca-a-conv"
    role = "credit"

    task1, existing1 = await create_task_guarded(conv_id, role, "Thẩm định lần 1", "input A")
    assert task1 is not None, "Lần 1 phải tạo task mới"
    assert existing1 is None

    task2, existing2 = await create_task_guarded(conv_id, role, "Thẩm định lần 2 (trùng)", "input B")
    assert task2 is None, "Lần 2 PHẢI trả (None, existing) — không tạo task thứ 2"
    assert existing2 is not None
    assert existing2.id == task1.id, "existing phải LÀ task lần 1 — không phải task mới khác"


@pytest.mark.asyncio
async def test_dispatch_idempotent_race_two_near_simultaneous_calls():
    """Lách khe await: bắn 2 create_task_guarded gần như đồng thời qua asyncio.gather —
    nếu check+create không nằm trong CÙNG 1 lock/đoạn atomic, cả 2 sẽ pass qua check
    trước khi cái nào kịp đăng ký registry → 2 task. Đây là ca "đường tắt fail"."""
    from app.orch.dispatch import create_task_guarded

    conv_id = "tester-ca-a-race-conv"
    role = "credit"

    results = await asyncio.gather(
        create_task_guarded(conv_id, role, "race-1", "in1"),
        create_task_guarded(conv_id, role, "race-2", "in2"),
    )
    created_count = sum(1 for task, _ in results if task is not None)
    assert created_count == 1, f"Race 2 dispatch đồng thời phải chỉ 1 cái tạo task, được {created_count}"


# ─────────────────────────────────────────────────────────────────────────
# Ca đinh (b) — Invariant sống còn: MỌI kết cục sub (done/failed/timeout/cancel)
# → ĐÚNG MỘT event task_done. Đường tắt (quên nhánh cancel/timeout, hoặc emit rải
# theo từng except thay vì 1 điểm hội tụ finally) FAIL ca này.
# ─────────────────────────────────────────────────────────────────────────


def _tester_task(conv_id: str, role: str = "credit", tid: str = "tester-task-1"):
    """Fixture task ĐỘC LẬP — tester tự dựng, không import fixture của backend
    (test_orch_invariant.py có _fake_task riêng — KHÔNG dùng chung để giữ độc lập kiểm định)."""
    from app.orch.store import Task

    return Task(id=tid, conv_id=conv_id, role=role, title="tester ca invariant", status="queued")


@pytest.fixture
def _isolated_store(monkeypatch):
    """Cô lập DB cho ca invariant: store.mark_running/finish_task/task_board thành no-op.
    Tester tự viết stub riêng (không tái dùng monkeypatch fixture của backend)."""
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
    """Sink đếm event task_done — bản tester tự viết, độc lập bản backend."""
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

    assert len(events) == 1, f"kết cục done PHẢI đúng 1 event task_done, có {len(events)}: {events}"
    assert events[0]["event"] == "task_done"
    assert events[0]["data"]["outcome"] == "done"
    assert events[0]["data"]["role"] == "credit"
    # task_id KHÔNG lên mặt tool nhưng CÓ trong payload nội bộ (spec §4.1) — verify đúng chỗ
    assert events[0]["data"]["task_id"] == "t-done"
    registry.reset_room("tester-inv-done")


@pytest.mark.asyncio
async def test_sub_outcome_failed_emits_exactly_one_event(_isolated_store):
    from app.orch import registry, sub_runner

    registry.reset_room("tester-inv-failed")
    events = await _sink_counter()

    async def runner_raise(task):
        raise ValueError("tool nổ giả lập — tester ép nhánh Exception")

    await sub_runner._run_sub(_tester_task("tester-inv-failed", tid="t-failed"), runner=runner_raise)

    assert len(events) == 1, f"kết cục failed PHẢI đúng 1 event, có {len(events)}: {events}"
    assert events[0]["data"]["outcome"] == "failed"
    assert "tool nổ giả lập" in events[0]["data"]["result_summary"], "reason lỗi phải lọt vào summary cho main đọc"
    registry.reset_room("tester-inv-failed")


@pytest.mark.asyncio
async def test_sub_outcome_timeout_emits_exactly_one_event(_isolated_store):
    """Landmine nêu trong dispatch: cám dỗ 'timeout thì thôi' — PHẢI báo, không im."""
    from app.orch import registry, sub_runner

    registry.reset_room("tester-inv-timeout")
    events = await _sink_counter()

    async def runner_timeout(task):
        raise sub_runner.IdleTimeout()

    await sub_runner._run_sub(_tester_task("tester-inv-timeout", tid="t-timeout"), runner=runner_timeout)

    assert len(events) == 1, f"kết cục timeout PHẢI đúng 1 event (không được im), có {len(events)}: {events}"
    assert events[0]["data"]["outcome"] == "timeout"
    registry.reset_room("tester-inv-timeout")


@pytest.mark.asyncio
async def test_sub_outcome_cancel_emits_exactly_one_event_not_swallowed(_isolated_store):
    """Ca THEN CHỐT nhất T1-2 (multi-agent §5): CancelledError là BaseException —
    except Exception KHÔNG bắt được. finally phải asyncio.shield() cả disconnect lẫn
    _report(), nếu không cancel nuốt luôn event → phòng treo vĩnh viễn.

    Tester tự dựng lại kịch bản (không copy backend): spawn sub treo vô hạn qua
    asyncio.Event đồng bộ hoá, cancel giữa chừng, verify event VẪN ra đúng 1 lần
    VÀ CancelledError propagate đúng ra ngoài (không bị finally/shield nuốt luôn exception)."""
    from app.orch import registry, sub_runner

    registry.reset_room("tester-inv-cancel")
    events = await _sink_counter()
    sub_is_running = asyncio.Event()

    async def runner_hang_forever(task):
        sub_is_running.set()
        await asyncio.sleep(3600)  # không bao giờ tự xong — chỉ thoát qua cancel

    t = sub_runner.spawn_sub(_tester_task("tester-inv-cancel", tid="t-cancel"), runner=runner_hang_forever)
    await asyncio.wait_for(sub_is_running.wait(), timeout=2.0)

    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t  # CancelledError phải propagate ra ngoài — task đã bị hủy thật

    # Điểm cốt lõi ca thử: DÙ task bị cancel, _report vẫn phải chạy qua shield → đúng 1 event.
    # Thiếu asyncio.shield() quanh _report trong finally → CancelledError nuốt luôn await đó →
    # events rỗng → phòng treo vĩnh viễn (invariant §5 vỡ, bug ẩn khó thấy nhất của T1-2).
    assert len(events) == 1, (
        f"cancel PHẢI vẫn sinh đúng 1 event (shield bảo vệ _report) — có {len(events)}. "
        "Rỗng nghĩa là thiếu asyncio.shield() quanh _report trong finally của _run_sub → "
        "phòng treo vĩnh viễn khi user hủy sub."
    )
    assert events[0]["data"]["outcome"] == "failed", "hủy = kết cục failed (không phải done/timeout)"
    assert "hủy" in events[0]["data"]["result_summary"], "result phải nói rõ lý do là user hủy"
    registry.reset_room("tester-inv-cancel")


# ─────────────────────────────────────────────────────────────────────────
# Ca đinh (c) — Slot/queue 1-lượt/phòng: phòng bận → event xếp hàng, KHÔNG nuốt.
# user_message/approval_decided KHÔNG BAO GIỜ dedup — 2 user_message liên tiếp
# khi phòng bận đều phải TỚI TAY main (multi-agent §2, spec §4.2).
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_room_busy_one_runs_one_queues():
    from app.orch import registry, room

    conv_id = "tester-ca-c-conv"
    registry.reset_room(conv_id) if hasattr(registry, "reset_room") else None

    acquired1 = await room.try_acquire(conv_id, "user_message", {"content": "câu 1"})
    assert acquired1 is True, "Phòng rảnh — lần 1 phải acquire được ngay"

    acquired2 = await room.try_acquire(conv_id, "user_message", {"content": "câu 2"})
    assert acquired2 is False, "Phòng đang bận (chưa release) — lần 2 phải xếp hàng, KHÔNG chạy song song"


@pytest.mark.asyncio
async def test_two_user_messages_while_busy_both_reach_main_no_dedup():
    """user_message KHÔNG có khóa tự nhiên như task_done(role) — dedup nó = nuốt lệnh người,
    phòng kẹt vĩnh viễn (spec §4.2, multi-agent §2 bẫy 'dedup mọi loại event chung 1 khóa').
    Đây là ca đường-tắt-fail: nếu implementer lỡ áp dedup chung cho mọi event type,
    2 tin liên tiếp sẽ chỉ còn 1 tin sống sót — FAIL. Test drain HẾT queue (không chỉ 1 lần
    release) và đếm cả 2 nội dung phải xuất hiện, không tin nào biến mất."""
    from app.orch import registry, room

    conv_id = "tester-ca-c-nodedup-conv"
    registry.reset_room(conv_id)

    # Phòng đang RẢNH — acquire lần 1 thành công (giả lập lượt đang chạy), 2 tin sau xếp hàng
    acquired0 = await room.try_acquire(conv_id, "user_message", {"content": "tin đang chạy"})
    assert acquired0 is True
    acquired1 = await room.try_acquire(conv_id, "user_message", {"content": "tin 1"})
    acquired2 = await room.try_acquire(conv_id, "user_message", {"content": "tin 2"})
    assert acquired1 is False and acquired2 is False, "phòng bận — cả 2 tin phải xếp hàng, không chạy chen"

    # release() lần đầu (kết lượt "tin đang chạy") → trả 1 event kế; registry.queue_for lộ
    # PHẦN CÒN LẠI thật trong queue (đọc thẳng state, không đoán qua acquire/release vòng vèo).
    first = await room.release(conv_id)
    assert first is not None
    contents_seen = [first[1]["content"]]
    remaining = registry.queue_for(conv_id)  # room.release() đã set_queue phần dư qua registry
    contents_seen += [data["content"] for _evt, data in remaining if "content" in data]

    assert "tin 1" in contents_seen, f"tin 1 KHÔNG ĐƯỢC biến mất — dedup nhầm user_message. Thấy: {contents_seen}"
    assert "tin 2" in contents_seen, f"tin 2 KHÔNG ĐƯỢC biến mất — dedup nhầm user_message. Thấy: {contents_seen}"
    registry.reset_room(conv_id)


@pytest.mark.asyncio
async def test_release_does_not_reacquire_ghost_slot():
    """Bẫy ghost-slot: release() re-acquire hộ handler kế → handler mới try_acquire thấy
    slot ĐANG GIỮ → tự xếp hàng lại → queue kẹt vĩnh viễn dù không còn ai chạy thật."""
    from app.orch import room

    conv_id = "tester-ca-c-ghostslot-conv"
    await room.try_acquire(conv_id, "user_message", {"content": "tin 1"})
    await room.release(conv_id)

    acquired_after_release = await room.try_acquire(conv_id, "user_message", {"content": "tin mới"})
    assert acquired_after_release is True, (
        "Sau release() slot phải nhả HẲN — try_acquire kế phải thành công ngay, không bị 'ghost-slot' chặn lại"
    )


# Ca GATE S1 end-to-end: T1-3 đã hạ cánh — bài test THẬT chuyển sang file riêng
# `test_gate_s1_e2e.py` (giữ tách khỏi pytestmark module-level skipif ở đầu file này,
# và theo đúng pattern opt-in live-SDK backend đã dùng ở test_orch_live_smoke.py).
