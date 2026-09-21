"""tenant isolation key and conversation groups

Revision ID: 9f3a2b7c4d10
Revises: 4b6f0d1a8c23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9f3a2b7c4d10"
down_revision: str | Sequence[str] | None = "4b6f0d1a8c23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
_TENANT_DEFAULT = sa.text(f"'{DEFAULT_TENANT_ID}'::uuid")
_CONVERSATION_CHILDREN = ("messages", "tasks", "cards", "tool_calls", "approvals", "shadow_reviews")
_OTHER_TENANT_TABLES = (
    "assessments",
    "task_attempts",
    "approval_execution_attempts",
    "external_case_links",
    "integration_inbox",
)


def _add_tenant_column(table: str) -> None:
    op.add_column(
        table,
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True, server_default=_TENANT_DEFAULT),
    )


def _backfill_tenants() -> None:
    op.execute(f"UPDATE users SET tenant_id='{DEFAULT_TENANT_ID}'::uuid WHERE tenant_id IS NULL")
    op.execute(
        "UPDATE conversations c SET tenant_id=u.tenant_id FROM users u "
        "WHERE c.user_id=u.username AND c.tenant_id IS NULL"
    )
    op.execute(f"UPDATE conversations SET tenant_id='{DEFAULT_TENANT_ID}'::uuid WHERE tenant_id IS NULL")
    for table in _CONVERSATION_CHILDREN:
        op.execute(
            f"UPDATE {table} child SET tenant_id=c.tenant_id FROM conversations c WHERE child.conversation_id=c.id"
        )
        op.execute(
            f"UPDATE {table} child SET tenant_id=c.tenant_id FROM conversations c "
            "WHERE child.tenant_id IS NULL AND child.conv_id=c.id::text"
        )
        op.execute(f"UPDATE {table} SET tenant_id='{DEFAULT_TENANT_ID}'::uuid WHERE tenant_id IS NULL")
    op.execute("UPDATE task_attempts a SET tenant_id=t.tenant_id FROM tasks t WHERE a.task_id=t.id")
    op.execute(
        "UPDATE approval_execution_attempts x SET tenant_id=a.tenant_id FROM approvals a WHERE x.approval_id=a.id"
    )
    op.execute(
        "UPDATE external_case_links x SET tenant_id=c.tenant_id FROM conversations c WHERE x.conversation_id=c.id"
    )
    for table in _OTHER_TENANT_TABLES:
        op.execute(f"UPDATE {table} SET tenant_id='{DEFAULT_TENANT_ID}'::uuid WHERE tenant_id IS NULL")


def _enforce_tenant_columns() -> None:
    for table in ("users", "conversations", *_CONVERSATION_CHILDREN, *_OTHER_TENANT_TABLES):
        op.alter_column(table, "tenant_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_tenant_id",
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def _create_sync_triggers() -> None:

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION shb_resolve_conversation_reference() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE resolved_id uuid; resolved_tenant uuid;
        BEGIN
          SELECT id, tenant_id INTO resolved_id, resolved_tenant
          FROM conversations WHERE id::text=NEW.conv_id;
          IF FOUND THEN
            NEW.conversation_id := resolved_id;
            NEW.tenant_id := resolved_tenant;
          ELSIF NEW.tenant_id IS NULL THEN
            NEW.tenant_id := '{DEFAULT_TENANT_ID}'::uuid;
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION shb_validate_conversation_group_tenant() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.group_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM conversation_groups g
            WHERE g.id=NEW.group_id AND g.tenant_id=NEW.tenant_id
          ) THEN
            RAISE EXCEPTION 'conversation group must belong to the same tenant'
              USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER trg_conversations_group_tenant "
        "BEFORE INSERT OR UPDATE OF tenant_id,group_id ON conversations "
        "FOR EACH ROW EXECUTE FUNCTION shb_validate_conversation_group_tenant()"
    )
    op.execute(
        f"""
        CREATE FUNCTION shb_sync_task_attempt_tenant() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE resolved_tenant uuid; resolved_conversation uuid;
        BEGIN
          SELECT tenant_id, conversation_id INTO resolved_tenant, resolved_conversation
          FROM tasks WHERE id=NEW.task_id;
          IF FOUND THEN
            NEW.tenant_id := resolved_tenant;
            NEW.conversation_id := COALESCE(NEW.conversation_id, resolved_conversation);
          ELSIF NEW.tenant_id IS NULL THEN
            NEW.tenant_id := '{DEFAULT_TENANT_ID}'::uuid;
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER trg_task_attempts_tenant BEFORE INSERT OR UPDATE OF task_id,tenant_id "
        "ON task_attempts FOR EACH ROW EXECUTE FUNCTION shb_sync_task_attempt_tenant()"
    )
    op.execute(
        f"""
        CREATE FUNCTION shb_sync_approval_attempt_tenant() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE resolved_tenant uuid;
        BEGIN
          SELECT tenant_id INTO resolved_tenant FROM approvals WHERE id=NEW.approval_id;
          IF FOUND THEN
            NEW.tenant_id := resolved_tenant;
          ELSIF NEW.tenant_id IS NULL THEN
            NEW.tenant_id := '{DEFAULT_TENANT_ID}'::uuid;
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER trg_approval_attempts_tenant "
        "BEFORE INSERT OR UPDATE OF approval_id,tenant_id ON approval_execution_attempts "
        "FOR EACH ROW EXECUTE FUNCTION shb_sync_approval_attempt_tenant()"
    )


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
        sa.CheckConstraint("btrim(slug)<>''", name="ck_tenants_slug_not_blank"),
        sa.CheckConstraint("btrim(name)<>''", name="ck_tenants_name_not_blank"),
    )
    op.execute(
        f"INSERT INTO tenants(id,slug,name) VALUES ('{DEFAULT_TENANT_ID}'::uuid,'bank-digital-default','BANK Digital')"
    )

    _add_tenant_column("users")
    _add_tenant_column("conversations")
    for table in (*_CONVERSATION_CHILDREN, *_OTHER_TENANT_TABLES):
        _add_tenant_column(table)

    op.create_table(
        "conversation_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 80", name="ck_conversation_groups_name"),
    )
    op.create_index(
        "uq_conversation_groups_tenant_name_ci",
        "conversation_groups",
        ["tenant_id", "created_by", sa.text("lower(name)")],
        unique=True,
    )
    op.create_index("ix_conversation_groups_tenant_created", "conversation_groups", ["tenant_id", "created_at"])

    op.add_column("conversations", sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_conversations_group_id",
        "conversations",
        "conversation_groups",
        ["group_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _backfill_tenants()
    _enforce_tenant_columns()

    op.alter_column(
        "assessments",
        "tenant_id",
        server_default=sa.text(
            f"COALESCE(NULLIF(current_setting('app.tenant_id', true), '')::uuid, '{DEFAULT_TENANT_ID}'::uuid)"
        ),
    )
    _create_sync_triggers()

    op.create_index("ix_users_tenant_username", "users", ["tenant_id", "username"])
    op.create_index("ix_conversations_tenant_created", "conversations", ["tenant_id", "created_at"])
    op.create_index(
        "ix_conversations_tenant_group_created",
        "conversations",
        ["tenant_id", "group_id", "created_at"],
    )
    op.create_index("ix_messages_tenant_ts", "messages", ["tenant_id", "ts"])
    op.create_index("ix_tasks_tenant_ended", "tasks", ["tenant_id", "ended_at"])
    op.create_index("ix_cards_tenant_conv_ts", "cards", ["tenant_id", "conv_id", "ts"])
    op.create_index("ix_tool_calls_tenant_ts", "tool_calls", ["tenant_id", "ts"])
    op.create_index("ix_approvals_tenant_status_created", "approvals", ["tenant_id", "status", "created_at"])
    op.create_index("ix_shadow_reviews_tenant_decided", "shadow_reviews", ["tenant_id", "decided_at"])
    op.create_index("ix_assessments_tenant_created", "assessments", ["tenant_id", "created_at"])
    op.create_index(
        "ix_external_case_links_tenant_status_synced",
        "external_case_links",
        ["tenant_id", "case_status", "synced_at"],
    )
    op.create_index(
        "ix_integration_inbox_tenant_case_received",
        "integration_inbox",
        ["tenant_id", "source_system", "external_case_id", "received_at"],
    )


def downgrade() -> None:
    for index, table in (
        ("ix_integration_inbox_tenant_case_received", "integration_inbox"),
        ("ix_external_case_links_tenant_status_synced", "external_case_links"),
        ("ix_shadow_reviews_tenant_decided", "shadow_reviews"),
        ("ix_assessments_tenant_created", "assessments"),
        ("ix_approvals_tenant_status_created", "approvals"),
        ("ix_tool_calls_tenant_ts", "tool_calls"),
        ("ix_cards_tenant_conv_ts", "cards"),
        ("ix_tasks_tenant_ended", "tasks"),
        ("ix_messages_tenant_ts", "messages"),
        ("ix_conversations_tenant_group_created", "conversations"),
        ("ix_conversations_tenant_created", "conversations"),
        ("ix_users_tenant_username", "users"),
    ):
        op.drop_index(index, table_name=table)

    op.execute("DROP TRIGGER trg_approval_attempts_tenant ON approval_execution_attempts")
    op.execute("DROP FUNCTION shb_sync_approval_attempt_tenant()")
    op.execute("DROP TRIGGER trg_task_attempts_tenant ON task_attempts")
    op.execute("DROP FUNCTION shb_sync_task_attempt_tenant()")
    op.execute("DROP TRIGGER trg_conversations_group_tenant ON conversations")
    op.execute("DROP FUNCTION shb_validate_conversation_group_tenant()")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION shb_resolve_conversation_reference() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          NEW.conversation_id := (SELECT id FROM conversations WHERE id::text=NEW.conv_id);
          RETURN NEW;
        END $$
        """
    )

    op.drop_constraint("fk_conversations_group_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "group_id")
    op.drop_index("ix_conversation_groups_tenant_created", table_name="conversation_groups")
    op.drop_index("uq_conversation_groups_tenant_name_ci", table_name="conversation_groups")
    op.drop_table("conversation_groups")

    for table in reversed(("users", "conversations", *_CONVERSATION_CHILDREN, *_OTHER_TENANT_TABLES)):
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")
        op.drop_column(table, "tenant_id")
    op.drop_table("tenants")
