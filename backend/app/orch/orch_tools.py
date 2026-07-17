"""Tool điều phối (server `orch`, CHỈ main mount): orch_dispatch + orch_status. spec §5.

conv_id inject qua closure (build_orch_server per-conversation) — model KHÔNG thấy conv_id/task_id
(spec §15 ID-cho-code). orch_dispatch idempotent (dispatch.py). orch_status honest: đọc registry
sống + DB, kèm asOf.
"""

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
    """MCP server `orch` bound tới 1 conversation (closure inject conv_id — model không thấy)."""

    @tool(
        name="orch_dispatch",
        description="Giao việc cho 1 chuyên gia số theo role. Trả {role, status} NGAY, chuyên gia "
        "chạy nền — KHÔNG chờ; giao tiếp hoặc kết thúc lượt. Trùng role đang chạy → báo đang chạy, "
        "không tạo thứ hai. KHÔNG dùng để hỏi tình hình đội — đó là orch_status.",
        input_schema={
            "type": "object",
            "properties": {
                "role": {"type": "string", "enum": sorted(sub_runner.discovered_roles())},
                "title": {"type": "string", "description": "tên việc, hiện trên bảng việc"},
                "input": {"type": "string", "description": "ngữ cảnh + yêu cầu cho chuyên gia"},
            },
            "required": ["role", "title", "input"],
        },
    )
    async def orch_dispatch(args: dict[str, Any]) -> dict[str, Any]:
        result = await dispatch.orch_dispatch_impl(conv_id, args["role"], args["title"], args["input"])
        return _text(result)

    @tool(
        name="orch_status",
        description="Bảng việc + trạng thái SỐNG các chuyên gia trong phòng. Dùng khi muốn biết đội "
        "đang làm gì (vd người dùng chen lời hỏi tình hình).",
        input_schema={"type": "object", "properties": {}},
    )
    async def orch_status(args: dict[str, Any]) -> dict[str, Any]:
        board = await store.task_board(conv_id)
        # honest: đối chiếu registry sống — role nào registry còn giữ mới thật sự 'running'
        live_roles = {role for (c, role) in _running_keys() if c == conv_id}
        for item in board:
            if item["status"] == "running" and item["role"] not in live_roles:
                item["status"] = "failed"  # cờ DB cũ, registry không có → không báo láo
        return _text(
            {
                "tasks": board,
                "count": len(board),
                "asOf": _now(),
            }
        )

    return create_sdk_mcp_server(name="orch", version="1.0.0", tools=[orch_dispatch, orch_status])


def _running_keys() -> list[tuple[str, str]]:
    # truy cập registry sống (đọc-only) để orch_status honest
    return list(registry._running_tasks.keys())  # noqa: SLF001 — cùng package orch


def _now() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat(timespec="seconds")
