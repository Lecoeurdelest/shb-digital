from __future__ import annotations

import json
from datetime import UTC
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from app.orch import dispatch, registry, store, sub_runner

ORCH_ALLOWED = ["mcp__orch__orch_dispatch", "mcp__orch__orch_status"]


def _text(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def build_orch_server(conv_id: str) -> Any:

    @tool(
        name="orch_dispatch",
        description="Assign work to one digital specialist by role. Return {role, status} immediately while the "
        "specialist runs in the background; do not wait. Assign other work or end the turn. If that role is already "
        "running, report its status without creating another task. Use orch_status, not this tool, for team status.",
        input_schema={
            "type": "object",
            "properties": {
                "role": {"type": "string", "enum": sorted(sub_runner.discovered_roles())},
                "title": {"type": "string", "description": "task name shown on the task board"},
                "input": {"type": "string", "description": "context and request for the specialist"},
            },
            "required": ["role", "title", "input"],
        },
    )
    async def orch_dispatch(args: dict[str, Any]) -> dict[str, Any]:
        result = await dispatch.orch_dispatch_impl(conv_id, args["role"], args["title"], args["input"])
        return _text(result)

    @tool(
        name="orch_status",
        description="Task board and LIVE status of specialists in the room. Use it to see what the team is doing, "
        "for example when the user interrupts to request a status update.",
        input_schema={"type": "object", "properties": {}},
    )
    async def orch_status(args: dict[str, Any]) -> dict[str, Any]:
        board = await store.task_board(conv_id)

        live_roles = {role for (c, role) in _running_keys() if c == conv_id}
        for item in board:
            if item["status"] == "running" and item["role"] not in live_roles:
                item["status"] = "failed"
        return _text(
            {
                "tasks": board,
                "count": len(board),
                "asOf": _now(),
            }
        )

    return create_sdk_mcp_server(name="orch", version="1.0.0", tools=[orch_dispatch, orch_status])


def _running_keys() -> list[tuple[str, str]]:

    return list(registry._running_tasks.keys())  # noqa: SLF001


def _now() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat(timespec="seconds")
