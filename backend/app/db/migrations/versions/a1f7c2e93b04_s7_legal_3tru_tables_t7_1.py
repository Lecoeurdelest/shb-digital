"""s7 legal 3-trụ tables T7-1 (police_records, employment_records, assessments)

Revision ID: a1f7c2e93b04
Revises: 51dc39084c9b
Create Date: 2026-07-18 19:10:00.000000

3 bảng cho 3-trụ phê duyệt legal (mentor-1807): ①công an ②lương xác minh ③chốt lane.
Schema KHỚP nguồn LAB shb-132.db (READ-ONLY, D-08) — không bịa cột. police/employment
= read-only tra cứu (PK owner_id); assessments = sổ GHI của legal_classify_profile
(WRITE tool — id serial autoincrement khớp sqlite AUTOINCREMENT).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f7c2e93b04"
down_revision: Union[str, Sequence[str], None] = "51dc39084c9b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — 3 bảng legal 3-trụ."""
    # ── ①công an: nhân thân + tiền án (PK owner_id, read-only tra cứu) ──
    op.create_table(
        "police_records",
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("id_number", sa.Text(), nullable=True),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("criminal_status", sa.Text(), nullable=True),
        sa.Column("record_type", sa.Text(), nullable=True),
        sa.Column("record_year", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("owner_id"),
    )
    # ── ③lương xác minh: verified income vs kê khai (PK owner_id, read-only) ──
    op.create_table(
        "employment_records",
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("employer", sa.Text(), nullable=True),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("tenure_months", sa.Integer(), nullable=True),
        sa.Column("verified_income_vnd", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("owner_id"),
    )
    # ── ⭐sổ chốt lane: legal_classify_profile GHI (WRITE) — id serial autoincrement ──
    op.create_table(
        "assessments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=True),
        sa.Column("loan_type", sa.Text(), nullable=True),
        sa.Column("loan_amount_vnd", sa.BigInteger(), nullable=True),
        sa.Column("lane", sa.Text(), nullable=True),
        sa.Column("criteria_json", sa.Text(), nullable=True),
        sa.Column("basis", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema — drop 3 bảng (đảo được)."""
    op.drop_table("assessments")
    op.drop_table("employment_records")
    op.drop_table("police_records")
