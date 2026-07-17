"""s1 conv_id text drop fk D-31

Revision ID: 4b282d74ff31
Revises: 448101c1915d
Create Date: 2026-07-18 03:24:48.061871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b282d74ff31'
down_revision: Union[str, Sequence[str], None] = '448101c1915d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """D-31: conv_id (tasks/messages) → TEXT + drop FK.

    conv_id = định danh xuyên suốt (registry key + SDK cwd + SSE topic) dạng string; ràng buộc
    mềm để orchestrator/spine dùng conv_id tự do. uuid PK conversations giữ nguyên.
    """
    op.drop_constraint("tasks_conv_id_fkey", "tasks", type_="foreignkey")
    op.drop_constraint("messages_conv_id_fkey", "messages", type_="foreignkey")
    op.alter_column(
        "tasks", "conv_id", type_=sa.Text(), postgresql_using="conv_id::text"
    )
    op.alter_column(
        "messages", "conv_id", type_=sa.Text(), postgresql_using="conv_id::text"
    )


def downgrade() -> None:
    """Khôi phục uuid + FK. conv_id là text tự do (D-31) → rows có conv_id KHÔNG-uuid (spine/test,
    không có conversation cha) không map ngược được → XOÁ trước khi convert (downgrade destructive,
    đúng bản chất: đảo bỏ tính năng conv_id-tự-do thì mất data phụ thuộc nó). Rows conv_id-uuid giữ."""
    _UUID_RE = "'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'"
    # (1) xoá rows conv_id KHÔNG-uuid (không convert được về uuid)
    op.execute(f"DELETE FROM tasks WHERE conv_id !~ {_UUID_RE}")
    op.execute(f"DELETE FROM messages WHERE conv_id !~ {_UUID_RE}")
    # (2) convert text → uuid (giờ mọi row còn lại đều uuid hợp lệ)
    op.alter_column("tasks", "conv_id", type_=sa.UUID(), postgresql_using="conv_id::uuid")
    op.alter_column("messages", "conv_id", type_=sa.UUID(), postgresql_using="conv_id::uuid")
    # (3) xoá rows conv_id uuid nhưng KHÔNG có conversation cha (orphan — FK sẽ chặn); destructive
    op.execute("DELETE FROM tasks WHERE conv_id NOT IN (SELECT id FROM conversations)")
    op.execute("DELETE FROM messages WHERE conv_id NOT IN (SELECT id FROM conversations)")
    # (4) re-create FK (mọi row còn lại đều có cha)
    op.create_foreign_key("tasks_conv_id_fkey", "tasks", "conversations", ["conv_id"], ["id"])
    op.create_foreign_key("messages_conv_id_fkey", "messages", "conversations", ["conv_id"], ["id"])
