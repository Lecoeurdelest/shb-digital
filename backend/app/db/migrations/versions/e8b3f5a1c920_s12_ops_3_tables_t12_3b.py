"""s12 ops 3 bảng T12-3b (applications/disbursements/procedure_steps)

Revision ID: e8b3f5a1c920
Revises: d7f1a2c9e4b0
Create Date: 2026-07-19 09:30:00.000000

3 bảng schema RIÊNG của operations pipeline (LAB ops_disburse thao tác — application_id/amount_vnd,
KHÁC loans/loan_id đường disburse demo). DDL từ LAB shb-132.db. PG idiom: TEXT PK, INTEGER amounts,
procedure_steps composite PK (application_id, step). Migration MỚI nối head (bất biến). Reversible.
Seed VALUES = seed_from_lab (extend TABLES). ops_disburse chạy dưới gated (T12-3b bridge tx-strip).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8b3f5a1c920"
down_revision: Union[str, Sequence[str], None] = "d7f1a2c9e4b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """3 bảng ops pipeline. Cột KHỚP LAB shb-132.db (tên + nghĩa) cho seed transfer positional."""
    op.create_table(
        "applications",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text()),
        sa.Column("product_id", sa.Text()),
        sa.Column("loan_amount_vnd", sa.BigInteger()),
        sa.Column("loan_type", sa.Text()),
        sa.Column("collateral_id", sa.Text()),
        sa.Column("status", sa.Text()),
        sa.Column("credit_ok", sa.Integer()),  # 0/1 (SQLite bool → int)
        sa.Column("legal_ok", sa.Integer()),
        sa.Column("human_approval", sa.Text()),  # pending|approved|denied
        sa.Column("approval_ref", sa.Text()),
        sa.Column("created_at", sa.Text()),
    )
    op.create_index("ix_applications_owner_id", "applications", ["owner_id"])
    op.create_table(
        "disbursements",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("application_id", sa.Text()),
        sa.Column("amount_vnd", sa.BigInteger()),
        sa.Column("beneficiary", sa.Text()),
        sa.Column("status", sa.Text()),  # executed
        sa.Column("executed_at", sa.Text()),
        sa.Column("receipt_code", sa.Text()),
    )
    op.create_index("ix_disbursements_application_id", "disbursements", ["application_id"])
    op.create_table(
        "procedure_steps",
        sa.Column("application_id", sa.Text(), nullable=False),
        sa.Column("step", sa.Text(), nullable=False),
        sa.Column("status", sa.Text()),
        sa.Column("done_at", sa.Text()),
        sa.PrimaryKeyConstraint("application_id", "step"),
    )


def downgrade() -> None:
    """Drop 3 bảng (đảo được)."""
    op.drop_index("ix_disbursements_application_id", table_name="disbursements")
    op.drop_table("disbursements")
    op.drop_index("ix_applications_owner_id", table_name="applications")
    op.drop_table("applications")
    op.drop_table("procedure_steps")
