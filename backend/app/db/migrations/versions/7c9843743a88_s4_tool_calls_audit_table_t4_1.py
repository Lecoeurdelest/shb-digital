"""s4 tool_calls audit table T4-1

Revision ID: 7c9843743a88
Revises: f3eb4c3becb1
Create Date: 2026-07-18 10:24:35.421740

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7c9843743a88'
down_revision: Union[str, Sequence[str], None] = 'f3eb4c3becb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    T4-1 audit APPEND-ONLY (SPEC §10): mọi tool-call của sub/main → 1 row bất biến (nền trace/
    Control Tower/F1 + cost meter). id server_default uuid (D-28c VỎ-inject §15). task_id nullable
    (main gọi tool ngoài sub → null). output/cost nullable (bắt best-effort). Index (task_id, ts)
    cho trace timeline + GET /api/audit filter.
    """
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=True),
        sa.Column("conv_id", sa.Text(), nullable=True),  # filter theo ca (main tool task_id null)
        sa.Column("ts", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),  # role (sub) | 'main'
        sa.Column("tool", sa.Text(), nullable=False),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cost", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_calls_task_ts", "tool_calls", ["task_id", "ts"], unique=False)
    op.create_index("ix_tool_calls_conv", "tool_calls", ["conv_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_tool_calls_conv", table_name="tool_calls")
    op.drop_index("ix_tool_calls_task_ts", table_name="tool_calls")
    op.drop_table("tool_calls")
