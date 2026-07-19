"""s12 products table + customers.segment (T12-5 FAIL B fix — Products toolpack thiếu bảng/cột)

Revision ID: a3f7e1d92b40
Revises: f2c8d6b41a70
Create Date: 2026-07-19 11:00:00.000000

FAIL B (tester T12-5): product_list → 'relation products does not exist'; product_suggest →
'column customers.segment does not exist'. World-swap T12-2 TABLES list SÓT bảng products (catalog
LAB) + customers LAB có cột `segment` (mass|vip|staff) mà migration cũ thiếu. DDL từ LAB shb-132.db.
Reversible: drop products + drop segment. Seed VALUES = seed_from_lab (extend TABLES).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f7e1d92b40"
down_revision: Union[str, Sequence[str], None] = "f2c8d6b41a70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """+products (catalog gói vay) + customers.segment (ADDITIVE nullable)."""
    op.create_table(
        "products",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text()),
        sa.Column("loan_type", sa.Text()),
        sa.Column("rate_annual", sa.Float()),
        sa.Column("term_max_months", sa.Integer()),
        sa.Column("amount_min_vnd", sa.BigInteger()),
        sa.Column("amount_max_vnd", sa.BigInteger()),
        sa.Column("fee_pct", sa.Float()),
        sa.Column("income_min_vnd", sa.BigInteger()),
        sa.Column("cic_max_group", sa.Integer()),
        sa.Column("segment", sa.Text()),  # mass|vip|staff|null
        sa.Column("status", sa.Text()),
        sa.Column("note", sa.Text()),
    )
    op.add_column("customers", sa.Column("segment", sa.Text(), nullable=True))  # mass|vip|staff


def downgrade() -> None:
    """Drop products + customers.segment (đảo được)."""
    op.drop_column("customers", "segment")
    op.drop_table("products")
