"""D-77 external case mapping and append-only integration inbox

Revision ID: 7d77c4a9e120
Revises: 2f9c1a6e4d33
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7d77c4a9e120"
down_revision: str | Sequence[str] | None = "2f9c1a6e4d33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CASE_STATUSES = (
    "received",
    "missing_information",
    "ready_for_preassessment",
    "preassessment_in_progress",
    "needs_specialist",
    "ready_for_handover",
    "cancelled",
)


def upgrade() -> None:
    op.create_table(
        "external_case_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("external_case_id", sa.Text(), nullable=False),
        # Soft reference có chủ đích: applications demo/raw không phải master của connector LOS.
        sa.Column("internal_application_id", sa.Text(), nullable=True),
        sa.Column("party_reference", sa.Text(), nullable=True),
        sa.Column("assigned_rm_subject", sa.Text(), nullable=True),
        sa.Column("product_code", sa.Text(), nullable=True),
        sa.Column("loan_amount_vnd", sa.BigInteger(), nullable=True),
        sa.Column("document_refs", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("missing_fields", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_version", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("case_status", sa.Text(), nullable=False),
        sa.Column("data_as_of", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("synced_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("source_system", "external_case_id", name="uq_external_case_source_identity"),
        sa.UniqueConstraint("conversation_id", name="uq_external_case_conversation"),
        sa.CheckConstraint("source_version > 0", name="ck_external_case_source_version"),
        sa.CheckConstraint("loan_amount_vnd IS NULL OR loan_amount_vnd >= 0", name="ck_external_case_amount"),
        sa.CheckConstraint("jsonb_typeof(document_refs)='array'", name="ck_external_case_document_refs"),
        sa.CheckConstraint("jsonb_typeof(missing_fields)='array'", name="ck_external_case_missing_fields"),
        sa.CheckConstraint(f"case_status IN { _CASE_STATUSES!r}", name="ck_external_case_status"),
    )
    op.create_index("ix_external_case_status_synced", "external_case_links", ["case_status", "synced_at"])
    op.create_index("ix_external_case_source_synced", "external_case_links", ["source_system", "synced_at"])

    op.create_table(
        "integration_inbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("external_case_id", sa.Text(), nullable=False),
        sa.Column("source_version", sa.BigInteger(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("receipt", postgresql.JSONB(), nullable=False),
        sa.Column("received_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("source_system", "event_id", name="uq_integration_inbox_source_event"),
        sa.CheckConstraint("schema_version > 0", name="ck_integration_inbox_schema_version"),
        sa.CheckConstraint("source_version > 0", name="ck_integration_inbox_source_version"),
        sa.CheckConstraint("jsonb_typeof(payload)='object'", name="ck_integration_inbox_payload"),
        sa.CheckConstraint("jsonb_typeof(receipt)='object'", name="ck_integration_inbox_receipt"),
    )
    op.create_index("ix_integration_inbox_case_received", "integration_inbox", ["source_system", "external_case_id", "received_at"])


def downgrade() -> None:
    op.drop_index("ix_integration_inbox_case_received", table_name="integration_inbox")
    op.drop_table("integration_inbox")
    op.drop_index("ix_external_case_source_synced", table_name="external_case_links")
    op.drop_index("ix_external_case_status_synced", table_name="external_case_links")
    op.drop_table("external_case_links")
