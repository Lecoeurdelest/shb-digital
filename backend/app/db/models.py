"""SQLAlchemy models — S1 scope: 9 tables (task T1-1).
Nghiệp vụ (cột khớp SQLite LAB, verify bằng PRAGMA khi copy seed — DECISIONS D-21):
    customers, loans, cic_records, assumptions
    + businesses, collaterals (D-28b — credit-pack query 2 bảng này vô điều kiện; seed thật
      5/7 rows để cust_search/cust_get/credit_assess(DN) chạy đúng thay vì db_error mọi call).
Vận hành tối thiểu (đủ cột cho T1-3 persist):
    conversations, messages, tasks
KHÔNG tạo cards/tool_calls/approvals ở S1 (fan-out sau — prove-spine-first; T1-1 Logic §A)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Nghiệp vụ (business data — cột khớp SQLite LAB seed/shb-132.db)
# ---------------------------------------------------------------------------


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str | None] = mapped_column(Text)
    age: Mapped[int | None] = mapped_column(Integer)
    occupation: Mapped[str | None] = mapped_column(Text)
    monthly_income: Mapped[int | None] = mapped_column(BigInteger)
    region: Mapped[str | None] = mapped_column(Text)


class Loan(Base):
    __tablename__ = "loans"

    loan_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str | None] = mapped_column(String)
    principal: Mapped[int | None] = mapped_column(BigInteger)
    outstanding: Mapped[int | None] = mapped_column(BigInteger)
    monthly_payment: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str | None] = mapped_column(Text)


class CicRecord(Base):
    __tablename__ = "cic_records"

    owner_id: Mapped[str] = mapped_column(String, primary_key=True)
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

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    sector: Mapped[str | None] = mapped_column(Text)
    annual_revenue: Mapped[int | None] = mapped_column(BigInteger)
    equity: Mapped[int | None] = mapped_column(BigInteger)
    years_operating: Mapped[int | None] = mapped_column(Integer)


class Collateral(Base):
    # D-28b: seed THẬT (7 rows) — credit_assess(collateral_id) + cust_get trả tài sản.
    __tablename__ = "collaterals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str | None] = mapped_column(String)
    type: Mapped[str | None] = mapped_column(Text)
    appraised_value: Mapped[int | None] = mapped_column(BigInteger)
    docs_status: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Vận hành tối thiểu (render + audit — spec §10, đủ cột cho T1-3 persist)
# ---------------------------------------------------------------------------


class User(Base):
    # SPEC §10 — 2 account seed: user(RM) / admin(quản lý·compliance) (D-19).
    __tablename__ = "users"

    # server_default gen_random_uuid() → INSERT raw (psycopg2) tự có id (app default không áp raw).
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String, unique=True)
    pass_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)  # 'user' | 'admin'


class Conversation(Base):
    __tablename__ = "conversations"

    # server_default (D-28c): orchestrator/T1-3 INSERT raw (psycopg2) → id tự sinh ở DB.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    user_id: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    sdk_session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    conv_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    sender: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    conv_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    role: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    cost: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
