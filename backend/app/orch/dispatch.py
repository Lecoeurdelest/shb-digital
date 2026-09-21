from __future__ import annotations

import json
from typing import Any

from app.orch import registry, store
from app.orch.store import Task


async def create_task_guarded(conv_id: str, role: str, title: str, brief: str) -> tuple[Task | None, Task | None]:

    async with registry.dispatch_lock:
        existing_id = registry.get_running_task_id(conv_id, role)
        if existing_id is not None:
            existing = await store.get_task(existing_id)

            return None, existing
        task = await store.create_task(conv_id, role, title, brief)
        registry.register_running(conv_id, role, task.id)
        return task, None


async def orch_dispatch_impl(conv_id: str, role: str, title: str, brief: str) -> dict[str, Any]:

    from app.orch import sub_runner

    known_roles = sub_runner.discovered_roles()
    if role not in known_roles:
        return {
            "code": "bad_role",
            "message": f"role '{role}' does not exist",
            "hint": f"Valid roles: {sorted(known_roles)}. Correct the role and call again.",
            "retryable": False,
        }

    task, existing = await create_task_guarded(conv_id, role, title, brief)
    if task is None:
        return {
            "created": False,
            "role": role,
            "status": "running",
            "title": existing.title if existing else title,
            "hint": "This sub-role is already running; check orch_status and do not dispatch it again.",
        }

    await _emit_task_created(task)  # Emit SSE task.created after the database write (streaming-sse §5).
    sub_runner.spawn_sub(task)
    return {
        "created": True,
        "role": role,
        "status": "running",
        "hint": (
            "The sub-task runs in the background and emits an event when complete. Do not wait; assign other work "
            "or end the turn."
        ),
    }


async def _emit_task_created(task: Any) -> None:

    try:
        from app.orch.store import task_to_dict
        from app.sse.emit import emit_task

        emit_task(task.conv_id, "task.created", task_to_dict(task))
    except Exception as e:  # noqa: BLE001
        import logging

        logging.getLogger("orch").warning("failed to emit task.created (ignored): %s", e)


def to_mcp_text(payload: dict[str, Any]) -> dict[str, Any]:

    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}
