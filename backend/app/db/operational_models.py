"""SQLAlchemy metadata for operational extension tables introduced after S21."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("btrim(slug)<>''", name="ck_tenants_slug_not_blank"),
        CheckConstraint("btrim(name)<>''", name="ck_tenants_name_not_blank"),
        UniqueConstraint("slug", name="uq_tenants_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class ConversationGroup(Base):
    __tablename__ = "conversation_groups"
    __table_args__ = (
        CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 80", name="ck_conversation_groups_name"),
        Index(
            "uq_conversation_groups_tenant_name_ci",
            "tenant_id",
            "created_by",
            text("lower(name)"),
            unique=True,
        ),
        Index("ix_conversation_groups_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class Party(Base):
    __tablename__ = "parties"

    owner_id: Mapped[str] = mapped_column(Text, primary_key=True)
    party_type: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class TaskAttempt(Base):
    __tablename__ = "task_attempts"
    __table_args__ = (UniqueConstraint("task_id", "attempt_no", name="uq_task_attempts_number"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer)
    worker_id: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class ApprovalExecutionAttempt(Base):
    __tablename__ = "approval_execution_attempts"
    __table_args__ = (UniqueConstraint("approval_id", "attempt_no", name="uq_approval_attempts_number"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("approvals.id", ondelete="SET NULL"), nullable=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer)
    worker_id: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    aggregate_type: Mapped[str] = mapped_column(Text)
    aggregate_id: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, server_default="0")
    available_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    locked_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class ExternalCaseLink(Base):
    __tablename__ = "external_case_links"
    __table_args__ = (
        UniqueConstraint("source_system", "external_case_id", name="uq_external_case_source_identity"),
        UniqueConstraint("conversation_id", name="uq_external_case_conversation"),
        CheckConstraint("source_version > 0", name="ck_external_case_source_version"),
        CheckConstraint("loan_amount_vnd IS NULL OR loan_amount_vnd >= 0", name="ck_external_case_amount"),
        CheckConstraint("jsonb_typeof(document_refs)='array'", name="ck_external_case_document_refs"),
        CheckConstraint("jsonb_typeof(missing_fields)='array'", name="ck_external_case_missing_fields"),
        CheckConstraint(
            "case_status IN ('received','missing_information','ready_for_preassessment',"
            "'preassessment_in_progress','needs_specialist','ready_for_handover','cancelled')",
            name="ck_external_case_status",
        ),
        Index("ix_external_case_status_synced", "case_status", "synced_at"),
        Index("ix_external_case_source_synced", "source_system", "synced_at"),
        Index("ix_external_case_links_tenant_status_synced", "tenant_id", "case_status", "synced_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )
    source_system: Mapped[str] = mapped_column(Text)
    external_case_id: Mapped[str] = mapped_column(Text)
    internal_application_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    party_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_rm_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    loan_amount_vnd: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    document_refs: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    missing_fields: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    source_version: Mapped[int] = mapped_column(BigInteger)
    content_hash: Mapped[str] = mapped_column(String(64))
    case_status: Mapped[str] = mapped_column(Text)
    data_as_of: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    synced_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class IntegrationInbox(Base):
    __tablename__ = "integration_inbox"
    __table_args__ = (
        UniqueConstraint("source_system", "event_id", name="uq_integration_inbox_source_event"),
        CheckConstraint("schema_version > 0", name="ck_integration_inbox_schema_version"),
        CheckConstraint("source_version > 0", name="ck_integration_inbox_source_version"),
        CheckConstraint("jsonb_typeof(payload)='object'", name="ck_integration_inbox_payload"),
        CheckConstraint("jsonb_typeof(receipt)='object'", name="ck_integration_inbox_receipt"),
        Index("ix_integration_inbox_case_received", "source_system", "external_case_id", "received_at"),
        Index(
            "ix_integration_inbox_tenant_case_received",
            "tenant_id",
            "source_system",
            "external_case_id",
            "received_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )
    source_system: Mapped[str] = mapped_column(Text)
    event_id: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[int] = mapped_column(Integer)
    external_case_id: Mapped[str] = mapped_column(Text)
    source_version: Mapped[int] = mapped_column(BigInteger)
    payload: Mapped[dict] = mapped_column(JSONB)
    payload_hash: Mapped[str] = mapped_column(String(64))
    receipt: Mapped[dict] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class PromptDefinitionModel(Base):
    __tablename__ = "prompt_definitions"

    prompt_key: Mapped[str] = mapped_column(Text, primary_key=True)
    scope: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    variables: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    default_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class PromptVersionModel(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_key", "version", name="uq_prompt_versions_number"),
        UniqueConstraint("prompt_key", "checksum", name="uq_prompt_versions_checksum"),
        UniqueConstraint("prompt_key", "id", name="uq_prompt_versions_key_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    prompt_key: Mapped[str] = mapped_column(ForeignKey("prompt_definitions.prompt_key"))
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(64))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    created_by: Mapped[str] = mapped_column(Text, server_default="bootstrap")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class PromptBindingModel(Base):
    __tablename__ = "prompt_bindings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["prompt_key", "version_id"],
            ["prompt_versions.prompt_key", "prompt_versions.id"],
            ondelete="RESTRICT",
        ),
    )

    prompt_key: Mapped[str] = mapped_column(Text, primary_key=True)
    environment: Mapped[str] = mapped_column(Text, primary_key=True, server_default="default")
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    activated_by: Mapped[str] = mapped_column(Text, server_default="bootstrap")
    activated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
