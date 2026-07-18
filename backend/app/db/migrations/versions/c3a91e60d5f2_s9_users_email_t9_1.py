"""s9 users.email T9-1 (register khách mới — D-57)

Revision ID: c3a91e60d5f2
Revises: b2e8d4f16a70
Create Date: 2026-07-18 20:30:00.000000

Cột email ADDITIVE cho POST /api/auth/register (khách mới đăng ký → nhận mail duyệt T9-2).
Nullable (account seed cũ user/admin/c001/b001/c019 không có email — không phá). Migration MỚI
nối tiếp (nguyên tắc: migration đã apply = bất biến, không sửa file cũ).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3a91e60d5f2"
down_revision: Union[str, Sequence[str], None] = "b2e8d4f16a70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade — users.email ADDITIVE (nullable)."""
    op.add_column("users", sa.Column("email", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade — drop email (đảo được)."""
    op.drop_column("users", "email")
