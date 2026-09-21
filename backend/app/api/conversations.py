from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth.deps import can_access_conv, require_user
from app.errors import ApiError
from app.orch import room, store, store_groups
from app.storage import connect_core
from app.tenancy import tenant_id_from_claims

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateConvBody(BaseModel):
    title: str = "New case"
    group_id: str | None = None
    provider: str | None = None
    model: str | None = None  # model string ("sonnet"/"glm-4.6"...). null = default.


class ChatBody(BaseModel):
    content: str


class PatchConvBody(BaseModel):
    title: str | None = None
    provider: str | None = None
    model: str | None = None
    group_id: str | None = None


def _validate_provider_model(provider: str | None, model: str | None, current_provider: str | None) -> None:

    from app.orch.providers import providers as _providers

    view = _providers.public_view()
    names = {p["name"] for p in view}
    if provider is not None and provider not in names:
        raise ApiError(
            400,
            "bad_provider",
            f"provider '{provider}' is unavailable or disabled.",
            "See GET /api/models.",
            retryable=False,
        )
    if model is not None:
        eff_provider = provider or current_provider or _providers.effective_default()
        pv = next((p for p in view if p["name"] == eff_provider), None)
        allowed = set(pv["models"]) if pv else set()
        if model not in allowed:
            raise ApiError(
                400,
                "bad_model",
                f"model '{model}' does not belong to provider '{eff_provider}'.",
                f"Valid models: {sorted(allowed)}." if allowed else "See GET /api/models.",
                retryable=False,
            )


def _conv_is_running(conv: dict[str, Any]) -> bool:

    from app.orch import registry

    conv_id = conv["id"]
    if registry.is_busy(conv_id):
        return True
    import psycopg2

    try:
        c = connect_core()
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
        return False


@router.post("")
async def create_conversation(body: CreateConvBody, claims: dict = Depends(require_user)) -> JSONResponse:

    if body.provider:
        from app.orch.providers import providers as _providers

        if body.provider not in {p["name"] for p in _providers.public_view()}:
            raise ApiError(
                400,
                "bad_provider",
                f"provider '{body.provider}' is not configured.",
                "See GET /api/models for valid provider names.",
                retryable=False,
            )
    tenant_id = tenant_id_from_claims(claims)
    is_admin = claims.get("role") == "admin"
    if body.group_id is not None and not await store_groups.can_use_group(
        body.group_id, tenant_id, claims["username"], is_admin
    ):
        raise ApiError(404, "group_not_found", "This group does not exist.", "Reload the group list.", retryable=False)
    conv = await store.create_conversation(
        claims["username"], body.title, body.provider, body.model, tenant_id, body.group_id
    )
    return JSONResponse(status_code=201, content=conv)


@router.get("")
async def list_conversations(claims: dict = Depends(require_user)) -> list[dict[str, Any]]:

    tenant_id = tenant_id_from_claims(claims)
    if claims.get("role") == "admin":
        return await store.list_all_conversations(tenant_id)
    return await store.list_conversations(claims["username"], tenant_id)


@router.get("/{conv_id}")
async def get_conversation(conv_id: str, claims: dict = Depends(require_user)) -> dict[str, Any]:

    conv = await store.get_conversation(conv_id)
    if conv is None or not can_access_conv(conv, claims):
        raise ApiError(404, "not_found", f"Case '{conv_id}' does not exist.", "Check the case ID.", retryable=False)
    messages = await store.list_messages(conv_id)
    tasks = await store.list_tasks(conv_id)
    cards = await store.list_cards(conv_id)  # canvas reload (canvas-present §4)
    return {"conversation": conv, "messages": messages, "tasks": tasks, "cards": cards}


@router.patch("/{conv_id}")
async def patch_conversation(conv_id: str, body: PatchConvBody, claims: dict = Depends(require_user)) -> dict[str, Any]:

    conv = await store.get_conversation(conv_id)
    if conv is None or not can_access_conv(conv, claims):
        raise ApiError(404, "not_found", f"Case '{conv_id}' does not exist.", "Check the case ID.", retryable=False)
    group_present = "group_id" in body.model_fields_set
    if body.title is None and body.provider is None and body.model is None and not group_present:
        raise ApiError(
            400,
            "empty_patch",
            "No fields were provided for update.",
            "Provide title, provider, or model.",
            retryable=False,
        )

    if (body.provider is not None or body.model is not None) and _conv_is_running(conv):
        raise ApiError(
            409,
            "conv_running",
            "The case is running; provider and model cannot change mid-turn.",
            "Wait for the current turn to finish before changing them.",
            retryable=True,
        )
    _validate_provider_model(body.provider, body.model, conv.get("provider"))
    tenant_id = tenant_id_from_claims(claims)
    if (
        group_present
        and body.group_id is not None
        and not await store_groups.can_use_group(
            body.group_id,
            tenant_id,
            claims["username"],
            claims.get("role") == "admin",
        )
    ):
        raise ApiError(404, "group_not_found", "This group does not exist.", "Reload the group list.", retryable=False)
    updated = await store.update_conversation(
        conv_id,
        body.title,
        body.provider,
        body.model,
        body.group_id,
        group_present,
    )
    if updated is None:
        raise ApiError(
            404,
            "not_found",
            f"Case '{conv_id}' does not exist.",
            "The case may have just been deleted.",
            retryable=False,
        )
    return updated


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str, claims: dict = Depends(require_user)) -> dict[str, Any]:

    conv = await store.get_conversation(conv_id)
    if conv is None or not can_access_conv(conv, claims):
        raise ApiError(404, "not_found", f"Case '{conv_id}' does not exist.", "Check the case ID.", retryable=False)
    if _conv_is_running(conv):
        raise ApiError(
            409,
            "conv_running",
            "The case is running and cannot be deleted mid-turn.",
            "Wait for the case to finish before deleting it.",
            retryable=True,
        )
    result = await store.delete_conversation(conv_id)
    if result == "pending":
        raise ApiError(
            409,
            "has_pending_approval",
            "The case has a pending approval and cannot be deleted.",
            "Approve or reject the request before deleting the case.",
            retryable=True,
        )
    if result == "not_found":
        raise ApiError(
            404,
            "not_found",
            f"Case '{conv_id}' does not exist.",
            "The case may have just been deleted.",
            retryable=False,
        )
    return {"deleted": True, "id": conv_id}


@router.post("/{conv_id}/chat")
async def chat(conv_id: str, body: ChatBody, request: Request, claims: dict = Depends(require_user)) -> JSONResponse:

    conv = await store.get_conversation(conv_id)
    if conv is None or not can_access_conv(conv, claims):
        raise ApiError(
            404,
            "not_found",
            f"Case '{conv_id}' does not exist.",
            "Create the case before sending a message.",
            retryable=False,
        )

    await store.add_message(conv_id, "user", body.content)

    asyncio.ensure_future(room.handle_room_event(conv_id, "user_message", {"content": body.content}))
    return JSONResponse(status_code=202, content={"queued": True})
