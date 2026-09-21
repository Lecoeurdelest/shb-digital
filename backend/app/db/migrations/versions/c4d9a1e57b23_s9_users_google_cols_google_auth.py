from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d9a1e57b23"
down_revision: Union[str, Sequence[str], None] = "c3a91e60d5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.add_column("users", sa.Column("google_sub", sa.Text(), nullable=True))

    op.create_index("uq_users_google_sub", "users", ["google_sub"], unique=True)
    op.alter_column("users", "pass_hash", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:

    op.execute("DELETE FROM users WHERE pass_hash IS NULL")
    op.alter_column("users", "pass_hash", existing_type=sa.Text(), nullable=False)
    op.drop_index("uq_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")
