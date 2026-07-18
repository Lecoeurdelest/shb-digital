"""s4 conversations provider model per-conv D-45b-c

Revision ID: 4e736cf0daae
Revises: 7c9843743a88
Create Date: 2026-07-18 12:07:30.435687

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e736cf0daae'
down_revision: Union[str, Sequence[str], None] = '7c9843743a88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    D-45b (c) per-conv provider/model: cột provider/model NULLABLE trên conversations. null →
    server-default SHB_PROVIDER (resolve lúc chạy) — :8000 cũ + conv cũ không vỡ. Resume-consistency:
    conv tạo provider X → mọi lượt đọc cột này chạy X.
    """
    op.add_column("conversations", sa.Column("provider", sa.Text(), nullable=True))
    op.add_column("conversations", sa.Column("model", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("conversations", "model")
    op.drop_column("conversations", "provider")
