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

from app.auth.deps import can_access_conv, require_user
from app.errors import ApiError
from app.orch import room, store

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateConvBody(BaseModel):
    title: str = "Ca mới"
    provider: str | None = None  # D-45b (c) — tên provider (providers.yaml). null = server-default.
    model: str | None = None  # model string ("sonnet"/"glm-4.6"...). null = default.


class ChatBody(BaseModel):
    content: str


class PatchConvBody(BaseModel):
    """PATCH partial — mọi field optional. title (rename) · provider/model (switch per-turn T15-2)."""

    title: str | None = None
    provider: str | None = None
    model: str | None = None


def _validate_provider_model(provider: str | None, model: str | None, current_provider: str | None) -> None:
    """T15-2: provider ∈ providers khả dụng (public_view — đã loại disabled); model ∈ models của
    provider KẾT QUẢ. model-only → validate theo provider HIỆN TẠI của conv (hoặc effective default nếu
    null) — không phải luôn provider mới (advisor). Lệch → 400 4-field (fail LOUD, không lưu sai)."""
    from app.orch.providers import providers as _providers

    view = _providers.public_view()
    names = {p["name"] for p in view}
    if provider is not None and provider not in names:
        raise ApiError(
            400, "bad_provider", f"provider '{provider}' không có/đã tắt.", "Xem GET /api/models.", retryable=False
        )
    if model is not None:
        # provider hiệu lực cho việc validate model = provider MỚI nếu có, else provider hiện tại, else effective
        eff_provider = provider or current_provider or _providers.effective_default()
        pv = next((p for p in view if p["name"] == eff_provider), None)
        allowed = set(pv["models"]) if pv else set()
        if model not in allowed:
            raise ApiError(
                400,
                "bad_model",
                f"model '{model}' không thuộc provider '{eff_provider}'.",
                f"Model hợp lệ: {sorted(allowed)}." if allowed else "Xem GET /api/models.",
                retryable=False,
            )


def _conv_is_running(conv: dict[str, Any]) -> bool:
    """Ca đang chạy = MAIN turn active (registry.is_busy — in-process, chuẩn nhất) HOẶC còn sub
    queued/running (fire-and-forget sống ngoài room-busy). KHÔNG tin conv.status='running' đơn lẻ
    (stale sau crash — cleanup_orphans tồn tại vì thế). Mục đích: tránh mồ côi task giữa chừng (D-67)."""
    from app.orch import registry

    conv_id = conv["id"]
    if registry.is_busy(conv_id):
        return True
    import psycopg2

    from app.db.config import DATABASE_URL

    try:
        c = psycopg2.connect(DATABASE_URL)
        try:
            with c.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM tasks WHERE conv_id=%s AND status IN ('queued','running') LIMIT 1",
                    (conv_id,),
                )
                return cur.fetchone() is not None
        finally:
            c.close()
    except psycopg2.Error:
        return False  # DB lỗi → không chặn delete/patch vì lý do hạ tầng (router khác sẽ bắt)


@router.post("")
async def create_conversation(body: CreateConvBody, claims: dict = Depends(require_user)) -> JSONResponse:
    """Create a conversation → 201. (Vietnamese detail below.)

    Tạo ca → Conversation (201). user_id từ JWT claims. provider/model optional (D-45b c)."""
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
    """List conversations (admin sees all; customer sees own — D-56 scoping).

    List ca (200). D-56 scoping: admin (ngân hàng) → TẤT CẢ ca; customer/user → CHỈ ca mình."""
    if claims.get("role") == "admin":
        return await store.list_all_conversations()
    return await store.list_conversations(claims["username"])


@router.get("/{conv_id}")
async def get_conversation(conv_id: str, claims: dict = Depends(require_user)) -> dict[str, Any]:
    """Get full conversation state (others' convs → 404-hide, not 403).

    Full state (CONTRACT §3). D-56: ca người khác → 404 (hide existence, KHÔNG 403)."""
    conv = await store.get_conversation(conv_id)
    if conv is None or not can_access_conv(conv, claims):
        raise ApiError(404, "not_found", f"Không có ca '{conv_id}'.", "Kiểm lại id ca.", retryable=False)
    messages = await store.list_messages(conv_id)
    tasks = await store.list_tasks(conv_id)
    cards = await store.list_cards(conv_id)  # canvas reload (canvas-present §4)
    return {"conversation": conv, "messages": messages, "tasks": tasks, "cards": cards}


@router.patch("/{conv_id}")
async def patch_conversation(conv_id: str, body: PatchConvBody, claims: dict = Depends(require_user)) -> dict[str, Any]:
    """Rename (title) và/hoặc switch provider/model per-turn (T15-2/T15-3).

    Chủ ca hoặc admin (can_access_conv — ca người khác → 404-hide Fix E). Body partial: title? provider?
    model?. Provider/model validate (400 nếu lệch). Switch provider/model khi ca đang chạy → 409 (tránh
    lẫn giữa lượt); rename title khi chạy → OK (không mồ côi gì). Lượt chat KẾ dùng provider/model mới
    (main_session đọc conv FRESH mỗi lượt — không cache)."""
    conv = await store.get_conversation(conv_id)
    if conv is None or not can_access_conv(conv, claims):
        raise ApiError(404, "not_found", f"Không có ca '{conv_id}'.", "Kiểm lại id ca.", retryable=False)
    if body.title is None and body.provider is None and body.model is None:
        raise ApiError(
            400, "empty_patch", "Không có field nào để cập nhật.", "Truyền title, provider hoặc model.", retryable=False
        )
    # switch provider/model đổi HÀNH VI lượt sau → chặn khi đang chạy (rename title thì không).
    if (body.provider is not None or body.model is not None) and _conv_is_running(conv):
        raise ApiError(
            409,
            "conv_running",
            "Ca đang chạy — không đổi provider/model giữa lượt.",
            "Đợi lượt hiện tại xong rồi đổi.",
            retryable=True,
        )
    _validate_provider_model(body.provider, body.model, conv.get("provider"))
    updated = await store.update_conversation(conv_id, body.title, body.provider, body.model)
    if updated is None:  # race: ca bị xoá giữa chừng
        raise ApiError(404, "not_found", f"Không có ca '{conv_id}'.", "Ca có thể vừa bị xoá.", retryable=False)
    return updated


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str, claims: dict = Depends(require_user)) -> dict[str, Any]:
    """Hard delete ca + nội dung (cards/tasks/messages) — GIỮ audit (tool_calls + phiếu đã quyết, D-67).

    Chủ ca/admin (404-hide). Chặn 409 'conv_running' khi đang chạy (tránh mồ côi task); chặn 409
    'has_pending_approval' khi còn phiếu pending (quyết phiếu trước). Ca không tồn tại → 404 (idempotent
    contract dispatch — KHÔNG 204)."""
    conv = await store.get_conversation(conv_id)
    if conv is None or not can_access_conv(conv, claims):
        raise ApiError(404, "not_found", f"Không có ca '{conv_id}'.", "Kiểm lại id ca.", retryable=False)
    if _conv_is_running(conv):
        raise ApiError(
            409,
            "conv_running",
            "Ca đang chạy — không thể xoá giữa chừng.",
            "Đợi ca chạy xong rồi xoá.",
            retryable=True,
        )
    result = await store.delete_conversation(conv_id)
    if result == "pending":
        raise ApiError(
            409,
            "has_pending_approval",
            "Ca còn phiếu chờ duyệt — không thể xoá.",
            "Quyết phiếu (duyệt/từ chối) trước khi xoá ca.",
            retryable=True,
        )
    if result == "not_found":  # race: xoá giữa 2 lần đọc
        raise ApiError(404, "not_found", f"Không có ca '{conv_id}'.", "Ca có thể vừa bị xoá.", retryable=False)
    return {"deleted": True, "id": conv_id}


@router.post("/{conv_id}/chat")
async def chat(conv_id: str, body: ChatBody, request: Request, claims: dict = Depends(require_user)) -> JSONResponse:
    """Post a user message → 202 immediately (MAIN streams the reply over SSE, no wait).

    Đẩy user_message vào phòng (spine) → 202 NGAY (main stream qua SSE, KHÔNG chờ).

    Main bận → handle_room_event tự xếp queue (T1-2). Lưu message user TRƯỚC, rồi spawn lượt.
    """
    conv = await store.get_conversation(conv_id)
    if conv is None or not can_access_conv(conv, claims):
        # D-56: ca người khác → 404 (hide) — không cho chat vào ca khách khác.
        raise ApiError(404, "not_found", f"Không có ca '{conv_id}'.", "Tạo ca trước khi chat.", retryable=False)

    await store.add_message(conv_id, "user", body.content)  # persist TRƯỚC (§5)
    # spawn lượt phòng — KHÔNG await (main stream qua SSE; /chat trả 202 ngay)
    asyncio.ensure_future(room.handle_room_event(conv_id, "user_message", {"content": body.content}))
    return JSONResponse(status_code=202, content={"queued": True})
