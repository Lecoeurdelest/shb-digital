"""versioned prompt catalog with environment bindings

Revision ID: 2f9c1a6e4d33
Revises: 1e8b0f5d3c22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2f9c1a6e4d33"
down_revision: str | Sequence[str] | None = "1e8b0f5d3c22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_definitions",
        sa.Column("prompt_key", sa.Text(), primary_key=True),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("variables", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("default_file", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("jsonb_typeof(variables)='array'", name="ck_prompt_definitions_variables"),
    )
    op.create_table(
        "prompt_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("prompt_key", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", sa.Text(), nullable=False, server_default="bootstrap"),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["prompt_key"], ["prompt_definitions.prompt_key"], ondelete="RESTRICT"),
        sa.UniqueConstraint("prompt_key", "version", name="uq_prompt_versions_number"),
        sa.UniqueConstraint("prompt_key", "checksum", name="uq_prompt_versions_checksum"),
        sa.UniqueConstraint("prompt_key", "id", name="uq_prompt_versions_key_id"),
        sa.CheckConstraint("version > 0", name="ck_prompt_versions_number"),
        sa.CheckConstraint("length(content) > 0", name="ck_prompt_versions_content"),
    )
    op.create_table(
        "prompt_bindings",
        sa.Column("prompt_key", sa.Text(), nullable=False),
        sa.Column("environment", sa.Text(), nullable=False, server_default="default"),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activated_by", sa.Text(), nullable=False, server_default="bootstrap"),
        sa.Column(
            "activated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["prompt_key", "version_id"],
            ["prompt_versions.prompt_key", "prompt_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("prompt_key", "environment"),
        sa.CheckConstraint("length(environment) > 0", name="ck_prompt_bindings_environment"),
    )
    op.create_index("ix_prompt_versions_created", "prompt_versions", ["prompt_key", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_prompt_versions_created", table_name="prompt_versions")
    op.drop_table("prompt_bindings")
    op.drop_table("prompt_versions")
    op.drop_table("prompt_definitions")
