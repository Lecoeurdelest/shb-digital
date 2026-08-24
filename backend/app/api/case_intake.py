"""D-77 service intake and admin case read-model routes."""

from __future__ import annotations

import asyncio
import hmac
import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.auth.deps import require_admin
from app.case_intake.config import CaseIntakeConfigError, SourceConfig, load_case_intake_config
from app.case_intake.read_model import list_cases
from app.case_intake.schemas import CaseEventV1
from app.case_intake.service import ingest_case_event
from app.errors import ApiError
from app.tenancy import tenant_id_from_claims

router = APIRouter(tags=["case-intake"])
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
            "Cổng tiếp nhận hồ sơ chưa sẵn sàng.",
            "Kiểm tra cấu hình nguồn trong vận hành.",
            retryable=True,
        ) from exc


def _source_config(source: str, authorization: str) -> SourceConfig:
    if not authorization.startswith("Bearer ") or not authorization[7:]:
        raise ApiError(401, "unauthorized", "Thiếu service credential hợp lệ.", "Cấp Bearer credential.")
    source_config = _config().sources.get(source)
    if source_config is None or not source_config.enabled or source_config.api_key() is None:
        raise ApiError(403, "source_disabled", "Nguồn intake không được phép hoạt động.", "Kiểm tra source allowlist.")
    if not hmac.compare_digest(authorization[7:], source_config.api_key() or ""):
        raise ApiError(401, "unauthorized", "Service credential không hợp lệ.", "Cấp lại credential.")
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
            "Nguồn hồ sơ chưa được cấu hình.",
            "Kiểm tra tên nguồn tích hợp.",
        )
    if not source_config.enabled:
        raise ApiError(
            403,
            "source_disabled",
            "Nguồn hồ sơ đang bị tắt.",
            "Liên hệ vận hành tích hợp để kiểm tra trạng thái nguồn.",
        )


def _parse_payload(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApiError(400, "bad_request", "Body JSON không hợp lệ.", "Gửi CaseEventV1 hợp lệ.") from exc
    if not isinstance(payload, dict):
        raise ApiError(400, "bad_request", "Body phải là JSON object.", "Gửi CaseEventV1 hợp lệ.")
    return payload


@router.post("/api/integrations/v1/case-events")
async def receive_case_event(request: Request) -> JSONResponse:
    raw = await request.body()
    if len(raw) > _ABSOLUTE_MAX_BYTES:
        raise ApiError(413, "payload_too_large", "Payload vượt giới hạn intake.", "Chỉ gửi field allowlist D-77.")
    payload = _parse_payload(raw)
    source = payload.get("source_system")
    if not isinstance(source, str):
        raise ApiError(400, "bad_request", "Thiếu source_system hợp lệ.", "Gửi source_system đã cấu hình.")
    source_config = _source_config(source, request.headers.get("Authorization", ""))
    if len(raw) > source_config.max_payload_bytes:
        raise ApiError(413, "payload_too_large", "Payload vượt giới hạn của nguồn.", "Chỉ gửi field allowlist D-77.")
    try:
        event = CaseEventV1.model_validate(payload)
    except ValidationError as exc:
        raise ApiError(400, "bad_request", "CaseEventV1 không hợp lệ.", "Kiểm tra field và kiểu dữ liệu.") from exc
    if request.headers.get("Idempotency-Key") != event.event_id:
        raise ApiError(
            400,
            "bad_idempotency_key",
            "Idempotency-Key phải bằng event_id.",
            "Gửi lại với đúng source event_id.",
        )
    if event.schema_version not in source_config.accepted_schema_versions:
        raise ApiError(400, "unsupported_schema", "schema_version không được hỗ trợ.", "Dùng schema version allowlist.")
    if event.event_type not in source_config.allowed_event_types:
        raise ApiError(403, "event_not_allowed", "Loại event không được phép.", "Kiểm tra source allowlist.")
    if event.case.product_code not in source_config.allowed_products:
        raise ApiError(403, "product_not_allowed", "Sản phẩm không được phép intake.", "Kiểm tra product allowlist.")
    receipt = await asyncio.to_thread(ingest_case_event, event, shadow=source_config.auto_start == "shadow")
    return JSONResponse(status_code=202, content=receipt)


@router.get("/api/cases")
async def get_cases(
    status: str | None = None,
    source: str | None = None,
    limit: int = Query(100, ge=1, le=200),
    claims: dict = Depends(require_admin),
) -> list[dict[str, Any]]:
    if status is not None and status not in _CASE_STATUSES:
        raise ApiError(400, "bad_status", "Trạng thái case không hợp lệ.", "Dùng CaseStatus trong contract.")
    if source is not None:
        _validate_read_source(source)
    return await asyncio.to_thread(
        list_cases,
        status=status,
        source=source,
        limit=limit,
        tenant_id=tenant_id_from_claims(claims),
    )
