"""s16 tasks instrument T16-1 (+6 cột token/duration/model — đọc ResultMessage.usage đang bị vứt)

Revision ID: f2c8d6b41a70
Revises: e8b3f5a1c920
Create Date: 2026-07-19 10:30:00.000000

6 cột nullable trên `tasks` để lưu chỉ số THẬT từ ResultMessage (SDK) — hiện bị vứt ở
main_session/sub_runner (`elif ResultMessage: pass`). Nguồn cho stats cost T16-2.
Mapping key SDK (đã capture THẬT, tránh silent-null — advisor): usage.input_tokens/output_tokens/
cache_read_input_tokens/cache_creation_input_tokens (snake_case top-level); model = KEY của
model_usage (KHÔNG có scalar msg.model). Reversible: drop 6 cột. `tasks.cost` (jsonb) sẵn có nhưng
KHÔNG ai ghi (vestigial) — T16-1 dùng cột số riêng cho query-able (T16-2 SUM/AVG), không nhét jsonb.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2c8d6b41a70"
down_revision: Union[str, Sequence[str], None] = "e8b3f5a1c920"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLS = [
    ("input_tokens", sa.BigInteger()),
    ("output_tokens", sa.BigInteger()),
    ("cache_read_tokens", sa.BigInteger()),
    ("cache_create_tokens", sa.BigInteger()),
    ("duration_ms", sa.BigInteger()),
    ("model", sa.Text()),  # model THẬT đã chạy (key của model_usage)
]


def upgrade() -> None:
    """+6 cột nullable (ADDITIVE — task cũ NULL, không phá)."""
    for name, col_type in _COLS:
        op.add_column("tasks", sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    """Drop 6 cột (đảo được)."""
    for name, _ in reversed(_COLS):
        op.drop_column("tasks", name)
