"""workflow idempotency, leases, attempts, and transactional outbox

Revision ID: 1e8b0f5d3c22
Revises: 0d7a9e4c2b11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "1e8b0f5d3c22"
down_revision: str | Sequence[str] | None = "0d7a9e4c2b11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _approval_columns() -> None:
    op.add_column("approvals", sa.Column("idempotency_key", sa.Text(), nullable=True))
    op.add_column(
        "approvals",
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True, server_default=sa.text("now()")),
    )
    op.add_column(
        "approvals",
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True, server_default=sa.text("now()")),
    )
    op.add_column("approvals", sa.Column("row_version", sa.Integer(), nullable=False, server_default="0"))
    op.execute(
        "UPDATE approvals SET idempotency_key='idem:v1:' || conv_id || ':' || action || ':' || payload_hash, "
        "created_at=COALESCE(decided_at,used_at,now()), updated_at=COALESCE(decided_at,used_at,now())"
    )
    op.execute(
        """
        CREATE FUNCTION shb_prepare_approval() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.idempotency_key IS NULL OR NEW.idempotency_key='' THEN
            NEW.idempotency_key := 'idem:v1:' || NEW.conv_id || ':' || NEW.action || ':' || NEW.payload_hash;
          END IF;
          IF TG_OP='INSERT' THEN
            NEW.created_at := COALESCE(NEW.created_at,now());
            NEW.updated_at := COALESCE(NEW.updated_at,NEW.created_at);
            NEW.row_version := COALESCE(NEW.row_version,0);
          ELSE
            NEW.updated_at := now();
            NEW.row_version := OLD.row_version + 1;
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER trg_approvals_prepare BEFORE INSERT OR UPDATE ON approvals "
        "FOR EACH ROW EXECUTE FUNCTION shb_prepare_approval()"
    )
    op.alter_column("approvals", "idempotency_key", existing_type=sa.Text(), nullable=False)
    op.alter_column(
        "approvals",
        "created_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=False,
    )
    op.alter_column(
        "approvals",
        "updated_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=False,
    )
    op.create_unique_constraint("uq_approvals_idempotency_key", "approvals", ["idempotency_key"])
    op.create_check_constraint(
        "ck_approvals_status",
        "approvals",
        "status IN ('pending','approved','rejected','used','exec_failed')",
    )
    op.create_check_constraint(
        "ck_approvals_used_receipt",
        "approvals",
        "(status='used') = (receipt IS NOT NULL AND used_at IS NOT NULL)",
    )
    op.create_index(
        "ix_approvals_pending_created",
        "approvals",
        ["created_at"],
        postgresql_where=sa.text("status='pending'"),
    )


def _task_resilience() -> None:
    op.add_column("tasks", sa.Column("parent_task_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("tasks", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tasks", sa.Column("lease_owner", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("lease_until", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("heartbeat_at", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("row_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_foreign_key(
        "fk_tasks_parent_task",
        "tasks",
        "tasks",
        ["parent_task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint("ck_tasks_attempt_count", "tasks", "attempt_count >= 0")
    op.create_check_constraint(
        "ck_tasks_lease_pair",
        "tasks",
        "(lease_owner IS NULL) = (lease_until IS NULL)",
    )
    op.create_index(
        "ix_tasks_claim",
        "tasks",
        ["queued_at"],
        postgresql_where=sa.text("status='queued'"),
    )
    op.create_index(
        "ix_tasks_expired_lease",
        "tasks",
        ["lease_until"],
        postgresql_where=sa.text("lease_until IS NOT NULL"),
    )


def _attempt_tables() -> None:
    op.create_table(
        "task_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        sa.Column(
            "started_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("ended_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("task_id", "attempt_no", name="uq_task_attempts_number"),
        sa.CheckConstraint("attempt_no > 0", name="ck_task_attempts_number"),
        sa.CheckConstraint(
            "status IN ('running','succeeded','failed','timeout','cancelled')",
            name="ck_task_attempts_status",
        ),
    )
    op.create_index("ix_task_attempts_conversation_started", "task_attempts", ["conversation_id", "started_at"])
    op.create_table(
        "approval_execution_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("result_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column(
            "started_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("ended_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("approval_id", "attempt_no", name="uq_approval_attempts_number"),
        sa.CheckConstraint("attempt_no > 0", name="ck_approval_attempts_number"),
        sa.CheckConstraint(
            "status IN ('running','succeeded','failed','timeout','cancelled')",
            name="ck_approval_attempts_status",
        ),
    )
    op.create_index(
        "uq_approval_attempts_one_success",
        "approval_execution_attempts",
        ["approval_id"],
        unique=True,
        postgresql_where=sa.text("status='succeeded'"),
    )


def _outbox() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "available_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("locked_by", sa.Text(), nullable=True),
        sa.Column("locked_until", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("status IN ('pending','publishing','published','dead')", name="ck_outbox_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_outbox_attempt_count"),
        sa.CheckConstraint("(locked_by IS NULL) = (locked_until IS NULL)", name="ck_outbox_lock_pair"),
    )
    op.create_index(
        "ix_outbox_claim",
        "outbox_events",
        ["available_at", "created_at"],
        postgresql_where=sa.text("status='pending'"),
    )
    op.create_index("ix_outbox_aggregate", "outbox_events", ["aggregate_type", "aggregate_id", "created_at"])


def upgrade() -> None:
    _approval_columns()
    _task_resilience()
    _attempt_tables()
    _outbox()


def downgrade() -> None:
    op.drop_index("ix_outbox_aggregate", table_name="outbox_events")
    op.drop_index("ix_outbox_claim", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index("uq_approval_attempts_one_success", table_name="approval_execution_attempts")
    op.drop_table("approval_execution_attempts")
    op.drop_index("ix_task_attempts_conversation_started", table_name="task_attempts")
    op.drop_table("task_attempts")
    op.drop_index("ix_tasks_expired_lease", table_name="tasks")
    op.drop_index("ix_tasks_claim", table_name="tasks")
    op.drop_constraint("ck_tasks_lease_pair", "tasks", type_="check")
    op.drop_constraint("ck_tasks_attempt_count", "tasks", type_="check")
    op.drop_constraint("fk_tasks_parent_task", "tasks", type_="foreignkey")
    for column in ("row_version", "heartbeat_at", "lease_until", "lease_owner", "attempt_count", "parent_task_id"):
        op.drop_column("tasks", column)
    op.drop_index("ix_approvals_pending_created", table_name="approvals")
    op.drop_constraint("ck_approvals_used_receipt", "approvals", type_="check")
    op.drop_constraint("ck_approvals_status", "approvals", type_="check")
    op.drop_constraint("uq_approvals_idempotency_key", "approvals", type_="unique")
    op.execute("DROP TRIGGER trg_approvals_prepare ON approvals")
    op.execute("DROP FUNCTION shb_prepare_approval()")
    for column in ("row_version", "updated_at", "created_at", "idempotency_key"):
        op.drop_column("approvals", column)
