"""s18 approval snapshots + append-only shadow review ledger

Revision ID: c8d4e6f1a290
Revises: a3f7e1d92b40
Create Date: 2026-08-24 10:00:00.000000

D-72: snapshot khuyến nghị lúc tạo phiếu, ngoài payload/hash nghiệp vụ. Khi người quyết,
shadow_reviews được ghi cùng transaction với approvals để không có decision thiếu audit.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c8d4e6f1a290"
down_revision: Union[str, Sequence[str], None] = "a3f7e1d92b40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Thêm snapshot nội bộ trên phiếu + ledger đối soát một-mẫu-mỗi-phiếu."""
    op.add_column("approvals", sa.Column("system_assessment_id", sa.Integer(), nullable=True))
    op.add_column("approvals", sa.Column("system_lane", sa.Text(), nullable=True))
    op.add_column("approvals", sa.Column("system_recommendation", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_approvals_system_lane",
        "approvals",
        "system_lane IS NULL OR system_lane IN ('green','yellow','red')",
    )
    op.create_check_constraint(
        "ck_approvals_system_recommendation",
        "approvals",
        "system_recommendation IS NULL OR "
        "system_recommendation IN ('auto-eligible','human-review','reject-recommended')",
    )

    op.create_table(
        "shadow_reviews",
        # PK vừa là khoá idempotency: double-click không thể tạo mẫu thứ hai cho cùng phiếu.
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conv_id", sa.Text(), nullable=False),
        sa.Column("system_lane", sa.Text(), nullable=True),
        sa.Column("system_recommendation", sa.Text(), nullable=False),
        sa.Column("human_decision", sa.Text(), nullable=False),
        sa.Column("human_reason", sa.Text(), nullable=True),
        sa.Column("decided_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("match", sa.Boolean(), nullable=True),
        sa.CheckConstraint(
            "system_lane IS NULL OR system_lane IN ('green','yellow','red')",
            name="ck_shadow_reviews_system_lane",
        ),
        sa.CheckConstraint(
            "system_recommendation IN ('auto-eligible','human-review','reject-recommended')",
            name="ck_shadow_reviews_system_recommendation",
        ),
        sa.CheckConstraint(
            "human_decision IN ('approved','rejected')",
            name="ck_shadow_reviews_human_decision",
        ),
        sa.PrimaryKeyConstraint("approval_id"),
    )
    op.create_index("ix_shadow_reviews_decided_at", "shadow_reviews", ["decided_at"], unique=False)


def downgrade() -> None:
    """Đảo sạch ledger rồi bỏ snapshot khỏi approvals."""
    op.drop_index("ix_shadow_reviews_decided_at", table_name="shadow_reviews")
    op.drop_table("shadow_reviews")
    op.drop_constraint("ck_approvals_system_recommendation", "approvals", type_="check")
    op.drop_constraint("ck_approvals_system_lane", "approvals", type_="check")
    op.drop_column("approvals", "system_recommendation")
    op.drop_column("approvals", "system_lane")
    op.drop_column("approvals", "system_assessment_id")
