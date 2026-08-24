"""operational identity and dual-written references

Revision ID: 0d7a9e4c2b11
Revises: c8d4e6f1a290
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0d7a9e4c2b11"
down_revision: str | Sequence[str] | None = "c8d4e6f1a290"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PARTY_TABLES = (
    "users",
    "loans",
    "cic_records",
    "collaterals",
    "owner_documents",
    "police_records",
    "employment_records",
    "assessments",
    "applications",
    "interaction_notes",
)
_CONVERSATION_TABLES = ("messages", "tasks", "cards", "tool_calls", "approvals", "shadow_reviews")


def _create_parties() -> None:
    op.create_table(
        "parties",
        sa.Column("owner_id", sa.Text(), primary_key=True),
        sa.Column("party_type", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("party_type IN ('customer','business')", name="ck_parties_type"),
    )
    op.execute(
        "INSERT INTO parties(owner_id,party_type,display_name) "
        "SELECT id,'customer',full_name FROM customers "
        "UNION ALL SELECT id,'business',name FROM businesses"
    )
    op.execute(
        """
        CREATE FUNCTION shb_refresh_party_references(p_owner_id text) RETURNS void
        LANGUAGE plpgsql AS $$
        BEGIN
          UPDATE users SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE loans SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE cic_records SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE collaterals SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE owner_documents SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE police_records SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE employment_records SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE assessments SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE applications SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE interaction_notes SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE party_relations SET from_party_id=p_owner_id WHERE from_id=p_owner_id;
          UPDATE party_relations SET to_party_id=p_owner_id WHERE to_id=p_owner_id;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION shb_sync_customer_party() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          INSERT INTO parties(owner_id,party_type,display_name)
          VALUES(NEW.id,'customer',NEW.full_name)
          ON CONFLICT(owner_id) DO UPDATE
            SET display_name=EXCLUDED.display_name, updated_at=now()
            WHERE parties.party_type='customer';
          IF NOT FOUND THEN RAISE EXCEPTION 'owner_id is already assigned to another party type'; END IF;
          PERFORM shb_refresh_party_references(NEW.id);
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION shb_sync_business_party() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          INSERT INTO parties(owner_id,party_type,display_name)
          VALUES(NEW.id,'business',NEW.name)
          ON CONFLICT(owner_id) DO UPDATE
            SET display_name=EXCLUDED.display_name, updated_at=now()
            WHERE parties.party_type='business';
          IF NOT FOUND THEN RAISE EXCEPTION 'owner_id is already assigned to another party type'; END IF;
          PERFORM shb_refresh_party_references(NEW.id);
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER trg_customers_party BEFORE INSERT OR UPDATE OF id,full_name ON customers "
        "FOR EACH ROW EXECUTE FUNCTION shb_sync_customer_party()"
    )
    op.execute(
        "CREATE TRIGGER trg_businesses_party BEFORE INSERT OR UPDATE OF id,name ON businesses "
        "FOR EACH ROW EXECUTE FUNCTION shb_sync_business_party()"
    )
    op.create_foreign_key("fk_customers_party", "customers", "parties", ["id"], ["owner_id"])
    op.create_foreign_key("fk_businesses_party", "businesses", "parties", ["id"], ["owner_id"])


def _create_party_references() -> None:
    for table in _PARTY_TABLES:
        op.add_column(table, sa.Column("party_id", sa.Text(), nullable=True))
    op.add_column("party_relations", sa.Column("from_party_id", sa.Text(), nullable=True))
    op.add_column("party_relations", sa.Column("to_party_id", sa.Text(), nullable=True))
    for table in _PARTY_TABLES:
        op.execute(
            f"UPDATE {table} child SET party_id=p.owner_id FROM parties p "
            "WHERE child.owner_id=p.owner_id"
        )
    op.execute(
        "UPDATE party_relations r SET from_party_id=p.owner_id FROM parties p WHERE r.from_id=p.owner_id"
    )
    op.execute("UPDATE party_relations r SET to_party_id=p.owner_id FROM parties p WHERE r.to_id=p.owner_id")
    op.execute(
        """
        CREATE FUNCTION shb_resolve_party_reference() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          NEW.party_id := (SELECT owner_id FROM parties WHERE owner_id=NEW.owner_id);
          RETURN NEW;
        END $$
        """
    )
    for table in _PARTY_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_party_ref BEFORE INSERT OR UPDATE OF owner_id,party_id ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION shb_resolve_party_reference()"
        )
        op.create_index(f"ix_{table}_party_id", table, ["party_id"])
        op.create_foreign_key(
            f"fk_{table}_party_id",
            table,
            "parties",
            ["party_id"],
            ["owner_id"],
            ondelete="SET NULL",
        )
    op.execute(
        """
        CREATE FUNCTION shb_resolve_relation_parties() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          NEW.from_party_id := (SELECT owner_id FROM parties WHERE owner_id=NEW.from_id);
          NEW.to_party_id := (SELECT owner_id FROM parties WHERE owner_id=NEW.to_id);
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER trg_party_relations_refs BEFORE INSERT OR UPDATE ON party_relations "
        "FOR EACH ROW EXECUTE FUNCTION shb_resolve_relation_parties()"
    )
    for side in ("from", "to"):
        op.create_index(f"ix_party_relations_{side}_party_id", "party_relations", [f"{side}_party_id"])
        op.create_foreign_key(
            f"fk_party_relations_{side}_party_id",
            "party_relations",
            "parties",
            [f"{side}_party_id"],
            ["owner_id"],
            ondelete="SET NULL",
        )


def _create_conversation_references() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column("conversations", sa.Column("deleted_at", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("conversations", sa.Column("row_version", sa.Integer(), nullable=False, server_default="0"))
    op.execute(
        """
        CREATE FUNCTION shb_touch_conversation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          NEW.updated_at := now();
          NEW.row_version := OLD.row_version + 1;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER trg_conversations_touch BEFORE UPDATE ON conversations "
        "FOR EACH ROW EXECUTE FUNCTION shb_touch_conversation()"
    )
    for table in _CONVERSATION_TABLES:
        op.add_column(table, sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.execute(
            f"UPDATE {table} child SET conversation_id=c.id FROM conversations c "
            "WHERE child.conv_id=c.id::text"
        )
    op.execute(
        """
        CREATE FUNCTION shb_resolve_conversation_reference() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          NEW.conversation_id := (SELECT id FROM conversations WHERE id::text=NEW.conv_id);
          RETURN NEW;
        END $$
        """
    )
    for table in _CONVERSATION_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_conversation_ref "
            f"BEFORE INSERT OR UPDATE OF conv_id,conversation_id ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION shb_resolve_conversation_reference()"
        )
        op.create_index(f"ix_{table}_conversation_id", table, ["conversation_id"])
        op.create_foreign_key(
            f"fk_{table}_conversation_id",
            table,
            "conversations",
            ["conversation_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.execute(
        "ALTER TABLE shadow_reviews ADD CONSTRAINT fk_shadow_reviews_approval "
        "FOREIGN KEY (approval_id) REFERENCES approvals(id) NOT VALID"
    )


def _create_issue_view() -> None:
    conversation_queries = [
        f"SELECT 'missing_conversation'::text issue_type,'{table}'::text entity_table,"
        f"id::text entity_key,conv_id reference_value FROM {table} "
        "WHERE conv_id IS NOT NULL AND conversation_id IS NULL"
        for table in _CONVERSATION_TABLES
        if table != "shadow_reviews"
    ]
    conversation_queries.append(
        "SELECT 'missing_conversation','shadow_reviews',approval_id::text,conv_id FROM shadow_reviews "
        "WHERE conv_id IS NOT NULL AND conversation_id IS NULL"
    )
    party_queries = [
        f"SELECT 'missing_party','{table}',ctid::text,owner_id::text FROM {table} "
        "WHERE owner_id IS NOT NULL AND party_id IS NULL"
        for table in _PARTY_TABLES
    ]
    approval_query = (
        "SELECT 'missing_approval','shadow_reviews',approval_id::text,approval_id::text FROM shadow_reviews s "
        "WHERE NOT EXISTS (SELECT 1 FROM approvals a WHERE a.id=s.approval_id)"
    )
    op.execute("CREATE VIEW operational_data_issues AS " + " UNION ALL ".join([*conversation_queries, *party_queries, approval_query]))


def upgrade() -> None:
    _create_parties()
    _create_party_references()
    _create_conversation_references()
    _create_issue_view()


def downgrade() -> None:
    op.execute("DROP VIEW operational_data_issues")
    op.drop_constraint("fk_shadow_reviews_approval", "shadow_reviews", type_="foreignkey")
    for table in reversed(_CONVERSATION_TABLES):
        op.drop_constraint(f"fk_{table}_conversation_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_conversation_id", table_name=table)
        op.execute(f"DROP TRIGGER trg_{table}_conversation_ref ON {table}")
        op.drop_column(table, "conversation_id")
    op.execute("DROP FUNCTION shb_resolve_conversation_reference()")
    op.execute("DROP TRIGGER trg_conversations_touch ON conversations")
    op.execute("DROP FUNCTION shb_touch_conversation()")
    op.drop_column("conversations", "row_version")
    op.drop_column("conversations", "deleted_at")
    op.drop_column("conversations", "updated_at")
    op.execute("DROP TRIGGER trg_party_relations_refs ON party_relations")
    op.execute("DROP FUNCTION shb_resolve_relation_parties()")
    for side in reversed(("from", "to")):
        op.drop_constraint(f"fk_party_relations_{side}_party_id", "party_relations", type_="foreignkey")
        op.drop_index(f"ix_party_relations_{side}_party_id", table_name="party_relations")
        op.drop_column("party_relations", f"{side}_party_id")
    for table in reversed(_PARTY_TABLES):
        op.drop_constraint(f"fk_{table}_party_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_party_id", table_name=table)
        op.execute(f"DROP TRIGGER trg_{table}_party_ref ON {table}")
        op.drop_column(table, "party_id")
    op.execute("DROP FUNCTION shb_resolve_party_reference()")
    op.drop_constraint("fk_businesses_party", "businesses", type_="foreignkey")
    op.drop_constraint("fk_customers_party", "customers", type_="foreignkey")
    op.execute("DROP TRIGGER trg_businesses_party ON businesses")
    op.execute("DROP TRIGGER trg_customers_party ON customers")
    op.execute("DROP FUNCTION shb_sync_business_party()")
    op.execute("DROP FUNCTION shb_sync_customer_party()")
    op.execute("DROP FUNCTION shb_refresh_party_references(text)")
    op.drop_table("parties")
