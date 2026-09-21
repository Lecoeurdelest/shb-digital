from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2e8d4f16a70"
down_revision: Union[str, Sequence[str], None] = "a1f7c2e93b04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.add_column("customers", sa.Column("id_number", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("businesses", sa.Column("tax_code", sa.Text(), nullable=True))
    op.add_column("businesses", sa.Column("address", sa.Text(), nullable=True))


def downgrade() -> None:

    op.drop_column("businesses", "address")
    op.drop_column("businesses", "tax_code")
    op.drop_column("customers", "address")
    op.drop_column("customers", "id_number")
