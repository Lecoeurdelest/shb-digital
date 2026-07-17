"""s1 server_default uuid ops tables D-28c

Revision ID: 448101c1915d
Revises: 1aef6233c6ac
Create Date: 2026-07-18 03:21:33.228050

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '448101c1915d'
down_revision: Union[str, Sequence[str], None] = '1aef6233c6ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """D-28c: server_default gen_random_uuid() cho id 3 bảng ops.

    Orchestrator/T1-3 INSERT raw (psycopg2) → id NULL → NotNullViolation nếu chỉ có app-default
    ORM. Thêm DB-level default để INSERT raw an toàn. (autogenerate KHÔNG detect server_default
    trên bảng đã tồn tại → viết tay alter_column.)
    """
    for table in ("conversations", "messages", "tasks"):
        op.alter_column(table, "id", server_default=sa.text("gen_random_uuid()"))


def downgrade() -> None:
    """Downgrade schema."""
    for table in ("conversations", "messages", "tasks"):
        op.alter_column(table, "id", server_default=None)
