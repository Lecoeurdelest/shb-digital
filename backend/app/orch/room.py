from __future__ import annotations

from typing import Any

from app.orch import registry, sub_runner

_DEDUP_EVENTS = {"task_done"}


async def try_acquire(conv_id: str, event: str, data: dict) -> bool:

    async with registry.room_lock:
        if not registry.is_busy(conv_id):
            registry.mark_busy(conv_id)
            return True
        q = registry.queue_for(conv_id)
        q.append((event, data))
        while len(q) > registry.MAX_QUEUE:
            idx = next((i for i, (e, _) in enumerate(q) if e == "task_done"), None)
            if idx is None:
                break
            q.pop(idx)
        return False


async def release(conv_id: str) -> tuple[str, dict] | None:

    async with registry.room_lock:
        registry.clear_busy(conv_id)
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
        registry.set_queue(conv_id, deduped[1:])
        return deduped[0]


_turn_runner: Any = None


def set_turn_runner(runner: Any) -> None:

    global _turn_runner
    _turn_runner = runner


async def handle_room_event(conv_id: str, event: str, data: dict) -> None:

    import asyncio

    if not await try_acquire(conv_id, event, data):
        return
    try:
        if _turn_runner is not None:
            await _turn_runner(conv_id, event, data)

    finally:
        nxt = await release(conv_id)
        if nxt is not None:
            asyncio.ensure_future(handle_room_event(conv_id, nxt[0], nxt[1]))


async def _event_sink(conv_id: str, event: str, data: dict) -> None:
    await handle_room_event(conv_id, event, data)


def wire_event_sink() -> None:

    sub_runner.set_event_sink(_event_sink)
