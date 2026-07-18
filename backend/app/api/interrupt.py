"""Interrupt router (T4-3 F2a) — POST /api/conversations/{conv_id}/interrupt (SPEC §11 §4.3).

Huỷ 1 SUB đang chạy: cancel asyncio.Task trong registry.sub_tasks → CancelledError → _run_sub nhánh
cancel → _report invariant (S1) tự lo event task_done + unregister + SSE. Router CHỈ validate +
cancel + 200 NGAY (fire-and-forget — KHÔNG chờ cancel xong, KHÔNG đụng _report §5).

target:"main" (huỷ main) NGOÀI scope T4-3 (ghi deviation — SPEC §11 body target mở rộng sau).
Chỉ huỷ TASK sub. "hủy từng con" §4.3: cancel đúng task.id → sub khác KHÔNG đụng.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.deps import require_user
from app.errors import ApiError
from app.orch import registry, store

router = APIRouter(prefix="/api/conversations", tags=["interrupt"])


class InterruptBody(BaseModel):
    target: str  # task_id (sub). "main" ngoài scope T4-3.


@router.post("/{conv_id}/interrupt")
async def interrupt(conv_id: str, body: InterruptBody, claims: dict = Depends(require_user)) -> dict[str, Any]:
    """Huỷ 1 sub đang chạy. target = task_id. 200 {cancelled:true} NGAY (fire).

    404 task không tồn tại / không thuộc conv · 409 đã xong hoặc không còn chạy (double-cancel).
    """
    target = body.target
    if target == "main":
        # target:"main" NGOÀI scope T4-3 (deviation ghi ở docstring + DECISIONS). Chỉ huỷ task sub.
        raise ApiError(
            400,
            "target_not_supported",
            "Huỷ 'main' chưa hỗ trợ ở T4-3 — chỉ huỷ task sub.",
            "Truyền target = task_id của sub cần huỷ.",
            retryable=False,
        )

    task = await store.get_task(target)
    if task is None or task.conv_id != conv_id:
        # không tồn tại HOẶC không thuộc conv này (không cho huỷ task ca khác) → 404
        raise ApiError(
            404, "task_not_found", f"Không có task '{target}' trong ca này.", "Kiểm lại task_id.", retryable=False
        )
    if task.status not in ("queued", "running"):
        # đã done/failed/timeout → không còn gì để huỷ
        raise ApiError(
            409,
            "task_not_running",
            f"Task '{target}' đã kết thúc ({task.status}) — không huỷ được.",
            "Task đã xong; tải lại trạng thái.",
            retryable=False,
        )

    t = registry.sub_tasks.get(target)
    if t is None or t.done():
        # DB nói running nhưng registry không còn (đã _report xong / double-cancel) → 409
        raise ApiError(
            409,
            "task_not_running",
            f"Task '{target}' không còn chạy trong registry (có thể vừa xong).",
            "Tải lại trạng thái.",
            retryable=False,
        )

    # CANCEL — fire: CancelledError → _run_sub nhánh cancel → _report (event/unregister/SSE) tự lo (S1).
    # KHÔNG await cancel xong (fire-and-forget §4.3). Chỉ task.id NÀY bị cancel → sub khác không đụng.
    t.cancel()
    return {"cancelled": True, "target": target, "role": task.role}
