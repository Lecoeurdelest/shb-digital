"""SSE emit + audit persist helpers cho MAIN/SUB turn (S8 — tách khỏi main_session.py <400 LOC).
toolcall/thinking SSE (§9) + tool_call audit persist (T4-1). Best-effort — lỗi KHÔNG fail turn."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.orch.store import Task

log = logging.getLogger("orch.session")


async def _audit_tool_call(task: Task, tool: str, tool_input: Any, output: Any) -> None:
    """T4-1: persist 1 tool_call (append-only) + emit SSE toolcall. Best-effort — audit lỗi KHÔNG
    fail sub turn (§12). actor = role sub. task_id/conv_id từ task."""
    from app.orch import store_audit

    try:
        row = await store_audit.record_tool_call(
            task_id=task.id, conv_id=task.conv_id, actor=task.role, tool=tool, tool_input=tool_input, output=output
        )
        if row is not None:
            _emit_toolcall(task.conv_id, row)
    except Exception as e:  # noqa: BLE001 — best-effort, không fail turn
        log.warning("audit tool_call lỗi (bỏ qua): %s", e)


async def _audit_main_tool_call(conv_id: str, tool: str, tool_input: Any, output: Any) -> None:
    """T4-1: persist tool_call của MAIN (actor='main', task_id=None — main gọi tool ngoài sub).
    Best-effort (§12)."""
    from app.orch import store_audit

    try:
        row = await store_audit.record_tool_call(
            task_id=None, conv_id=conv_id, actor="main", tool=tool, tool_input=tool_input, output=output
        )
        if row is not None:
            _emit_toolcall(conv_id, row)
    except Exception as e:  # noqa: BLE001
        log.warning("audit main tool_call lỗi (bỏ qua): %s", e)


def _emit_toolcall(conv_id: str, row: dict[str, Any]) -> None:
    """SSE toolcall §9 {task_id, tool, summary, cost} + `id` (FE upsert live tránh trùng reload+SSE
    chồng — FE yêu cầu; audit row có id nên đưa vào event, mở rộng tương thích SPEC §9). Lazy import;
    lỗi SSE KHÔNG fail (fire-and-forget)."""
    try:
        from app.sse.emit import emit

        summary = json.dumps(row.get("input"), ensure_ascii=False)[:200] if row.get("input") is not None else ""
        emit(
            conv_id,
            "toolcall",
            {
                "id": row.get("id"),  # = tool_calls.id (khớp GET /api/audit row.id) → FE dedup upsert
                "task_id": row.get("task_id"),
                "tool": row["tool"],
                "summary": summary,
                "cost": row.get("cost"),
            },
        )
    except Exception as e:  # noqa: BLE001
        log.warning("emit toolcall lỗi (bỏ qua): %s", e)


def _emit_thinking(conv_id: str, task_id: str | None, text: str) -> None:
    """T4-2 F1 trace: SSE thinking {task_id, text} — suy nghĩ model (ThinkingBlock). task_id=sub role
    · None=main. LIVE-only (KHÔNG persist DB — trace tạm, SPEC không đòi bảng thinking). Fire-and-forget
    (lỗi SSE KHÔNG fail turn). text rỗng → bỏ qua (không emit khối rỗng)."""
    if not text:
        return
    try:
        from app.sse.emit import emit

        emit(conv_id, "thinking", {"task_id": str(task_id) if task_id else None, "text": text})
    except Exception as e:  # noqa: BLE001
        log.warning("emit thinking lỗi (bỏ qua): %s", e)
