"""s8 users owner_id customer persona D-56

Revision ID: 51dc39084c9b
Revises: 4e736cf0daae
Create Date: 2026-07-18 16:17:01.554240

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "51dc39084c9b"
down_revision: Union[str, Sequence[str], None] = "4e736cf0daae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.add_column("users", sa.Column("owner_id", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "owner_id")
