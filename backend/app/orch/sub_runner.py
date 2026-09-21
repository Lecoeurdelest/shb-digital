from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.orch import registry, store
from app.orch.store import Task

SubRunner = Callable[[Task], Awaitable[dict[str, Any]]]

IDLE_TIMEOUT_S = 120


class IdleTimeout(Exception):
    pass


_event_sink: Callable[[str, str, dict], Awaitable[None]] | None = None


def set_event_sink(sink: Callable[[str, str, dict], Awaitable[None]]) -> None:

    global _event_sink
    _event_sink = sink


_default_runner: SubRunner | None = None


def set_default_runner(runner: SubRunner) -> None:
    global _default_runner
    _default_runner = runner


def discovered_roles() -> set[str]:

    from app.mount.mount_role import ROLES_DIR

    if not ROLES_DIR.exists():
        return set()
    return {
        p.name
        for p in ROLES_DIR.iterdir()
        if p.is_dir() and not p.name.startswith("_") and (p / "functions.py").exists() and (p / "SKILL.md").exists()
    }


async def _report(task: Task, outcome: str, result: dict[str, Any] | None) -> None:

    registry.unregister_running(task.conv_id, task.role)
    registry.sub_tasks.pop(task.id, None)
    try:
        await store.finish_task(task.id, outcome, result)
        await _emit_task_status(task.id, task.conv_id)  # SSE task.status (streaming-sse §5)
        board = await store.task_board(task.conv_id)
        payload = {
            "task_id": task.id,
            "role": task.role,
            "outcome": outcome,  # done | failed | timeout
            "result_summary": _summarize(result),
            "board": board,
        }
        if _event_sink is not None:
            # shielded). ACCEPT S1 (architect verify 5 discriminator: sema-released, disconnect

            await _event_sink(task.conv_id, "task_done", payload)
    except Exception as e:
        import logging

        logging.getLogger("orch").error("_report failed for task %s: %s", task.id, e)


async def _emit_task_status(task_id: str, conv_id: str) -> None:

    try:
        from app.orch.store import task_to_dict
        from app.sse.emit import emit_task

        full = await store.get_task(task_id)
        if full is not None:
            emit_task(conv_id, "task.status", task_to_dict(full))
    except Exception as e:  # noqa: BLE001
        import logging

        logging.getLogger("orch").warning("failed to emit task.status (ignored): %s", e)


def _summarize(result: dict[str, Any] | None, max_chars: int = 3000) -> str:
    if result is None:
        return ""
    import json

    text = json.dumps(result, ensure_ascii=False)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + " …[summarized — details are available on the card or in the database]"


async def _run_sub(task: Task, runner: SubRunner | None = None) -> None:

    run = runner or _default_runner
    outcome: str = "failed"
    result: dict[str, Any] | None = {"reason": "unknown"}
    try:
        async with registry.sub_semaphore(task.conv_id):
            registry.CTX_CONV.set(task.conv_id)
            registry.CTX_ACTOR.set(task.role)
            registry.CTX_TASK.set(task.id)
            await store.mark_running(task.id)
            if run is None:
                raise RuntimeError("no sub runner set (SDK has not booted or the test has not injected one)")
            out = await run(task)
            outcome, result = "done", out
    except IdleTimeout:
        outcome, result = "timeout", {"reason": f"idle {IDLE_TIMEOUT_S}s"}
    except asyncio.CancelledError:
        outcome, result = "failed", {"reason": "cancelled by user"}
        raise
    except Exception as e:  # noqa: BLE001
        outcome, result = "failed", {"reason": str(e)[:500]}
    finally:
        await asyncio.shield(_report(task, outcome, result))


def spawn_sub(task: Task, runner: SubRunner | None = None) -> asyncio.Task:

    t = asyncio.ensure_future(_run_sub(task, runner))
    registry.sub_tasks[task.id] = t
    return t
