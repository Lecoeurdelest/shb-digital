"""s1 conv_id text drop fk D-31

Revision ID: 4b282d74ff31
Revises: 448101c1915d
Create Date: 2026-07-18 03:24:48.061871

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4b282d74ff31"
down_revision: Union[str, Sequence[str], None] = "448101c1915d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.drop_constraint("tasks_conv_id_fkey", "tasks", type_="foreignkey")
    op.drop_constraint("messages_conv_id_fkey", "messages", type_="foreignkey")
    op.alter_column("tasks", "conv_id", type_=sa.Text(), postgresql_using="conv_id::text")
    op.alter_column("messages", "conv_id", type_=sa.Text(), postgresql_using="conv_id::text")


def downgrade() -> None:

    _UUID_RE = "'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'"

    op.execute(f"DELETE FROM tasks WHERE conv_id !~ {_UUID_RE}")
    op.execute(f"DELETE FROM messages WHERE conv_id !~ {_UUID_RE}")

    op.alter_column("tasks", "conv_id", type_=sa.UUID(), postgresql_using="conv_id::uuid")
    op.alter_column("messages", "conv_id", type_=sa.UUID(), postgresql_using="conv_id::uuid")

    op.execute("DELETE FROM tasks WHERE conv_id NOT IN (SELECT id FROM conversations)")
    op.execute("DELETE FROM messages WHERE conv_id NOT IN (SELECT id FROM conversations)")

    op.create_foreign_key("tasks_conv_id_fkey", "tasks", "conversations", ["conv_id"], ["id"])
    op.create_foreign_key("messages_conv_id_fkey", "messages", "conversations", ["conv_id"], ["id"])
