"""s7 identity cols additive T7-1 (customers.id_number/address, businesses.tax_code/address)

Revision ID: b2e8d4f16a70
Revises: a1f7c2e93b04
Create Date: 2026-07-18 19:40:00.000000

4 cột nhân thân ADDITIVE cho trụ ①công an (SEED-REPORT §7): legal `_owner_identity`
đối chiếu bản CRM (customers/businesses) vs bản Bộ Công an (police_records) — cần
id_number/address (khách) + tax_code/address (DN). Thiếu 4 cột này → trụ police chết.
Nullable + additive → không phá data hiện có (idempotent trên DB đã seed cũ).
Nguồn schema: shb-132.db (READ-ONLY, D-08) — cột TEXT khớp bản LAB.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2e8d4f16a70"
down_revision: Union[str, Sequence[str], None] = "a1f7c2e93b04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade — 4 cột identity ADDITIVE (nullable, không phá data cũ)."""
    op.add_column("customers", sa.Column("id_number", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("businesses", sa.Column("tax_code", sa.Text(), nullable=True))
    op.add_column("businesses", sa.Column("address", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade — drop 4 cột (đảo được)."""
    op.drop_column("businesses", "address")
    op.drop_column("businesses", "tax_code")
    op.drop_column("customers", "address")
    op.drop_column("customers", "id_number")
