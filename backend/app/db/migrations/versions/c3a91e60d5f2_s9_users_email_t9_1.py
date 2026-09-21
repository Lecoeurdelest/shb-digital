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

    op.drop_column("users", "email")
