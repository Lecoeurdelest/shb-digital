"""Public readiness probe; success non-sensitive, failure 503 theo envelope toàn hệ."""

from __future__ import annotations

from fastapi import APIRouter

from app.errors import ApiError
from app.readiness import ReadinessFailure, readiness_snapshot

router = APIRouter(tags=["health"])


@router.get("/api/ready")
async def ready() -> dict:
    try:
        return await readiness_snapshot()
    except ReadinessFailure as exc:
        raise ApiError(
            503,
            "not_ready",
            "Dịch vụ chưa sẵn sàng.",
            "Kiểm tra DB, migration, provider và role mount trong log máy chủ.",
            retryable=True,
        ) from exc
