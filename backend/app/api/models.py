"""Models/providers router (D-45b b) — cho FE dropdown chọn provider/model.

GET /api/models — list provider (public_view: name/kind/models/default/has_key) KHÔNG kèm key.
Luật bí mật (port battle): endpoint này KHÔNG BAO GIỜ trả api_key — chỉ has_key true/false.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth.deps import require_user
from app.orch.providers import providers

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
async def list_models(claims: dict = Depends(require_user)) -> dict[str, Any]:
    """Provider + model cho FE dropdown. reload() bắt .env mới (điền key runtime → has_key đổi).

    Trả {providers: [...], default: <name>}. KHÔNG key (public_view). default = provider mặc định
    (FE chọn sẵn). Mỗi provider: {name, kind, base_url, models[], default, has_key, note}.
    """
    providers.reload()
    return {"providers": providers.public_view(), "default": providers.default_name()}
