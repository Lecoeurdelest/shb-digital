"""s9 users google cols — google_sub + pass_hash nullable (Google OAuth, persona KHÁCH D-56)

Additive: google_sub nullable + unique index; pass_hash thả NOT NULL (account Google-only không có
mật khẩu — authenticate coi NULL như sai mật khẩu, không 500). Downgrade thuận: drop cột +
siết lại NOT NULL sau khi xoá row google-only (pass_hash NULL).

LANDING MERGE re-parent (đất backend): down_revision đổi b2e8d4f16a70 → c3a91e60d5f2 (email T9-1,
head hiện hành) để hết 2-head fork (upgrade head nổ container deploy). Vì c3a91e60d5f2 ĐÃ thêm cột
`email` → BỎ add_column email ở đây (tránh DuplicateColumn); chỉ giữ google_sub + pass_hash nullable.

Revision ID: c4d9a1e57b23
Revises: c3a91e60d5f2
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d9a1e57b23"
down_revision: Union[str, Sequence[str], None] = "c3a91e60d5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # email ĐÃ có từ c3a91e60d5f2 (T9-1) — KHÔNG add lại (re-parent landing merge). Chỉ google_sub.
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
    # email KHÔNG drop ở đây — thuộc c3a91e60d5f2 (T9-1), downgrade của nó lo.
