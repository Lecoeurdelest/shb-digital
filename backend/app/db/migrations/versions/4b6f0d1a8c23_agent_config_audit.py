"""append-only audit for administrator prompt configuration

Revision ID: 4b6f0d1a8c23
Revises: 7d77c4a9e120
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "4b6f0d1a8c23"
down_revision: str | Sequence[str] | None = "7d77c4a9e120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_config_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("prompt_key", sa.Text(), nullable=False),
        sa.Column("environment", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("action IN ('version_created','activated')", name="ck_agent_config_events_action"),
    )
    op.create_index("ix_agent_config_events_prompt_created", "agent_config_events", ["prompt_key", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_config_events_prompt_created", table_name="agent_config_events")
    op.drop_table("agent_config_events")
