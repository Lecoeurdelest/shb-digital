"""Conversation-group REST resource (D-79)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.auth.deps import require_user
from app.errors import ApiError
from app.orch import store_groups
from app.tenancy import tenant_id_from_claims

router = APIRouter(prefix="/api/conversation-groups", tags=["conversation-groups"])


class GroupBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        name = " ".join(value.split())
        if not name:
            raise ValueError("name must not be blank")
        return name


def _scope(claims: dict[str, Any]) -> tuple[str, str, bool]:
    return tenant_id_from_claims(claims), str(claims["username"]), claims.get("role") == "admin"


def _conflict(name: str) -> ApiError:
    return ApiError(
        409,
        "group_name_conflict",
        f"Đã có nhóm '{name}'.",
        "Chọn tên khác hoặc dùng nhóm hiện có.",
        retryable=False,
    )


@router.get("")
async def list_groups(claims: dict = Depends(require_user)) -> list[dict[str, Any]]:
    return await store_groups.list_groups(*_scope(claims))


@router.post("")
async def create_group(body: GroupBody, claims: dict = Depends(require_user)) -> JSONResponse:
    tenant_id, username, _ = _scope(claims)
    try:
        group = await store_groups.create_group(tenant_id, username, body.name)
    except store_groups.GroupNameConflict as exc:
        raise _conflict(body.name) from exc
    return JSONResponse(status_code=201, content=group)


@router.patch("/{group_id}")
async def update_group(group_id: str, body: GroupBody, claims: dict = Depends(require_user)) -> dict[str, Any]:
    try:
        group = await store_groups.update_group(group_id, *_scope(claims), body.name)
    except store_groups.GroupNameConflict as exc:
        raise _conflict(body.name) from exc
    if group is None:
        raise ApiError(404, "group_not_found", "Không có nhóm này.", "Tải lại danh sách nhóm.", retryable=False)
    return group


@router.delete("/{group_id}")
async def delete_group(group_id: str, claims: dict = Depends(require_user)) -> dict[str, Any]:
    if not await store_groups.delete_group(group_id, *_scope(claims)):
        raise ApiError(404, "group_not_found", "Không có nhóm này.", "Tải lại danh sách nhóm.", retryable=False)
    return {"deleted": True, "id": group_id}
