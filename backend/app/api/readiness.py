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
            "The service is not ready.",
            "Check the database, migrations, providers, and role mounts in the server logs.",
            retryable=True,
        ) from exc
