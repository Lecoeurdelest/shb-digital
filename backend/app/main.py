"""FastAPI entry point and orchestrator startup.

Startup validates configuration, cleans up orphaned tasks, and connects the SDK
runner and event sink. Errors use the application-wide four-field envelope.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent_config import router as agent_config_router
from app.api.approvals import router as approvals_router
from app.api.audit import router as audit_router
from app.api.case_intake import router as case_intake_router
from app.api.compare import router as compare_router
from app.api.conversation_groups import router as conversation_groups_router
from app.api.conversations import router as conversations_router
from app.api.cost import router as cost_router
from app.api.form_intake import router as form_intake_router
from app.api.interrupt import router as interrupt_router
from app.api.models import router as models_router
from app.api.notifications import router as notifications_router
from app.api.readiness import router as readiness_router
from app.api.sse import router as sse_router
from app.api.stats import router as stats_router
from app.auth.router import me_router
from app.auth.router import router as auth_router
from app.config import CORS_ORIGINS
from app.errors import register_error_handler

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Boot cleanup marks queued/running tasks from the previous process as failed.
    # D-39: DEV_SKIP_AUTH grants admin access and must not be used for a real deployment.
    from app.case_intake.config import load_case_intake_config
    from app.config import DEV_SKIP_AUTH
    from app.orch import main_session, registry, store
    from app.reason_taxonomy import activate_reason_taxonomy
    from app.runtime_security import validate_runtime_security

    validate_runtime_security()  # bank_dc must fail before DB cleanup or agent boot.
    # D-81/D-82: reject invalid static artifacts before any mutation. Tenant resolution
    # happens in the intake transaction, so this check does not require DB availability.
    load_case_intake_config()
    activate_reason_taxonomy()

    if DEV_SKIP_AUTH:
        log.warning("DEV_SKIP_AUTH ON: every request has admin access. Do not use in a real deployment.")

    registry.reset_all()
    try:
        # S6 (A): record boot_time before cleanup so tasks queued by this process are safe.
        # UTC matches the queued_at timestamptz column.
        from datetime import UTC, datetime

        boot_time = datetime.now(UTC)
        n = await store.cleanup_orphans(boot_time)
        if n:
            log.info("boot-cleanup: %d orphaned tasks marked failed(server restart)", n)
    except Exception as e:  # noqa: BLE001 — DB unavailability must not prevent app startup.
        log.warning("boot-cleanup skip (DB?): %s", e)
    main_session.boot()  # Connect the SDK runner and event sink for specialist completion.
    try:
        yield
    finally:
        from app.prompting import reset_prompt_service
        from app.storage import reset_registry

        reset_prompt_service()
        reset_registry()


_CORS_METHODS = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
_CORS_HEADERS = ["Authorization", "Content-Type", "Accept"]


def configure_cors(target: FastAPI, origins: tuple[str, ...]) -> None:
    """Use same-origin only unless an explicit allowlist enables embedded clients."""
    if not origins:
        return
    target.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=True,
        allow_methods=_CORS_METHODS,
        allow_headers=_CORS_HEADERS,
    )


app = FastAPI(title="BANK Digital Expert Guild", lifespan=lifespan)
configure_cors(app, CORS_ORIGINS)

register_error_handler(app)  # ApiError and validation share the CONTRACT §0 envelope.
app.include_router(auth_router)
app.include_router(me_router)  # /api/me exposes the D-56 persona.
app.include_router(conversations_router)  # Conversations and chat.
app.include_router(conversation_groups_router)  # D-79: tenant-scoped groups.
app.include_router(sse_router)  # SSE stream.
app.include_router(approvals_router)  # Approval decisions and listing.
app.include_router(agent_config_router)  # Admin prompt versions without provider secrets.
app.include_router(models_router)  # D-45b: available providers and models.
app.include_router(audit_router)  # Tool-call audit search.
app.include_router(interrupt_router)  # Interrupt a specialist.
app.include_router(compare_router)  # Single-agent versus multi-agent comparison.
app.include_router(form_intake_router)  # Customer form submission.
app.include_router(notifications_router)  # Customer notification bell.
app.include_router(stats_router)  # Control Tower statistics and assessments.
app.include_router(cost_router)  # GET /stats/cost + /stats/cost-trend (T16-2)
app.include_router(readiness_router)  # GET /api/ready: DB+migration+provider+role mounts
app.include_router(case_intake_router)  # D-77: service intake and admin case read model.


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}
