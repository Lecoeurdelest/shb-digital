"""S20 consent wording proof ledger, append-only at DB level

Revision ID: d4e8a1b7c203
Revises: 9f3a2b7c4d10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e8a1b7c203"
down_revision: str | Sequence[str] | None = "9f3a2b7c4d10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_ref", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("wording_version", sa.Text(), nullable=False),
        sa.Column("wording_checksum", sa.String(64), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("recorded_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("granted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "tenant_id",
            "source",
            "source_ref",
            "purpose",
            name="uq_consent_records_source_purpose",
        ),
        sa.CheckConstraint("subject_type IN ('user','external_party')", name="ck_consent_subject_type"),
        sa.CheckConstraint("btrim(subject_ref)<>''", name="ck_consent_subject_ref"),
        sa.CheckConstraint(
            "purpose='pre_pilot_shadow_preassessment'",
            name="ck_consent_purpose",
        ),
        sa.CheckConstraint("wording_version ~ '^v[1-9][0-9]*$'", name="ck_consent_wording_version"),
        sa.CheckConstraint("wording_checksum ~ '^[0-9a-f]{64}$'", name="ck_consent_wording_checksum"),
        sa.CheckConstraint(
            "(granted IS TRUE AND granted_at IS NOT NULL) OR (granted IS FALSE AND granted_at IS NULL)",
            name="ck_consent_granted_at",
        ),
        sa.CheckConstraint("btrim(actor)<>''", name="ck_consent_actor"),
        sa.CheckConstraint("source='customer_form'", name="ck_consent_source"),
        sa.CheckConstraint("btrim(source_ref)<>''", name="ck_consent_source_ref"),
    )
    op.create_index(
        "ix_consent_records_tenant_recorded",
        "consent_records",
        ["tenant_id", "recorded_at"],
    )
    op.execute(
        """
        CREATE FUNCTION shb_reject_consent_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'consent_records is append-only' USING ERRCODE='55000';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER trg_consent_records_append_only BEFORE UPDATE OR DELETE ON consent_records "
        "FOR EACH ROW EXECUTE FUNCTION shb_reject_consent_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_consent_records_append_only ON consent_records")
    op.execute("DROP FUNCTION shb_reject_consent_mutation()")
    op.drop_index("ix_consent_records_tenant_recorded", table_name="consent_records")
    op.drop_table("consent_records")
