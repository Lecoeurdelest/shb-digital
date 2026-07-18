"""s4 approvals exec_attempts loop-bound T4-0

Revision ID: f3eb4c3becb1
Revises: 8e8edc5b9187
Create Date: 2026-07-18 09:57:43.145465

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3eb4c3becb1'
down_revision: Union[str, Sequence[str], None] = '8e8edc5b9187'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    T4-0 loop-bound: cột exec_attempts đếm số lần guard-B re-dispatch ops#2 claim phiếu approved.
    Trần MAX_EXEC_ATTEMPTS chặn task-storm khi ops#2 fail BỀN (loan lỗi → rollback → grant treo).
    DEFAULT 0 (server_default) → row cũ + INSERT không set đều 0, không vỡ code hiện tại.
    """
    op.add_column(
        "approvals",
        sa.Column("exec_attempts", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("approvals", "exec_attempts")
