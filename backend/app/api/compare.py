from __future__ import annotations

import asyncio
import logging
import time
from contextvars import ContextVar
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.deps import require_admin
from app.errors import ApiError
from app.orch import room, store, store_audit
from app.prompting import get_prompt_service
from app.tenancy import tenant_id_from_claims

log = logging.getLogger("api.compare")

router = APIRouter(prefix="/api/compare", tags=["compare"])

_MULTI_TIMEOUT_S = 120.0
_SINGLE_TIMEOUT_S = 60.0

_POLL_INTERVAL_S = 2.0


_STOP_STATES = {"waiting_approval", "failed"}
_ACTIVE_TASK = {"queued", "running"}
_COMPARE_TENANT: ContextVar[str | None] = ContextVar("compare_tenant", default=None)


class CompareBody(BaseModel):
    question: str


async def _run_single(question: str) -> dict[str, Any]:

    from claude_agent_sdk import AssistantMessage, ClaudeSDKClient, ResultMessage, TextBlock

    from app.orch.main_session import MAIN_MODEL, conversation_cwd
    from app.orch.providers import server_provider_env

    try:
        from claude_agent_sdk import ClaudeAgentOptions

        opts = ClaudeAgentOptions(
            system_prompt=get_prompt_service().render("compare.single.system"),
            model=MAIN_MODEL,
            mcp_servers={},
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
                log.warning("single-agent disconnect failed: %s", e)
        return {"text": "".join(text_parts), "duration_s": round(time.monotonic() - t0, 2), "cost": cost}
    except Exception as e:  # noqa: BLE001
        log.warning("single-agent comparison failed: %s", e)
        return {"text": f"[single-agent error: {str(e)[:120]}]", "duration_s": None, "cost": None, "error": True}


async def _run_multi(question: str) -> dict[str, Any]:

    tenant_id = _COMPARE_TENANT.get()
    create_kwargs = {"tenant_id": tenant_id} if tenant_id is not None else {}
    conv = await store.create_conversation("compare", "compare-run", **create_kwargs)
    conv_id = conv["id"]
    t0 = time.monotonic()
    await store.add_message(conv_id, "user", question)

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
            settled = True
            break
        if status in ("idle", "done"):
            board = await store.task_board(conv_id)
            if board and not any(t.get("status") in _ACTIVE_TASK for t in board):
                settled = True
                break
    duration = round(time.monotonic() - t0, 2)

    tool_calls = await store_audit.query_tool_calls(
        {"conv_id": conv_id},
        limit=1000,
        tenant_id=tenant_id,
    )
    cards = await store.list_cards(conv_id)
    if not settled:
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
        "status": status,
        "tool_calls": len(tool_calls),
        "cards": len(cards),
        "conv_id": conv_id,
    }


@router.post("")
async def compare(body: CompareBody, claims: dict = Depends(require_admin)) -> dict[str, Any]:

    question = (body.question or "").strip()
    if not question:
        raise ApiError(400, "empty_question", "The question is empty.", "Enter a question to compare.", retryable=False)

    single_task = asyncio.wait_for(_run_single(question), timeout=_SINGLE_TIMEOUT_S)
    tenant_token = _COMPARE_TENANT.set(tenant_id_from_claims(claims))
    try:
        single_r, multi_r = await asyncio.gather(
            single_task,
            _run_multi(question),
            return_exceptions=True,
        )
    finally:
        _COMPARE_TENANT.reset(tenant_token)
    if isinstance(single_r, Exception):
        single = {"text": "single-agent did not respond (timeout)", "timeout": True, "duration_s": _SINGLE_TIMEOUT_S}
    else:
        single = single_r
    multi = multi_r if not isinstance(multi_r, Exception) else {"timeout": True, "error": f"{multi_r}"[:120]}
    return {"question": question, "single": single, "multi": multi}
