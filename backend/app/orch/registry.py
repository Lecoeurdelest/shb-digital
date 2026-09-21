from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import Any

CTX_CONV: ContextVar[str] = ContextVar("conversation_id", default="")
CTX_ACTOR: ContextVar[str] = ContextVar("actor", default="")


CTX_TASK: ContextVar[str] = ContextVar("task_id", default="")


_busy_rooms: set[str] = set()
_event_queues: dict[str, list[tuple[str, dict]]] = {}
room_lock = asyncio.Lock()
MAX_QUEUE = 50

# ── Registry idempotency dispatch (dispatch.py) — (conv_id, role) -> task_id ─
_running_tasks: dict[tuple[str, str], str] = {}
dispatch_lock = asyncio.Lock()


sub_tasks: dict[str, asyncio.Task] = {}


_sub_semaphores: dict[str, asyncio.Semaphore] = {}
SUB_CONCURRENCY = 4


main_clients: dict[str, Any] = {}


def sub_semaphore(conv_id: str) -> asyncio.Semaphore:

    if conv_id not in _sub_semaphores:
        _sub_semaphores[conv_id] = asyncio.Semaphore(SUB_CONCURRENCY)
    return _sub_semaphores[conv_id]


def get_running_task_id(conv_id: str, role: str) -> str | None:
    return _running_tasks.get((conv_id, role))


def register_running(conv_id: str, role: str, task_id: str) -> None:
    _running_tasks[(conv_id, role)] = task_id


def unregister_running(conv_id: str, role: str) -> None:

    _running_tasks.pop((conv_id, role), None)


def is_busy(conv_id: str) -> bool:
    return conv_id in _busy_rooms


def mark_busy(conv_id: str) -> None:
    _busy_rooms.add(conv_id)


def clear_busy(conv_id: str) -> None:

    _busy_rooms.discard(conv_id)


def queue_for(conv_id: str) -> list[tuple[str, dict]]:
    return _event_queues.setdefault(conv_id, [])


def pop_queue(conv_id: str) -> list[tuple[str, dict]]:
    return _event_queues.pop(conv_id, [])


def set_queue(conv_id: str, events: list[tuple[str, dict]]) -> None:
    if events:
        _event_queues[conv_id] = events
    else:
        _event_queues.pop(conv_id, None)


def reset_room(conv_id: str) -> None:

    _busy_rooms.discard(conv_id)
    _event_queues.pop(conv_id, None)
    _sub_semaphores.pop(conv_id, None)
    main_clients.pop(conv_id, None)
    for key in [k for k in _running_tasks if k[0] == conv_id]:
        _running_tasks.pop(key, None)


def reset_all() -> None:

    _busy_rooms.clear()
    _event_queues.clear()
    _running_tasks.clear()
    sub_tasks.clear()
    _sub_semaphores.clear()
    main_clients.clear()
