"""enforce immutable tenant ownership on operational rows

Revision ID: e6f9b2c4d105
Revises: d4e8a1b7c203
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e6f9b2c4d105"
down_revision: str | Sequence[str] | None = "d4e8a1b7c203"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# D-79: tenant là partition/isolation key, không phải thuộc tính có thể chuyển sau khi tạo.
# Liệt kê tường minh để migration review thấy chính xác phạm vi được khóa.
_TENANT_TABLES = (
    "users",
    "conversation_groups",
    "conversations",
    "messages",
    "tasks",
    "cards",
    "tool_calls",
    "approvals",
    "shadow_reviews",
    "assessments",
    "task_attempts",
    "approval_execution_attempts",
    "external_case_links",
    "integration_inbox",
    "consent_records",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION shb_reject_tenant_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
            RAISE EXCEPTION 'tenant_id is immutable for %', TG_TABLE_NAME
              USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
        """
    )
    for table in _TENANT_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_tenant_immutable "
            f"BEFORE UPDATE OF tenant_id ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION shb_reject_tenant_change()"
        )


def downgrade() -> None:
    for table in reversed(_TENANT_TABLES):
        op.execute(f"DROP TRIGGER trg_{table}_tenant_immutable ON {table}")
    op.execute("DROP FUNCTION shb_reject_tenant_change()")
