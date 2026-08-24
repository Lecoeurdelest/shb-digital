"""Observable guarantees added by the operational database migrations."""

from __future__ import annotations

from uuid import uuid4

import psycopg2
import pytest

from app.db.config import DATABASE_URL

from .conftest import requires_db


@requires_db
def test_party_and_conversation_references_are_dual_written_without_rejecting_legacy_ids():
    token = uuid4().hex[:10]
    owner = f"CDB{token}"
    known_loan = f"LDB{token}"
    unknown_loan = f"LDU{token}"
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO customers(id,full_name) VALUES(%s,'DB migration test')", (owner,))
            cur.execute("INSERT INTO loans(loan_id,owner_id,status) VALUES(%s,%s,'active')", (known_loan, owner))
            cur.execute(
                "INSERT INTO loans(loan_id,owner_id,status) VALUES(%s,%s,'active')",
                (unknown_loan, f"X{token}"),
            )
            cur.execute("SELECT party_type FROM parties WHERE owner_id=%s", (owner,))
            assert cur.fetchone() == ("customer",)
            cur.execute("SELECT party_id FROM loans WHERE loan_id=%s", (known_loan,))
            assert cur.fetchone() == (owner,)
            cur.execute("SELECT party_id FROM loans WHERE loan_id=%s", (unknown_loan,))
            assert cur.fetchone() == (None,)
            cur.execute(
                "SELECT count(*) FROM operational_data_issues "
                "WHERE issue_type='missing_party' AND entity_table='loans' AND reference_value=%s",
                (f"X{token}",),
            )
            assert cur.fetchone()[0] == 1
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM loans WHERE loan_id IN (%s,%s)", (known_loan, unknown_loan))
            cur.execute("DELETE FROM customers WHERE id=%s", (owner,))
            cur.execute("DELETE FROM parties WHERE owner_id=%s", (owner,))
        conn.close()


@requires_db
def test_approval_idempotency_and_used_receipt_invariant_are_database_enforced():
    token = uuid4().hex
    conv = f"db-invariant-{token}"
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO approvals(conv_id,action,payload,payload_hash,status) "
                "VALUES(%s,'disburse','{}',%s,'pending') RETURNING id,idempotency_key",
                (conv, token[:16]),
            )
            approval_id, key = cur.fetchone()
            assert key == f"idem:v1:{conv}:disburse:{token[:16]}"
            with pytest.raises(psycopg2.errors.UniqueViolation):
                cur.execute(
                    "INSERT INTO approvals(conv_id,action,payload,payload_hash,status) "
                    "VALUES(%s,'disburse','{}',%s,'pending')",
                    (conv, token[:16]),
                )
            with pytest.raises(psycopg2.errors.CheckViolation):
                cur.execute("UPDATE approvals SET status='used' WHERE id=%s", (approval_id,))
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv,))
        conn.close()


@requires_db
def test_operational_tables_and_foreign_keys_exist():
    expected = {
        "parties",
        "task_attempts",
        "approval_execution_attempts",
        "outbox_events",
        "prompt_definitions",
        "prompt_versions",
        "prompt_bindings",
    }
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            assert expected <= {row[0] for row in cur.fetchall()}
            cur.execute("SELECT count(*) FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace")
            assert cur.fetchone()[0] >= 27
    finally:
        conn.close()
