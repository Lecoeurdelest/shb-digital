"""D-77 service intake and admin case read-model routes."""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.auth.deps import require_admin
from app.case_intake.config import CaseIntakeConfigError, SourceConfig, load_case_intake_config
from app.case_intake.read_model import get_case, list_cases
from app.case_intake.schemas import CaseEventV1
from app.case_intake.service import ingest_case_event
from app.errors import ApiError
from app.tenancy import tenant_id_from_claims

router = APIRouter(tags=["case-intake"])
log = logging.getLogger("api.case_intake")
_ABSOLUTE_MAX_BYTES = 1_048_576
_CASE_STATUSES = {
    "received",
    "missing_information",
    "ready_for_preassessment",
    "preassessment_in_progress",
    "needs_specialist",
    "ready_for_handover",
    "cancelled",
}


def _config() -> Any:
    try:
        return load_case_intake_config()
    except CaseIntakeConfigError as exc:
        raise ApiError(
            503,
            "case_intake_not_ready",
            "The case intake endpoint is not ready.",
            "Check the source configuration in operations.",
            retryable=True,
        ) from exc


def _source_config(source: str, authorization: str) -> SourceConfig:
    if not authorization.startswith("Bearer ") or not authorization[7:]:
        raise ApiError(401, "unauthorized", "A valid service credential is required.", "Provide a Bearer credential.")
    source_config = _config().sources.get(source)
    if source_config is None or not source_config.enabled or source_config.api_key() is None:
        raise ApiError(
            403, "source_disabled", "This intake source is not permitted to operate.", "Check the source allowlist."
        )
    if not hmac.compare_digest(authorization[7:], source_config.api_key() or ""):
        raise ApiError(401, "unauthorized", "The service credential is invalid.", "Issue a new credential.")
    return source_config


def _validate_read_source(source: str) -> None:
    """Expose configured source state to admins without leaking config or credentials."""
    if source == "internal_operations":
        return
    source_config = _config().sources.get(source)
    if source_config is None:
        raise ApiError(
            404,
            "source_not_configured",
            "The case source is not configured.",
            "Check the integration source name.",
        )
    if not source_config.enabled:
        raise ApiError(
            403,
            "source_disabled",
            "The case source is disabled.",
            "Contact integration operations to check the source status.",
        )


def _parse_payload(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApiError(400, "bad_request", "The JSON body is invalid.", "Send a valid CaseEventV1.") from exc
    if not isinstance(payload, dict):
        raise ApiError(400, "bad_request", "The body must be a JSON object.", "Send a valid CaseEventV1.")
    return payload


def _notify_rfi(case_id: str, missing_fields: tuple[str, ...]) -> None:
    """Post-commit best effort: transport failure must never rewrite an accepted receipt."""
    try:
        from app.notify.channels import notify_channel_case_rfi

        notify_channel_case_rfi(case_id, list(missing_fields))
    except Exception as exc:  # noqa: BLE001
        log.warning("failed to send case RFI notification case=%s exception=%s", case_id[:8], type(exc).__name__)


def _case_not_found() -> ApiError:
    return ApiError(
        404,
        "not_found",
        "The case was not found within the tenant scope.",
        "Check the case link.",
        retryable=False,
    )


@router.post("/api/integrations/v1/case-events")
async def receive_case_event(request: Request) -> JSONResponse:
    raw = await request.body()
    if len(raw) > _ABSOLUTE_MAX_BYTES:
        raise ApiError(
            413, "payload_too_large", "The payload exceeds the intake limit.", "Send only fields allowed by D-77."
        )
    payload = _parse_payload(raw)
    source = payload.get("source_system")
    if not isinstance(source, str):
        raise ApiError(400, "bad_request", "A valid source_system is required.", "Send a configured source_system.")
    source_config = _source_config(source, request.headers.get("Authorization", ""))
    if len(raw) > source_config.max_payload_bytes:
        raise ApiError(
            413, "payload_too_large", "The payload exceeds the source limit.", "Send only fields allowed by D-77."
        )
    try:
        event = CaseEventV1.model_validate(payload)
    except ValidationError as exc:
        raise ApiError(400, "bad_request", "CaseEventV1 is invalid.", "Check the fields and data types.") from exc
    if request.headers.get("Idempotency-Key") != event.event_id:
        raise ApiError(
            400,
            "bad_idempotency_key",
            "Idempotency-Key must equal event_id.",
            "Resend the request with the correct source event_id.",
        )
    if event.schema_version not in source_config.accepted_schema_versions:
        raise ApiError(
            400, "unsupported_schema", "schema_version is not supported.", "Use an allowlisted schema version."
        )
    if event.event_type not in source_config.allowed_event_types:
        raise ApiError(403, "event_not_allowed", "This event type is not allowed.", "Check the source allowlist.")
    if event.case.product_code not in source_config.allowed_products:
        raise ApiError(
            403, "product_not_allowed", "This product is not allowed for intake.", "Check the product allowlist."
        )
    profile = source_config.profile_for(event.case.product_code)
    result = await asyncio.to_thread(
        ingest_case_event,
        event,
        tenant_slug=source_config.tenant_slug,
        shadow=profile.auto_start == "shadow",
    )

    response = JSONResponse(status_code=202, content=result.receipt)
    if result.rfi_candidate is not None:
        _notify_rfi(result.rfi_candidate.case_id, result.rfi_candidate.missing_fields)
    return response


@router.get("/api/cases")
async def get_cases(
    status: str | None = None,
    source: str | None = None,
    limit: int = Query(100, ge=1, le=200),
    claims: dict = Depends(require_admin),
) -> list[dict[str, Any]]:
    if status is not None and status not in _CASE_STATUSES:
        raise ApiError(400, "bad_status", "The case status is invalid.", "Use a CaseStatus defined by the contract.")
    if source is not None:
        _validate_read_source(source)
    return await asyncio.to_thread(
        list_cases,
        status=status,
        source=source,
        limit=limit,
        tenant_id=tenant_id_from_claims(claims),
    )


@router.get("/api/cases/{case_id}")
async def get_exact_case(case_id: str, claims: dict = Depends(require_admin)) -> dict[str, Any]:
    try:
        canonical_case_id = str(UUID(case_id))
    except (ValueError, AttributeError) as exc:
        raise _case_not_found() from exc
    row = await asyncio.to_thread(get_case, canonical_case_id, tenant_id=tenant_id_from_claims(claims))
    if row is None:
        raise _case_not_found()
    return row
