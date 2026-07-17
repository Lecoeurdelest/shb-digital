"""State điều phối in-process (N4: 1 worker, không Redis/distributed lock).

TẤT CẢ state ephemeral — restart là mất (boot-cleanup §7 dọn cờ DB mồ côi). Gom 1 chỗ để:
- slot/queue phòng (room.py dùng)          — 1 lượt/phòng
- registry idempotency (dispatch.py dùng)  — khoá (conv_id, role)
- sub asyncio tasks (sub_runner/interrupt) — hủy per-agent
- main clients đang trong lượt (interrupt) — hủy lượt main

ContextVar attribution (lab-joint §7): set dòng ĐẦU coroutine chạy lượt/sub — KHÔNG set ở cha
trước spawn (create_task copy context cha → set-ở-cha thì sub mang actor='main').
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import Any

# ── Attribution (audit/log biết ca nào, ai gọi, task nào) ───────────────────
CTX_CONV: ContextVar[str] = ContextVar("conversation_id", default="")
CTX_ACTOR: ContextVar[str] = ContextVar("actor", default="")
# CTX_TASK: task_id của sub đang chạy (present-tool inject vào card). Main gọi present ngoài
# sub task → default "" → card task_id null (main tờ trình không thuộc task nào — OK, T2-1 §C).
CTX_TASK: ContextVar[str] = ContextVar("task_id", default="")

# ── Slot + hàng đợi phòng (room.py) — 1 lượt/phòng ──────────────────────────
_busy_rooms: set[str] = set()
_event_queues: dict[str, list[tuple[str, dict]]] = {}
room_lock = asyncio.Lock()
MAX_QUEUE = 50

# ── Registry idempotency dispatch (dispatch.py) — (conv_id, role) -> task_id ─
_running_tasks: dict[tuple[str, str], str] = {}
dispatch_lock = asyncio.Lock()

# ── Sub asyncio tasks (sub_runner spawn, interrupt hủy) — task_id -> Task ────
sub_tasks: dict[str, asyncio.Task] = {}

# ── Semaphore cap đồng thời PER-PHÒNG (dispatch fan-out) ────────────────────
_sub_semaphores: dict[str, asyncio.Semaphore] = {}
SUB_CONCURRENCY = 4

# ── Main clients đang TRONG lượt (interrupt main) — conv_id -> client ────────
main_clients: dict[str, Any] = {}


def sub_semaphore(conv_id: str) -> asyncio.Semaphore:
    """Semaphore per-phòng (KHÔNG toàn hệ — ca này bóp cổ ca kia). Lazy."""
    if conv_id not in _sub_semaphores:
        _sub_semaphores[conv_id] = asyncio.Semaphore(SUB_CONCURRENCY)
    return _sub_semaphores[conv_id]


# ── Idempotency registry helpers (dispatch.py gọi trong dispatch_lock) ──────
def get_running_task_id(conv_id: str, role: str) -> str | None:
    return _running_tasks.get((conv_id, role))


def register_running(conv_id: str, role: str, task_id: str) -> None:
    _running_tasks[(conv_id, role)] = task_id


def unregister_running(conv_id: str, role: str) -> None:
    """Gỡ đăng ký (conv_id, role). Gọi TRONG _report — nơi MỌI kết cục hội tụ (§5).
    Quên = role khoá vĩnh viễn (dispatch sau luôn trả existing của task đã chết)."""
    _running_tasks.pop((conv_id, role), None)


# ── Slot/queue helpers (room.py gọi trong room_lock) ────────────────────────
def is_busy(conv_id: str) -> bool:
    return conv_id in _busy_rooms


def mark_busy(conv_id: str) -> None:
    _busy_rooms.add(conv_id)


def clear_busy(conv_id: str) -> None:
    """Nhả slot HẲN (release gọi). KHÔNG re-acquire hộ — ghost-slot."""
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


# ── Test/boot reset (tester dùng reset_room; boot dùng reset_all) ───────────
def reset_room(conv_id: str) -> None:
    """Dọn sạch state 1 phòng (test isolation)."""
    _busy_rooms.discard(conv_id)
    _event_queues.pop(conv_id, None)
    _sub_semaphores.pop(conv_id, None)
    main_clients.pop(conv_id, None)
    for key in [k for k in _running_tasks if k[0] == conv_id]:
        _running_tasks.pop(key, None)


def reset_all() -> None:
    """Dọn toàn bộ state in-process (boot / test teardown)."""
    _busy_rooms.clear()
    _event_queues.clear()
    _running_tasks.clear()
    sub_tasks.clear()
    _sub_semaphores.clear()
    main_clients.clear()
