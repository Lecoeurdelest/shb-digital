from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.deps import require_user
from app.errors import ApiError
from app.orch import registry, store

router = APIRouter(prefix="/api/conversations", tags=["interrupt"])


class InterruptBody(BaseModel):
    target: str


@router.post("/{conv_id}/interrupt")
async def interrupt(conv_id: str, body: InterruptBody, claims: dict = Depends(require_user)) -> dict[str, Any]:

    from app.auth.deps import can_access_conv

    conv = await store.get_conversation(conv_id)
    if conv is None or not can_access_conv(conv, claims):
        raise ApiError(404, "not_found", f"Case '{conv_id}' does not exist.", "Check the case ID.", retryable=False)

    target = body.target
    if target == "main":
        raise ApiError(
            400,
            "target_not_supported",
            "Cancelling 'main' is not supported in T4-3; only sub-tasks can be cancelled.",
            "Set target to the task_id of the sub-task to cancel.",
            retryable=False,
        )

    task = await store.get_task(target)
    if task is None or task.conv_id != conv_id:
        raise ApiError(
            404,
            "task_not_found",
            f"Task '{target}' does not exist in this case.",
            "Check the task_id.",
            retryable=False,
        )
    if task.status not in ("queued", "running"):
        raise ApiError(
            409,
            "task_not_running",
            f"Task '{target}' has already finished ({task.status}) and cannot be cancelled.",
            "The task is complete; reload its status.",
            retryable=False,
        )

    t = registry.sub_tasks.get(target)
    if t is None or t.done():
        raise ApiError(
            409,
            "task_not_running",
            f"Task '{target}' is no longer running in the registry and may have just finished.",
            "Reload the status.",
            retryable=False,
        )

    t.cancel()
    return {"cancelled": True, "target": target, "role": task.role}
