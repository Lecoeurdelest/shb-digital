"""_run_sub + _report — invariant SỐNG CÒN: MỌI kết cục sub → ĐÚNG MỘT event task_done.

multi-agent §5: dồn mọi đường thoát qua 1 điểm hội tụ `_report()` trong finally ngoài cùng.
done / failed / timeout / cancel đều sinh đúng 1 event. Landmine (brief §B):
- `except asyncio.CancelledError` (BaseException — `except Exception` KHÔNG bắt): gán outcome
  rồi RE-RAISE. finally: `asyncio.shield(disconnect)` + `asyncio.shield(_report)` — cancel
  KHÔNG được nuốt event (thiếu shield = 0 event = phòng treo vĩnh viễn).
- IdleTimeout → outcome='timeout', VẪN báo (cám dỗ 'timeout thì thôi' = phòng treo).

SEAM testability (advisor): phần "chạy 1 lượt sub" = callable `runner` inject được → test mock
4 kết cục KHÔNG cần SDK subprocess. Default runner = SDK thật (main_session.run_sub_turn).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.orch import registry, store
from app.orch.store import Task

# Runner seam: async fn(task) -> result_dict. Raise IdleTimeout/Exception/CancelledError để
# biểu diễn kết cục. main_session gán runner SDK thật lúc boot; test inject fake.
SubRunner = Callable[[Task], Awaitable[dict[str, Any]]]

IDLE_TIMEOUT_S = 120


class IdleTimeout(Exception):
    """Sub im quá idle threshold (watchdog vỏ). Kết cục 'timeout' — VẪN báo (§5)."""


# Event sink: room.py gán = handle_room_event bơm vào queue phòng. Test gán fake đếm event.
# Tách khỏi import trực tiếp room (tránh vòng import + cho test thay).
_event_sink: Callable[[str, str, dict], Awaitable[None]] | None = None


def set_event_sink(sink: Callable[[str, str, dict], Awaitable[None]]) -> None:
    """room.py (hoặc test) đăng ký nơi nhận event task_done."""
    global _event_sink
    _event_sink = sink


# Runner mặc định (SDK thật) — main_session gán. None ở test thuần mechanics.
_default_runner: SubRunner | None = None


def set_default_runner(runner: SubRunner) -> None:
    global _default_runner
    _default_runner = runner


def discovered_roles() -> set[str]:
    """Role có thật (quét roles/ — dispatch validate). S1: credit (mount thật)."""
    from app.mount.mount_role import ROLES_DIR

    if not ROLES_DIR.exists():
        return set()
    return {p.name for p in ROLES_DIR.iterdir() if p.is_dir() and (p / "functions.py").exists()}


async def _report(task: Task, outcome: str, result: dict[str, Any] | None) -> None:
    """1 điểm hội tụ MỌI kết cục (§5+§6). Gỡ registry (ĐẦU TIÊN — quên = role khoá vĩnh viễn),
    persist DB TRƯỚC emit, đẩy event task_done kèm bảng việc. Bọc try/except: hỏng cũng không
    chết im (ít nhất log)."""
    registry.unregister_running(task.conv_id, task.role)  # ĐẦU TIÊN — role mở lại cho dispatch sau
    registry.sub_tasks.pop(task.id, None)
    try:
        await store.finish_task(task.id, outcome, result)  # persist TRƯỚC emit (§6)
        await _emit_task_status(task.id, task.conv_id)  # SSE task.status (streaming-sse §5)
        board = await store.task_board(task.conv_id)
        payload = {
            "task_id": task.id,  # NỘI BỘ (DB/log) — KHÔNG lên prompt
            "role": task.role,  # định danh main nhìn thấy
            "outcome": outcome,  # done | failed | timeout
            "result_summary": _summarize(result),
            "board": board,
        }
        if _event_sink is not None:  # đường HÀNG ĐỢI PHÒNG (đánh thức main) — TÁCH khỏi SSE
            await _event_sink(task.conv_id, "task_done", payload)
    except Exception as e:  # đường đỡ cuối — không nuốt im
        import logging

        logging.getLogger("orch").error("_report lỗi task %s: %s", task.id, e)


async def _emit_task_status(task_id: str, conv_id: str) -> None:
    """Bắn SSE task.status (nguyên row). Lazy import (SSE ≠ orchestration; test bus rỗng = no-op).
    Lỗi SSE KHÔNG được fail _report (fire-and-forget — SSE là thông báo)."""
    try:
        from app.orch.store import task_to_dict
        from app.sse.emit import emit_task

        full = await store.get_task(task_id)
        if full is not None:
            emit_task(conv_id, "task.status", task_to_dict(full))
    except Exception as e:  # noqa: BLE001
        import logging

        logging.getLogger("orch").warning("emit task.status lỗi (bỏ qua): %s", e)


def _summarize(result: dict[str, Any] | None, max_chars: int = 3000) -> str:
    if result is None:
        return ""
    import json

    text = json.dumps(result, ensure_ascii=False)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + " …[đã tóm tắt — chi tiết trên card/DB]"


async def _run_sub(task: Task, runner: SubRunner | None = None) -> None:
    """MỌI đường thoát qua _report() trong finally. runner inject được (seam test).

    Semaphore cap per-phòng (§3). mark_running khi THẬT chạy (queued→running). Hủy = cancel
    CHÍNH asyncio task này → CancelledError tại await → nhánh cancel gán outcome + re-raise;
    finally shield disconnect + _report (cancel KHÔNG nuốt event).
    """
    run = runner or _default_runner
    outcome: str = "failed"
    result: dict[str, Any] | None = {"reason": "unknown"}
    try:
        async with registry.sub_semaphore(task.conv_id):
            # ContextVar set dòng ĐẦU (lab-joint §7) — actor = role (không phải 'main')
            registry.CTX_CONV.set(task.conv_id)
            registry.CTX_ACTOR.set(task.role)
            await store.mark_running(task.id)
            if run is None:
                raise RuntimeError("no sub runner set (SDK chưa boot / test chưa inject)")
            out = await run(task)
            outcome, result = "done", out
    except IdleTimeout:
        outcome, result = "timeout", {"reason": f"idle {IDLE_TIMEOUT_S}s"}
    except asyncio.CancelledError:
        # BaseException — `except Exception` KHÔNG bắt. Gán rồi RE-RAISE (finally vẫn chạy).
        outcome, result = "failed", {"reason": "user hủy"}
        raise
    except Exception as e:  # noqa: BLE001 — cửa cuối, sub không được chết im
        outcome, result = "failed", {"reason": str(e)[:500]}
    finally:
        # shield: cancel KHÔNG nuốt được dọn dẹp + event (thiếu = phòng treo — §5)
        await asyncio.shield(_report(task, outcome, result))


def spawn_sub(task: Task, runner: SubRunner | None = None) -> asyncio.Task:
    """Fire-and-forget: đăng ký sub_tasks NGAY (hủy được cả sub còn chờ sema) + spawn nền."""
    t = asyncio.ensure_future(_run_sub(task, runner))
    registry.sub_tasks[task.id] = t
    return t
