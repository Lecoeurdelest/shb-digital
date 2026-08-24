"""SQLAlchemy metadata for core domain and runtime tables.

Alembic migrations remain the physical source of truth. Legacy text identifiers stay beside new
nullable FK columns during the D-76 migration window so old audit/test rows are not deleted.
Operational extension tables live in ``operational_models.py``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# ---------------------------------------------------------------------------
# Nghiệp vụ (business data — cột khớp SQLite LAB seed/shb-132.db)
# ---------------------------------------------------------------------------


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String, ForeignKey("parties.owner_id"), primary_key=True)
    full_name: Mapped[str | None] = mapped_column(Text)
    age: Mapped[int | None] = mapped_column(Integer)
    occupation: Mapped[str | None] = mapped_column(Text)
    monthly_income: Mapped[int | None] = mapped_column(BigInteger)
    region: Mapped[str | None] = mapped_column(Text)
    id_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    segment: Mapped[str | None] = mapped_column(Text, nullable=True)


class Loan(Base):
    __tablename__ = "loans"

    loan_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str | None] = mapped_column(String)
    party_id: Mapped[str | None] = mapped_column(ForeignKey("parties.owner_id"), nullable=True)
    principal: Mapped[int | None] = mapped_column(BigInteger)
    outstanding: Mapped[int | None] = mapped_column(BigInteger)
    monthly_payment: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str | None] = mapped_column(Text)


class CicRecord(Base):
    __tablename__ = "cic_records"

    owner_id: Mapped[str] = mapped_column(String, primary_key=True)
    party_id: Mapped[str | None] = mapped_column(ForeignKey("parties.owner_id"), nullable=True)
    cic_group: Mapped[int | None] = mapped_column(Integer)
    history_note: Mapped[str | None] = mapped_column(Text)


class Assumption(Base):
    __tablename__ = "assumptions"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    # value giữ TEXT — LAB cast float trong tool (credit.py: float(r[1]))
    value: Mapped[str | None] = mapped_column(Text)


class Business(Base):
    # D-28b: seed THẬT (5 rows) từ S1 để cust_search/cust_get/credit_assess(DN) chạy đúng
    # thay vì db_error mọi call — credit-pack query businesses vô điều kiện. Cột khớp SQLite LAB.
    __tablename__ = "businesses"

    id: Mapped[str] = mapped_column(String, ForeignKey("parties.owner_id"), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    sector: Mapped[str | None] = mapped_column(Text)
    annual_revenue: Mapped[int | None] = mapped_column(BigInteger)
    equity: Mapped[int | None] = mapped_column(BigInteger)
    years_operating: Mapped[int | None] = mapped_column(Integer)
    tax_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)


class Collateral(Base):
    # D-28b: seed THẬT (7 rows) — credit_assess(collateral_id) + cust_get trả tài sản.
    __tablename__ = "collaterals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str | None] = mapped_column(String)
    party_id: Mapped[str | None] = mapped_column(ForeignKey("parties.owner_id"), nullable=True)
    type: Mapped[str | None] = mapped_column(Text)
    appraised_value: Mapped[int | None] = mapped_column(BigInteger)
    docs_status: Mapped[str | None] = mapped_column(Text)


# ── Legal tables (T2-2 — mount legal thật; cột khớp SQLite LAB) ──────────────
# PK tổng hợp (không có id đơn) — dùng đủ cột phân biệt làm composite PK.
class LegalRequirement(Base):
    __tablename__ = "legal_requirements"

    loan_type: Mapped[str] = mapped_column(Text, primary_key=True)
    doc_code: Mapped[str] = mapped_column(Text, primary_key=True)
    doc_name: Mapped[str | None] = mapped_column(Text)
    mandatory: Mapped[int | None] = mapped_column(Integer)


class OwnerDocument(Base):
    __tablename__ = "owner_documents"

    owner_id: Mapped[str] = mapped_column(String, primary_key=True)
    party_id: Mapped[str | None] = mapped_column(ForeignKey("parties.owner_id"), nullable=True)
    doc_code: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str | None] = mapped_column(Text)


class CollateralLegal(Base):
    __tablename__ = "collateral_legal"

    collateral_id: Mapped[str] = mapped_column(String, primary_key=True)
    dispute_status: Mapped[str | None] = mapped_column(Text)
    zoning_status: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)


class RestrictedPurpose(Base):
    __tablename__ = "restricted_purposes"

    purpose_code: Mapped[str] = mapped_column(Text, primary_key=True)
    purpose_name: Mapped[str | None] = mapped_column(Text)
    restriction: Mapped[str | None] = mapped_column(Text)
    legal_basis: Mapped[str | None] = mapped_column(Text)


class Assessment(Base):
    """Runtime legal verdict ledger; writes come from the certified LAB tool via the DB seam."""

    __tablename__ = "assessments"
    __table_args__ = (
        Index("ix_assessments_party_id", "party_id"),
        Index("ix_assessments_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        server_default=text(
            "COALESCE(NULLIF(current_setting('app.tenant_id', true), '')::uuid, "
            "'00000000-0000-0000-0000-000000000001'::uuid)"
        ),
    )
    owner_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    loan_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    loan_amount_vnd: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    lane: Mapped[str | None] = mapped_column(Text, nullable=True)
    criteria_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    party_id: Mapped[str | None] = mapped_column(ForeignKey("parties.owner_id", ondelete="SET NULL"), nullable=True)


# ---------------------------------------------------------------------------
# Vận hành tối thiểu (render + audit — spec §10, đủ cột cho T1-3 persist)
# ---------------------------------------------------------------------------


class User(Base):
    # SPEC §10 — 2 account seed: user(RM) / admin(quản lý·compliance) (D-19).
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_tenant_username", "tenant_id", "username"),)

    # server_default gen_random_uuid() → INSERT raw (psycopg2) tự có id (app default không áp raw).
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )
    username: Mapped[str] = mapped_column(String, unique=True)
    pass_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text)  # 'user' | 'admin'
    owner_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    party_id: Mapped[str | None] = mapped_column(ForeignKey("parties.owner_id"), nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_sub: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_tenant_created", "tenant_id", "created_at"),
        Index("ix_conversations_tenant_group_created", "tenant_id", "group_id", "created_at"),
    )

    # server_default (D-28c): orchestrator/T1-3 INSERT raw (psycopg2) → id tự sinh ở DB.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversation_groups.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    sdk_session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_tenant_ts", "tenant_id", "ts"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )
    # conv_id vẫn là định danh xuyên tầng; conversation_id là FK dual-write trong cửa sổ D-76.
    conv_id: Mapped[str] = mapped_column(Text)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    sender: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Approval(Base):
    # SPEC §10 §4.4 — phanh (T3-1). Phiếu chờ duyệt: 1 mặt với card approval. status vòng đời
    # pending→approved|rejected→used. Key (conv_id, action, payload_hash) khớp phiếu — lookup
    # LUÔN lọc conv_id (phiếu ca A không mở ca B). id/conv_id/task_id pattern D-28c/D-31.
    __tablename__ = "approvals"
    __table_args__ = (
        # lookup key wrapper gated (conv_id, action, payload_hash) — 4 bước phanh
        Index("ix_approvals_key", "conv_id", "action", "payload_hash"),
        Index("ix_approvals_tenant_status_created", "tenant_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )
    conv_id: Mapped[str] = mapped_column(Text, index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
    payload_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")  # pending|approved|rejected|used|exec_failed
    decided_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    receipt: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # T4-0 loop-bound: số lần guard-B re-dispatch ops#2 claim phiếu (chống task-storm khi fail bền).
    exec_attempts: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    # S18: snapshot phản-thực tại LÚC TẠO phiếu, tách khỏi payload/hash để config/assessment đổi
    # sau đó không viết lại lịch sử nghiệp vụ hoặc đổi danh tính hành động.
    system_assessment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    system_lane: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class ShadowReview(Base):
    """S18 ledger append-only: khuyến nghị hệ thống lúc pending đối chiếu quyết định người."""

    __tablename__ = "shadow_reviews"
    __table_args__ = (
        Index("ix_shadow_reviews_decided_at", "decided_at"),
        Index("ix_shadow_reviews_tenant_decided", "tenant_id", "decided_at"),
    )

    # FK được tạo NOT VALID để giữ 4 row legacy mồ côi; write mới vẫn bị DB chặn.
    approval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approvals.id", name="fk_shadow_reviews_approval"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )
    conv_id: Mapped[str] = mapped_column(Text)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    system_lane: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_recommendation: Mapped[str] = mapped_column(Text)
    human_decision: Mapped[str] = mapped_column(Text)
    human_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class Card(Base):
    # SPEC §10 — canvas reload. id vỏ-inject (server_default D-28c); card CHỈ từ present-tool (N5).
    # conv_id text (D-31 pattern). task_id null OK (main gọi present ngoài sub task).
    __tablename__ = "cards"
    __table_args__ = (Index("ix_cards_tenant_conv_ts", "tenant_id", "conv_id", "ts"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )
    conv_id: Mapped[str] = mapped_column(Text)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    type: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSONB)
    ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class ToolCall(Base):
    # T4-1 audit APPEND-ONLY (SPEC §10) — nền trace/Control Tower/F1 + cost meter. id VỎ-inject
    # (server_default D-28c §15). task_id null OK (main gọi tool ngoài sub). conv_id filter theo ca.
    # KHÔNG update/delete (bất biến — audit). output/cost best-effort (null nếu chưa bắt được).
    __tablename__ = "tool_calls"
    __table_args__ = (
        Index("ix_tool_calls_task_ts", "task_id", "ts"),
        Index("ix_tool_calls_conv", "conv_id"),
        Index("ix_tool_calls_tenant_ts", "tenant_id", "ts"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    conv_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    actor: Mapped[str] = mapped_column(Text)  # role (sub) | 'main'
    tool: Mapped[str] = mapped_column(Text)
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cost: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_tenant_ended", "tenant_id", "ended_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )
    conv_id: Mapped[str] = mapped_column(Text)  # định danh legacy/API; conversation_id là FK dual-write
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    role: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    cost: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cache_create_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    lease_owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
