from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f7e1d92b40"
down_revision: Union[str, Sequence[str], None] = "f2c8d6b41a70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

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

    op.drop_column("customers", "segment")
    op.drop_table("products")
