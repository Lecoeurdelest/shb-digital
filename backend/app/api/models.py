from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth.deps import require_user
from app.orch.providers import providers

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
async def list_models(claims: dict = Depends(require_user)) -> dict[str, Any]:

    providers.reload()
    return {"providers": providers.public_view(), "default": providers.effective_default()}
