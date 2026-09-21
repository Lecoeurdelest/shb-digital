from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7f1a2c9e4b0"
down_revision: Union[str, Sequence[str], None] = "c4d9a1e57b23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table(
        "wiki_pages",
        sa.Column("id", sa.Text(), primary_key=True),  # slug
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("topic", sa.Text()),
        sa.Column("tags", sa.Text()),
        sa.Column("legal_basis", sa.Text()),
        sa.Column("effective_from", sa.Text()),
        sa.Column("effective_to", sa.Text()),
        sa.Column("status", sa.Text(), server_default="active"),  # active|expired|replaced|amended
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_file", sa.Text()),
        sa.Column("so_hieu", sa.Text()),
        sa.Column("dieu", sa.Text()),
        sa.Column("amended_by", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("crawled_at", sa.Text()),
    )
    op.create_table(
        "wiki_links",
        sa.Column("from_page", sa.Text(), nullable=False),
        sa.Column("to_page", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("from_page", "to_page"),
    )
    op.create_table(
        "interaction_notes",
        sa.Column("note_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("ts", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),  # meet|call|email|branch
        sa.Column("rm", sa.Text(), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.LargeBinary()),  # bytea — float32[768] vietnamese-bi-encoder
    )
    op.create_index("ix_interaction_notes_owner_id", "interaction_notes", ["owner_id"])
    op.create_table(
        "party_relations",
        sa.Column("from_id", sa.Text(), nullable=False),
        sa.Column("to_id", sa.Text(), nullable=False),
        sa.Column("relation", sa.Text(), nullable=False),  # owns|chairman|guarantor|spouse
        sa.Column("pct", sa.Float()),
        sa.PrimaryKeyConstraint("from_id", "to_id", "relation"),
    )


def downgrade() -> None:

    op.drop_table("party_relations")
    op.drop_index("ix_interaction_notes_owner_id", table_name="interaction_notes")
    op.drop_table("interaction_notes")
    op.drop_table("wiki_links")
    op.drop_table("wiki_pages")
