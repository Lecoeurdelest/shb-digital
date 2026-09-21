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
    ("model", sa.Text()),
]


def upgrade() -> None:

    for name, col_type in _COLS:
        op.add_column("tasks", sa.Column(name, col_type, nullable=True))


def downgrade() -> None:

    for name, _ in reversed(_COLS):
        op.drop_column("tasks", name)
