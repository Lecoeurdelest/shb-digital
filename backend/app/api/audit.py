from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.auth.deps import require_admin
from app.errors import ApiError
from app.orch import store_audit
from app.tenancy import tenant_id_from_claims

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
async def list_audit(
    task_id: str | None = Query(None),
    conv_id: str | None = Query(None),
    tool: str | None = Query(None),
    actor: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    claims: dict = Depends(require_admin),
) -> list[dict[str, Any]]:

    filters = {"task_id": task_id, "conv_id": conv_id, "tool": tool, "actor": actor}

    active = {k: v for k, v in filters.items() if v}
    try:
        return await store_audit.query_tool_calls(
            active,
            limit=limit,
            tenant_id=tenant_id_from_claims(claims),
        )
    except Exception as e:  # noqa: BLE001
        raise ApiError(
            400,
            "bad_filter",
            f"Invalid audit filter: {str(e)[:100]}",
            "Check that task_id and conv_id use the correct format.",
            retryable=False,
        ) from e
