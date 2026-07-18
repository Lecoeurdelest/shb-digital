"""Compare single vs multi-agent (T4-4, deliverable #5) — POST /api/compare TỐI GIẢN.

Điểm demo: MULTI có NGUỒN (tool_calls + cards + trace), SINGLE nhẩm chay (1 query thuần không tool).
Chạy SONG SONG asyncio.gather 2 nhánh độc lập. Sync HTTP dài (~60-90s) chấp nhận (async không block
loop 1-worker; demo bấm 1 lần chờ). Partial khi multi timeout/lỗi → single vẫn trả (KHÔNG 500).

KHÔNG đụng main_session/orch internals — dùng SEAM CÔNG KHAI: store.create_conversation +
room.handle_room_event (luồng multi thật) + store_audit.query_tool_calls (đếm) + 1 SDK query riêng
cho single (ClaudeAgentOptions no-mcp, max_turns=1).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.deps import require_admin
from app.errors import ApiError
from app.orch import room, store, store_audit

log = logging.getLogger("api.compare")

router = APIRouter(prefix="/api/compare", tags=["compare"])

_MULTI_TIMEOUT_S = 120.0
_POLL_INTERVAL_S = 2.0
# "settled" = dừng HẲN, không phải idle-lượt-đầu (dispatch). idle ĐẦU (main giao việc, sub CHƯA chạy)
# KHÔNG phải xong — phải chờ sub done → main tổng hợp → idle LẦN 2. Điều kiện settled:
#   waiting_approval/failed (dừng hẳn) · HOẶC idle+done VÀ KHÔNG task nào queued/running (sub xong hết).
_STOP_STATES = {"waiting_approval", "failed"}  # dừng hẳn, không chờ thêm
_ACTIVE_TASK = {"queued", "running"}  # còn task đang chạy → CHƯA xong (dù conv idle giữa lượt)

_SINGLE_SKILL = (
    "Bạn là trợ lý ngân hàng. Trả lời thẳng câu hỏi bằng KIẾN THỨC CỦA BẠN, ngắn gọn. "
    "Bạn KHÔNG có công cụ tra cứu dữ liệu khách hàng — trả lời dựa trên hiểu biết chung."
)


class CompareBody(BaseModel):
    question: str


async def _run_single(question: str) -> dict[str, Any]:
    """1 SDK query THUẦN — KHÔNG mcp/tool, max_turns=1. Đo duration + cost. Lỗi → text lỗi + note."""
    from claude_agent_sdk import AssistantMessage, ClaudeSDKClient, ResultMessage, TextBlock

    from app.orch.main_session import MAIN_MODEL, conversation_cwd
    from app.orch.providers import server_provider_env

    try:
        from claude_agent_sdk import ClaudeAgentOptions

        opts = ClaudeAgentOptions(
            system_prompt=_SINGLE_SKILL,
            model=MAIN_MODEL,
            mcp_servers={},  # KHÔNG tool — single nhẩm chay
            tools=[],
            allowed_tools=[],
            permission_mode="dontAsk",
            setting_sources=[],
            max_turns=1,
            cwd=str(conversation_cwd("compare-single")),
            env=server_provider_env() or {},
        )
        t0 = time.monotonic()
        client = ClaudeSDKClient(options=opts)
        text_parts: list[str] = []
        cost: Any = None
        try:
            await client.connect()
            await client.query(question)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            text_parts.append(block.text)
                elif isinstance(msg, ResultMessage):
                    cost = getattr(msg, "total_cost_usd", None) or getattr(msg, "cost", None)
        finally:
            try:
                await client.disconnect()
            except Exception as e:  # noqa: BLE001
                log.warning("single disconnect lỗi: %s", e)
        return {"text": "".join(text_parts), "duration_s": round(time.monotonic() - t0, 2), "cost": cost}
    except Exception as e:  # noqa: BLE001 — single lỗi KHÔNG làm hỏng cả compare (multi vẫn có)
        log.warning("compare single lỗi: %s", e)
        return {"text": f"[single lỗi: {str(e)[:120]}]", "duration_s": None, "cost": None, "error": True}


async def _run_multi(question: str) -> dict[str, Any]:
    """Conv THẬT + handle_room_event (luồng multi) → poll idle → text + đếm tool_calls + cards.

    Timeout → partial {timeout:true, conv_id}. Câu giải ngân → waiting_approval = trả trạng thái đó.
    """
    conv = await store.create_conversation("compare", "compare-run")
    conv_id = conv["id"]
    t0 = time.monotonic()
    await store.add_message(conv_id, "user", question)
    # spawn lượt phòng (multi flow thật) — KHÔNG await (poll status thay)
    asyncio.ensure_future(room.handle_room_event(conv_id, "user_message", {"content": question}))

    elapsed = 0.0
    status = "running"
    settled = False
    while elapsed < _MULTI_TIMEOUT_S:
        await asyncio.sleep(_POLL_INTERVAL_S)
        elapsed += _POLL_INTERVAL_S
        c = await store.get_conversation(conv_id)
        status = c["status"] if c else "unknown"
        if status in _STOP_STATES:
            settled = True  # waiting_approval (giải ngân) / failed — dừng hẳn, không chờ thêm
            break
        if status in ("idle", "done"):
            # idle có thể là lượt-đầu (dispatch, sub CHƯA chạy) HOẶC lượt-cuối (tổng hợp xong).
            # Phân biệt: còn task queued/running → CHƯA xong (chờ tiếp). Không còn → settled.
            board = await store.task_board(conv_id)
            if board and not any(t.get("status") in _ACTIVE_TASK for t in board):
                settled = True  # sub xong hết + main idle → tổng hợp xong
                break
    duration = round(time.monotonic() - t0, 2)

    tool_calls = await store_audit.query_tool_calls({"conv_id": conv_id}, limit=1000)
    cards = await store.list_cards(conv_id)
    if not settled:
        # timeout — partial (single vẫn trả). conv_id để FE xem ca dở.
        return {
            "timeout": True,
            "conv_id": conv_id,
            "status": status,
            "duration_s": duration,
            "tool_calls": len(tool_calls),
            "cards": len(cards),
        }

    messages = await store.list_messages(conv_id)
    assistant = [m for m in messages if m.get("sender") == "assistant"]
    text = assistant[-1]["content"] if assistant else ""
    return {
        "text": text,
        "duration_s": duration,
        "status": status,  # idle | waiting_approval (giải ngân) | failed
        "tool_calls": len(tool_calls),
        "cards": len(cards),
        "conv_id": conv_id,
    }


@router.post("")
async def compare(body: CompareBody, claims: dict = Depends(require_admin)) -> dict[str, Any]:
    """So sánh single (nhẩm chay) vs multi (có nguồn). 2 nhánh SONG SONG. Partial khi multi lỗi/timeout."""
    question = (body.question or "").strip()
    if not question:
        raise ApiError(400, "empty_question", "Câu hỏi trống.", "Nhập câu hỏi để so sánh.", retryable=False)

    # gather 2 nhánh — return_exceptions: 1 nhánh nổ KHÔNG kéo cả request (partial).
    single_r, multi_r = await asyncio.gather(_run_single(question), _run_multi(question), return_exceptions=True)
    single = single_r if not isinstance(single_r, Exception) else {"text": f"[single lỗi: {single_r}]", "error": True}
    multi = multi_r if not isinstance(multi_r, Exception) else {"timeout": True, "error": f"{multi_r}"[:120]}
    return {"question": question, "single": single, "multi": multi}
