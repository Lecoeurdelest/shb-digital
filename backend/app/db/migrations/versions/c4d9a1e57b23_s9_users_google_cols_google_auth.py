"""s9 users google cols — email + google_sub, pass_hash nullable (Google OAuth, persona KHÁCH D-56)

Additive: 2 cột nullable + unique index; pass_hash thả NOT NULL (account Google-only không có
mật khẩu — authenticate coi NULL như sai mật khẩu, không 500). Downgrade thuận: drop cột +
siết lại NOT NULL sau khi xoá row google-only (pass_hash NULL).

Revision ID: c4d9a1e57b23
Revises: b2e8d4f16a70
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d9a1e57b23"
down_revision: Union[str, Sequence[str], None] = "b2e8d4f16a70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("google_sub", sa.Text(), nullable=True))
    # unique: 1 account Google = 1 user (PG cho phép nhiều NULL trong unique index)
    op.create_index("uq_users_google_sub", "users", ["google_sub"], unique=True)
    op.alter_column("users", "pass_hash", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    # row google-only (pass_hash NULL) phải xoá trước khi siết NOT NULL trở lại
    op.execute("DELETE FROM users WHERE pass_hash IS NULL")
    op.alter_column("users", "pass_hash", existing_type=sa.Text(), nullable=False)
    op.drop_index("uq_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")
    op.drop_column("users", "email")
