from __future__ import annotations

import json
import logging
from typing import Any

from app.orch.store import Task

log = logging.getLogger("orch.session")


async def _audit_tool_call(task: Task, tool: str, tool_input: Any, output: Any) -> None:

    from app.orch import store_audit

    try:
        row = await store_audit.record_tool_call(
            task_id=task.id, conv_id=task.conv_id, actor=task.role, tool=tool, tool_input=tool_input, output=output
        )
        if row is not None:
            _emit_toolcall(task.conv_id, row)
    except Exception as e:  # noqa: BLE001
        log.warning("failed to audit tool_call (ignored): %s", e)


async def _audit_main_tool_call(conv_id: str, tool: str, tool_input: Any, output: Any) -> None:

    from app.orch import store_audit

    try:
        row = await store_audit.record_tool_call(
            task_id=None, conv_id=conv_id, actor="main", tool=tool, tool_input=tool_input, output=output
        )
        if row is not None:
            _emit_toolcall(conv_id, row)
    except Exception as e:  # noqa: BLE001
        log.warning("failed to audit main tool_call (ignored): %s", e)


def _emit_toolcall(conv_id: str, row: dict[str, Any]) -> None:

    try:
        from app.sse.emit import emit

        summary = json.dumps(row.get("input"), ensure_ascii=False)[:200] if row.get("input") is not None else ""
        emit(
            conv_id,
            "toolcall",
            {
                "id": row.get("id"),
                "task_id": row.get("task_id"),
                "tool": row["tool"],
                "summary": summary,
                "cost": row.get("cost"),
            },
        )
    except Exception as e:  # noqa: BLE001
        log.warning("failed to emit toolcall (ignored): %s", e)


def _emit_thinking(conv_id: str, task_id: str | None, text: str) -> None:

    if not text:
        return
    try:
        from app.sse.emit import emit

        emit(conv_id, "thinking", {"task_id": str(task_id) if task_id else None, "text": text})
    except Exception as e:  # noqa: BLE001
        log.warning("failed to emit thinking event (ignored): %s", e)
