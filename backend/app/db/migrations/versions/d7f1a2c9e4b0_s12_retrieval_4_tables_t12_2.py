"""s12 retrieval 4 bảng T12-2 (wiki_pages/wiki_links/interaction_notes/party_relations)

Revision ID: d7f1a2c9e4b0
Revises: c4d9a1e57b23
Create Date: 2026-07-19 08:30:00.000000

4 tầng retrieval (D-63/D-65 — SPEC §14 vector lật hẹp CHỈ interaction_notes). DDL chuyển từ LAB
seed_retrieval.py sang PG idiom: AUTOINCREMENT→INTEGER PK (transfer id THẬT từ world, read-only
runtime — không cần SERIAL), BLOB→bytea (embedding float32[768], memoryview→bytes ở PGConnAdapter).
Migration MỚI nối head (bất biến — không sửa file đã apply). Reversible: downgrade drop 4 bảng.
assumptions(related_group_cap_pct) + loan L901 = seed VALUES (seed_from_lab), KHÔNG phải DDL.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7f1a2c9e4b0"
down_revision: Union[str, Sequence[str], None] = "c4d9a1e57b23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Tạo 4 bảng retrieval. Cột KHỚP LAB seed_retrieval.DDL (tên + nghĩa) để seed transfer positional."""
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
        sa.Column("so_hieu", sa.Text()),  # số hiệu QPPL thật (null cho trang gia-thuyet-lab)
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
        # note_id transfer THẬT từ world (citation ổn định) — INTEGER PK, KHÔNG SERIAL (read-only runtime)
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
        sa.Column("pct", sa.Float()),  # % sở hữu nếu owns
        sa.PrimaryKeyConstraint("from_id", "to_id", "relation"),
    )


def downgrade() -> None:
    """Drop 4 bảng (đảo được — D-65 'từng mục đảo được bằng 1 commit')."""
    op.drop_table("party_relations")
    op.drop_index("ix_interaction_notes_owner_id", table_name="interaction_notes")
    op.drop_table("interaction_notes")
    op.drop_table("wiki_links")
    op.drop_table("wiki_pages")
