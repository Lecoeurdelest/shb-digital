"""Slot/queue 1-lượt/phòng + handle_room_event (wake→work→sleep). multi-agent §1+§2.

Luật: tại 1 thời điểm CHỈ 1 lượt main/phòng. Event tới → try_acquire (rảnh→chạy, bận→queue).
release nhả HẲN slot rồi trả event kế (KHÔNG re-acquire — ghost-slot). Dedup CHỈ task_done
theo role; user_message/approval_decided KHÔNG BAO GIỜ dedup/drop (nuốt = phòng kẹt vĩnh viễn).

handle_room_event = hàm trung tâm 1 lượt (T1-3 gọi khi user_message). close-on-done: main
connect+disconnect trong CÙNG thân hàm này (1 asyncio task) — KHÔNG cache client qua event
(cross-task disconnect = treo im lặng, session.py đã trả giá).
"""

from __future__ import annotations

from typing import Any

from app.orch import registry, sub_runner

# Event máy CÓ khoá tự nhiên → dedup được. user_message/approval_decided KHÔNG.
_DEDUP_EVENTS = {"task_done"}


async def try_acquire(conv_id: str, event: str, data: dict) -> bool:
    """True = caller chạy lượt. False = đã xếp hàng. KHÔNG interrupt hộ ai (§4.3).

    Cap queue MAX_QUEUE: đầy → CHỈ drop task_done cũ nhất (còn lưới đỡ bảng việc);
    user_message/approval_decided KHÔNG BAO GIỜ drop.
    """
    async with registry.room_lock:
        if not registry.is_busy(conv_id):
            registry.mark_busy(conv_id)
            return True
        q = registry.queue_for(conv_id)
        q.append((event, data))
        while len(q) > registry.MAX_QUEUE:
            idx = next((i for i, (e, _) in enumerate(q) if e == "task_done"), None)
            if idx is None:
                break  # không có task_done để drop → giữ nguyên (không drop lệnh người)
            q.pop(idx)
        return False


async def release(conv_id: str) -> tuple[str, dict] | None:
    """Nhả slot HẲN rồi trả event kế (handler mới TỰ acquire — KHÔNG re-acquire = ghost-slot).

    Dedup CHỈ task_done theo role (giữ bản mới nhất). user_message/approval_decided giữ đủ
    từng cái. Phần còn lại của queue để lại cho vòng drain kế.
    """
    async with registry.room_lock:
        registry.clear_busy(conv_id)  # nhả trước, KHÔNG re-acquire
        q = registry.pop_queue(conv_id)
        if not q:
            return None
        seen_roles: set[str] = set()
        deduped: list[tuple[str, dict]] = []
        for evt, data in reversed(q):
            if evt in _DEDUP_EVENTS:
                role = data.get("role")
                if role in seen_roles:
                    continue
                seen_roles.add(role)
            deduped.append((evt, data))
        deduped.reverse()
        registry.set_queue(conv_id, deduped[1:])  # phần còn lại chờ drain kế
        return deduped[0]


# Handler 1 lượt — main_session gán qua set_turn_runner (SDK thật); test thay fake.
_turn_runner: Any = None


def set_turn_runner(runner: Any) -> None:
    """main_session đăng ký hàm chạy 1 lượt main SDK (resume + stream). Signature:
    async fn(conv_id, event, data) -> None."""
    global _turn_runner
    _turn_runner = runner


async def handle_room_event(conv_id: str, event: str, data: dict) -> None:
    """Hàm trung tâm: acquire → chạy lượt main → persist → nhả slot → DRAIN event kế.

    Vòng drain TỰ KHÉP: finally release → có event kế thì spawn handler mới → handler mới
    try_acquire sạch → chạy → release… tới khi queue rỗng.
    """
    import asyncio

    if not await try_acquire(conv_id, event, data):
        return  # đã xếp hàng — vòng drain sẽ nhặt
    try:
        if _turn_runner is not None:
            await _turn_runner(conv_id, event, data)
        # _turn_runner None (test mechanics thuần / SDK chưa boot): chỉ xoay slot/queue
    finally:
        nxt = await release(conv_id)
        if nxt is not None:
            asyncio.ensure_future(handle_room_event(conv_id, nxt[0], nxt[1]))


# Nối sub_runner._report → hàng đợi phòng: sub xong → task_done vào queue đánh thức main.
async def _event_sink(conv_id: str, event: str, data: dict) -> None:
    await handle_room_event(conv_id, event, data)


def wire_event_sink() -> None:
    """Đăng ký _event_sink cho sub_runner (gọi lúc boot / test setup)."""
    sub_runner.set_event_sink(_event_sink)
