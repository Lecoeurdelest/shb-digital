"""Conversations + chat router (CONTRACT §2). Success = resource trần; error = 4-field.

POST /conversations (tạo ca) · GET /conversations (list) · GET /conversations/{id} (full state)
· POST /conversations/{id}/chat (đẩy user_message vào phòng → 202, main stream qua SSE).
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth.deps import require_user
from app.errors import ApiError
from app.orch import room, store

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateConvBody(BaseModel):
    title: str = "Ca mới"
    provider: str | None = None  # D-45b (c) — tên provider (providers.yaml). null = server-default.
    model: str | None = None  # model string ("sonnet"/"glm-4.6"...). null = default.


class ChatBody(BaseModel):
    content: str


@router.post("")
async def create_conversation(body: CreateConvBody, claims: dict = Depends(require_user)) -> JSONResponse:
    """Tạo ca → Conversation (201). user_id từ JWT claims. provider/model optional (D-45b c)."""
    # validate provider nếu truyền — fail LOUD (4-field) thay vì lưu provider sai → hang lúc chạy.
    if body.provider:
        from app.orch.providers import providers as _providers

        if body.provider not in {p["name"] for p in _providers.public_view()}:
            raise ApiError(
                400,
                "bad_provider",
                f"provider '{body.provider}' không có trong cấu hình.",
                "Xem GET /api/models để lấy tên provider hợp lệ.",
                retryable=False,
            )
    conv = await store.create_conversation(claims["username"], body.title, body.provider, body.model)
    return JSONResponse(status_code=201, content=conv)


@router.get("")
async def list_conversations(claims: dict = Depends(require_user)) -> list[dict[str, Any]]:
    """List ca của user (200) — resource trần."""
    return await store.list_conversations(claims["username"])


@router.get("/{conv_id}")
async def get_conversation(conv_id: str, claims: dict = Depends(require_user)) -> dict[str, Any]:
    """Full state: {conversation, messages[], tasks[]} (CONTRACT §3 ConversationFullState)."""
    conv = await store.get_conversation(conv_id)
    if conv is None:
        raise ApiError(404, "not_found", f"Không có ca '{conv_id}'.", "Kiểm lại id ca.", retryable=False)
    messages = await store.list_messages(conv_id)
    tasks = await store.list_tasks(conv_id)
    cards = await store.list_cards(conv_id)  # canvas reload (canvas-present §4)
    return {"conversation": conv, "messages": messages, "tasks": tasks, "cards": cards}


@router.post("/{conv_id}/chat")
async def chat(conv_id: str, body: ChatBody, request: Request, claims: dict = Depends(require_user)) -> JSONResponse:
    """Đẩy user_message vào phòng (spine) → 202 NGAY (main stream qua SSE, KHÔNG chờ).

    Main bận → handle_room_event tự xếp queue (T1-2). Lưu message user TRƯỚC, rồi spawn lượt.
    """
    conv = await store.get_conversation(conv_id)
    if conv is None:
        raise ApiError(404, "not_found", f"Không có ca '{conv_id}'.", "Tạo ca trước khi chat.", retryable=False)

    await store.add_message(conv_id, "user", body.content)  # persist TRƯỚC (§5)
    # spawn lượt phòng — KHÔNG await (main stream qua SSE; /chat trả 202 ngay)
    asyncio.ensure_future(room.handle_room_event(conv_id, "user_message", {"content": body.content}))
    return JSONResponse(status_code=202, content={"queued": True})
