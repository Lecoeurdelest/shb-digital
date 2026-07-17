"""s1 add businesses collaterals D-28b spine

Revision ID: 53a8d21ecbe9
Revises: 24573677068a
Create Date: 2026-07-18 02:59:51.802096

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '53a8d21ecbe9'
down_revision: Union[str, Sequence[str], None] = '24573677068a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — businesses + collaterals (D-28b: spine-completeness cho credit-pack).

    credit-pack (cust_search/cust_get/credit_assess) query 2 bảng này VÔ ĐIỀU KIỆN.
    Thiếu bảng → psycopg2 UndefinedTable → db_error mọi call. Tạo + seed thật (5/7 rows) để
    3/4 tool chạy đúng, khớp ca demo 'DN X vay 5 tỷ'. Cột KHỚP SQLite LAB seed.
    """
    op.create_table(
        "businesses",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("sector", sa.Text(), nullable=True),
        sa.Column("annual_revenue", sa.BigInteger(), nullable=True),
        sa.Column("equity", sa.BigInteger(), nullable=True),
        sa.Column("years_operating", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "collaterals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=True),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("appraised_value", sa.BigInteger(), nullable=True),
        sa.Column("docs_status", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("collaterals")
    op.drop_table("businesses")
