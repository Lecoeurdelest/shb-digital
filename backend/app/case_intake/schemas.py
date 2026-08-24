"""Machine-validated D-77 event and receipt shapes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CaseStatus = Literal[
    "received",
    "missing_information",
    "ready_for_preassessment",
    "preassessment_in_progress",
    "needs_specialist",
    "ready_for_handover",
    "cancelled",
]
EventType = Literal["case.snapshot_upserted", "case.preassessment_requested", "case.cancelled"]


class CaseSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_case_id: str = Field(min_length=1, max_length=200)
    external_party_id: str | None = Field(default=None, min_length=1, max_length=200)
    assigned_rm_subject: str | None = Field(default=None, min_length=1, max_length=200)
    product_code: str = Field(min_length=1, max_length=100)
    loan_amount_vnd: int = Field(ge=0, le=9_223_372_036_854_775_807)
    document_refs: list[str] = Field(default_factory=list, max_length=500)
    missing_fields: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("document_refs", "missing_fields")
    @classmethod
    def validate_string_list(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 200 for value in values):
            raise ValueError("list items must be non-empty strings no longer than 200 characters")
        return values


class CaseEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    event_id: str = Field(min_length=1, max_length=200)
    event_type: EventType
    source_system: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    source_version: int = Field(ge=1)
    occurred_at: datetime
    case: CaseSnapshotV1

    @field_validator("occurred_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("occurred_at must be an ISO-8601 UTC timestamp")
        return value


class CaseEventReceipt(BaseModel):
    id: str
    event_id: str
    status: Literal["accepted", "duplicate", "stale_ignored"]
    source_system: str
    external_case_id: str
    source_version: int
    case_status: CaseStatus
    conversation_id: str | None
