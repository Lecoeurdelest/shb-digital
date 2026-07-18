"""Audit router (T4-1) — GET /api/audit tool_calls search (admin, SPEC §11).

Success = list resource trần (tool_call rows). Filter: task_id? conv_id? tool? actor? (whitelist ở
store_audit). Append-only — CHỈ đọc (không POST/PUT/DELETE audit qua API — bất biến §10).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.auth.deps import require_user
from app.errors import ApiError
from app.orch import store_audit

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
async def list_audit(
    task_id: str | None = Query(None),
    conv_id: str | None = Query(None),
    tool: str | None = Query(None),
    actor: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    claims: dict = Depends(require_user),
) -> list[dict[str, Any]]:
    """tool_calls theo filter (user — D-54). Mới nhất trước. Ít nhất 1 filter khuyến nghị nhưng không bắt
    (audit toàn cục cũng hợp lệ cho Control Tower). limit cap 1000."""
    filters = {"task_id": task_id, "conv_id": conv_id, "tool": tool, "actor": actor}
    # bỏ None → chỉ filter cột được truyền
    active = {k: v for k, v in filters.items() if v}
    try:
        return await store_audit.query_tool_calls(active, limit=limit)
    except Exception as e:  # noqa: BLE001 — id sai format uuid (task_id) → 400 giọng-agent
        raise ApiError(
            400,
            "bad_filter",
            f"Filter audit lỗi: {str(e)[:100]}",
            "Kiểm task_id/conv_id đúng định dạng.",
            retryable=False,
        ) from e
