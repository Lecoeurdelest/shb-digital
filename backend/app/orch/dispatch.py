"""orch_dispatch (tool điều phối, mount vào MAIN) + create_task_guarded (idempotent core).

Fire-and-forget (multi-agent §3): trả NGAY {role, status:running} — sub chạy nền, main FREE.
Idempotent (multi-agent §4): khoá (conv_id, role) trong dispatch_lock. task_id KHÔNG lên mặt
tool (role là khoá — spec §4.1; model chép id = hallucinate).

Vòng đời registry idempotency: register TRONG dispatch_lock (dưới) → unregister TRONG _report
(sub_runner §5, nơi MỌI kết cục hội tụ). KHÔNG unregister ở đây — sub sống lâu hơn dispatch.
"""

from __future__ import annotations

import json
from typing import Any

from app.orch import registry, store
from app.orch.store import Task


async def create_task_guarded(conv_id: str, role: str, title: str, brief: str) -> tuple[Task | None, Task | None]:
    """Bản DUY NHẤT của check+create (multi-agent §4). orch_dispatch gọi thẳng.

    Trả (task, None) khi tạo mới · (None, existing) khi role ĐANG chạy trong phòng.
    Check registry sống + tạo DB + đăng ký registry trong CÙNG dispatch_lock — 2 lệnh lách
    khe await không thể cùng tạo task (race test tester ca-a).
    """
    async with registry.dispatch_lock:
        existing_id = registry.get_running_task_id(conv_id, role)
        if existing_id is not None:
            existing = await store.get_task(existing_id)
            # existing có thể None nếu DB dọn cờ (hiếm) — vẫn trả tuple (None, existing)
            return None, existing
        task = await store.create_task(conv_id, role, title, brief)
        registry.register_running(conv_id, role, task.id)
        return task, None


async def orch_dispatch_impl(conv_id: str, role: str, title: str, brief: str) -> dict[str, Any]:
    """Logic dispatch (không phải @tool wrapper — main_session mount thành tool).

    Trả dict cho model: TÊN (role) không ID. Trùng → created:false + hint (KHÔNG lỗi — main
    retry sẽ vòng lặp nếu trả error). Spawn _run_sub nền qua sub_runner (import lazy tránh vòng).
    """
    from app.orch import sub_runner

    known_roles = sub_runner.discovered_roles()
    if role not in known_roles:
        return {
            "code": "bad_role",
            "message": f"role '{role}' không tồn tại",
            "hint": f"role hợp lệ: {sorted(known_roles)}. Đổi rồi gọi lại.",
            "retryable": False,
        }

    task, existing = await create_task_guarded(conv_id, role, title, brief)
    if task is None:
        return {
            "created": False,
            "role": role,
            "status": "running",
            "title": existing.title if existing else title,
            "hint": "Sub role này ĐANG chạy — xem orch_status, KHÔNG giao lại.",
        }

    await _emit_task_created(task)  # SSE task.created (streaming-sse §5) — sau ghi DB
    sub_runner.spawn_sub(task)  # FIRE-AND-FORGET: đăng ký sub_tasks + spawn _run_sub nền
    return {
        "created": True,
        "role": role,
        "status": "running",
        "hint": "Sub chạy nền, xong sẽ có sự kiện báo lại. KHÔNG chờ — giao việc khác hoặc kết thúc lượt.",
    }


async def _emit_task_created(task: Any) -> None:
    """SSE task.created (nguyên row). Lazy import; lỗi SSE KHÔNG fail dispatch (fire-and-forget)."""
    try:
        from app.orch.store import task_to_dict
        from app.sse.emit import emit_task

        emit_task(task.conv_id, "task.created", task_to_dict(task))
    except Exception as e:  # noqa: BLE001
        import logging

        logging.getLogger("orch").warning("emit task.created lỗi (bỏ qua): %s", e)


def to_mcp_text(payload: dict[str, Any]) -> dict[str, Any]:
    """Bọc dict → MCP content envelope (dùng khi mount orch_dispatch thành @tool)."""
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}
