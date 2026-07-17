"""SDK lifecycle: MAIN (bền/phòng, resume disk) + SUB (tươi/task). claude-sdk §1-§3 + session.py.

LANDMINE (session.py đã trả giá THẬT):
1. connect/disconnect CÙNG asyncio task (anyio cancel-scope) — disconnect cross-task = TREO IM
   LẶNG. close-on-done: 1 lượt = 1 coroutine trọn gói, disconnect trong finally CỦA CHÍNH task đó.
2. cwd ổn định per-conversation (data/conversations/<id>/) — cwd trôi → resume im lặng mở phiên
   mới, main mất trí nhớ (bẫy #555).
3. bắt session_id ở MỌI kết cục (kể cả is_error). Lệch id → resume_failed, GIỮ id gốc.
4. resume chết (ProcessError) → fresh 1 lần, KHÔNG tính trần retry.

D-16: main=sonnet, sub=haiku (từ providers.yaml — T1-2 dùng model string trực tiếp; providers
routing full ở sprint sau). setting_sources=[] harness sạch, tools=[] chỉ mở qua allowed_tools,
permission_mode='dontAsk' (headless). D-29: SDK live = bonus, mechanics gate không phụ thuộc.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.mount.mount_role import ROLES_DIR, mount_role
from app.orch import registry, store
from app.orch.store import Task

log = logging.getLogger("orch.session")

# cwd gốc per-conversation — neo transcript resume (landmine #2)
CONV_ROOT = Path(__file__).resolve().parents[2] / "data" / "conversations"

MAIN_MODEL = "sonnet"
SUB_MODEL = "haiku"
MAIN_MAX_TURNS = 40
SUB_MAX_TURNS = 20

# Skill điều phối MAIN = vỏ TỰ VIẾT (mỏng — KHÔNG skill nghiệp vụ, N1).
MAIN_SKILL = """Bạn là ĐIỀU PHỐI VIÊN của một chi nhánh ngân hàng số SHB.

Bạn KHÔNG tự thẩm định. Bạn giao việc cho chuyên gia số qua tool orch_dispatch(role, title, input):
- role hợp lệ hiện có: "credit" (thẩm định tín dụng: DSCR, LTV, CIC, trần vay).
- Giao xong, tool trả NGAY {status:running} — bạn KHÔNG chờ trong lượt; kết thúc lượt hoặc giao
  việc khác. Khi chuyên gia xong, hệ thống báo lại bạn bằng một sự kiện kèm kết quả + bảng việc.
- Muốn biết đội đang làm gì: gọi orch_status().

LUẬT:
- Mọi con số phải CÓ NGUỒN từ tool chuyên gia — KHÔNG tự nhẩm DSCR/LTV/khả năng trả.
- Khi có kết quả từ chuyên gia: tổng hợp lại cho người dùng bằng tiếng Việt, trích số + nguồn.
- Cần tính toán phụ trợ: dùng tool calc, không nhẩm tay.
- Thiếu thông tin (ai, số tiền) → hỏi người dùng 1 câu ngắn.
"""


def conversation_cwd(conv_id: str) -> Path:
    """Thư mục ổn định per-conversation (resume neo transcript ở đây). Tạo nếu chưa có."""
    # conv_id có thể chứa ký tự lạ (text tự do D-31) → sanitize thành tên thư mục an toàn
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in conv_id)
    d = CONV_ROOT / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def _build_sub_options(task: Task) -> Any:
    """Options SUB: SKILL role + toolpack role (mount_role) + common. model=haiku. KHÔNG resume."""
    from claude_agent_sdk import ClaudeAgentOptions

    skill, server, allowed = mount_role(task.role)
    from app.orch.common_tools import COMMON_ALLOWED, COMMON_SERVER

    return ClaudeAgentOptions(
        system_prompt=skill,
        model=SUB_MODEL,
        mcp_servers={f"banking_{task.role}": server, "common": COMMON_SERVER},
        tools=[],
        allowed_tools=allowed + COMMON_ALLOWED,
        permission_mode="dontAsk",
        setting_sources=[],
        max_turns=SUB_MAX_TURNS,
        cwd=str(conversation_cwd(task.conv_id)),
    )


async def run_sub_turn(task: Task) -> dict[str, Any]:
    """SDK runner THẬT cho _run_sub (seam). Chạy sub tươi tới ResultMessage, trả kết quả text +
    tool-calls. close-on-done: disconnect trong finally CÙNG task. KHÔNG resume (sub disposable).
    """
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeSDKClient,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
    )

    brief = task.input or task.title
    client = ClaudeSDKClient(options=_build_sub_options(task))
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    try:
        await client.connect()
        await client.query(brief)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        tool_calls.append({"tool": block.name.split("__")[-1], "input": block.input})
            elif isinstance(msg, ResultMessage):
                pass  # sub không resume → không cần giữ session_id
    finally:
        try:
            await client.disconnect()
        except Exception as e:  # noqa: BLE001
            log.warning("sub disconnect lỗi: %s", e)
    return {"text": "".join(text_parts), "tool_calls": tool_calls}


def _build_main_options(conv_id: str, resume: str | None) -> Any:
    """Options MAIN: skill điều phối + orch_* + common. model=sonnet. resume phiên bền."""
    from claude_agent_sdk import ClaudeAgentOptions

    from app.orch.common_tools import COMMON_ALLOWED, COMMON_SERVER
    from app.orch.orch_tools import ORCH_ALLOWED, build_orch_server

    return ClaudeAgentOptions(
        system_prompt=MAIN_SKILL,
        model=MAIN_MODEL,
        mcp_servers={"orch": build_orch_server(conv_id), "common": COMMON_SERVER},
        tools=[],
        allowed_tools=ORCH_ALLOWED + COMMON_ALLOWED,
        permission_mode="dontAsk",
        setting_sources=[],
        max_turns=MAIN_MAX_TURNS,
        cwd=str(conversation_cwd(conv_id)),
        resume=resume,
    )


async def run_main_turn(conv_id: str, prompt: str, on_text: Any = None) -> dict[str, Any]:
    """Chạy 1 lượt MAIN (close-on-done + resume). connect+disconnect CÙNG task này (landmine #1).

    resume = sdk_session_id lưu DB; bắt session_id mới ở ResultMessage (mọi kết cục). on_text =
    callback stream chunk (T1-3 nối SSE). Trả {text, session_id, is_error}.
    """
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeSDKClient,
        ProcessError,
        ResultMessage,
        TextBlock,
    )

    # ContextVar set dòng ĐẦU (brief §E · lab-joint §7): actor='main'. QUAN TRỌNG cho re-entrant
    # path (sub done → _report → _event_sink → handle_room_event → run_main_turn chạy TRONG task
    # của sub): không set lại thì CTX_ACTOR leak = role sub → audit mis-attribute lượt main (T1-3).
    registry.CTX_CONV.set(conv_id)
    registry.CTX_ACTOR.set("main")

    expected = await store.get_conv_session_id(conv_id)
    try:
        client = ClaudeSDKClient(options=_build_main_options(conv_id, resume=expected))
        await client.connect()
    except ProcessError:
        if not expected:
            raise
        log.warning("resume %s chết → fresh (conv %s)", expected, conv_id)
        await store.set_conv_session_id(conv_id, None)
        client = ClaudeSDKClient(options=_build_main_options(conv_id, resume=None))
        await client.connect()

    registry.main_clients[conv_id] = client  # cho interrupt (§7) — pop trong finally
    text_parts: list[str] = []
    session_id: str | None = None
    is_error = False
    try:
        await client.query(prompt)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                        if on_text is not None:
                            await on_text(block.text)
            elif isinstance(msg, ResultMessage):
                session_id = getattr(msg, "session_id", None)
                is_error = bool(getattr(msg, "is_error", False))
    finally:
        registry.main_clients.pop(conv_id, None)
        try:
            await client.disconnect()  # close-on-done — CÙNG task (landmine #1)
        except Exception as e:  # noqa: BLE001
            log.warning("main disconnect lỗi: %s", e)

    if session_id and session_id != expected:
        # bắt id mới (kể cả lượt đầu expected=None). Lệch khi expected có → resume nghi hỏng,
        # nhưng vẫn lưu id mới để lượt sau resume (session.py giữ id gốc; ở đây S1 đơn giản: lưu mới)
        await store.set_conv_session_id(conv_id, session_id)
    return {"text": "".join(text_parts), "session_id": session_id, "is_error": is_error}


async def _turn_runner(conv_id: str, event: str, data: dict) -> None:
    """Nối handle_room_event → run_main_turn. Dựng prompt theo loại event (vỏ đưa dữ kiện, não
    quyết — N1: KHÔNG lệnh 'đợi đủ N con')."""
    prompt = _build_event_prompt(event, data)
    await run_main_turn(conv_id, prompt)


def _build_event_prompt(event: str, data: dict) -> str:
    if event == "user_message":
        return f"Tin nhắn người dùng: {data['content']}"
    if event == "task_done":
        return (
            f"Sự kiện: chuyên gia {data['role']} kết thúc [{data['outcome']}]. "
            f"Kết quả: {data['result_summary']}\nBảng việc hiện tại: {json.dumps(data['board'], ensure_ascii=False)}"
        )
    return json.dumps(data, ensure_ascii=False)


def boot() -> None:
    """Gọi lúc app startup: gán runner SDK thật cho seam + nối event sink. Tách khỏi test
    (test mechanics KHÔNG gọi boot → không đụng SDK)."""
    from app.orch import room, sub_runner

    sub_runner.set_default_runner(run_sub_turn)
    room.set_turn_runner(_turn_runner)
    room.wire_event_sink()


def roles_available() -> list[str]:
    if not ROLES_DIR.exists():
        return []
    return [p.name for p in ROLES_DIR.iterdir() if p.is_dir() and (p / "functions.py").exists()]
