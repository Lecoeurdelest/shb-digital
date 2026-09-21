from __future__ import annotations

import json
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.db.config import DATABASE_URL
from app.main import app
from app.orch import store_approvals

from .conftest import requires_db, requires_test_db

client = TestClient(app)


def _admin_cookie():
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    return r.cookies


def _mk_pending_raw(conv: str, payload: dict, action: str = "disburse") -> str:

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO approvals (conv_id, action, payload, payload_hash, status) "
                "VALUES (%s,%s,%s,%s,'pending') RETURNING id",
                (conv, action, json.dumps(payload), "dfb01_" + uuid4().hex[:12]),
            )
            return str(cur.fetchone()[0])
    finally:
        conn.close()


def _seed_assessment(owner_id: str, lane: str) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO assessments (owner_id, lane, loan_amount_vnd, criteria_json, created_at) "
                "VALUES (%s,%s,%s,'[]',now()::text) RETURNING id",
                (owner_id, lane, 100_000_000),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def _rm_dfb01(conv: str, owners: tuple[str, ...] = ()) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv,))
        for o in owners:
            cur.execute("DELETE FROM assessments WHERE owner_id=%s", (o,))
    conn.close()


@requires_test_db
@pytest.mark.asyncio
async def test_enrich_display_real_loan_full_5_fields():

    lane_id = _seed_assessment("C001", "green")
    aid = _mk_pending_raw("dfb01a", {"loan_id": "L001", "amount": 5000000000})
    try:
        rows = await store_approvals.list_pending("dfb01a")
        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == aid

        assert row["payload"] == {"loan_id": "L001", "amount": 5000000000}
        assert row["status"] == "pending"
        d = row["display"]
        assert set(d) == {"customer_name", "owner_id", "loan_id", "amount_vnd", "lane"}
        assert len(d["customer_name"].split()) == 3
        assert d["owner_id"] == "C001"
        assert d["loan_id"] == "L001"
        assert d["amount_vnd"] == 5000000000  # int
        assert d["lane"] == "green"
    finally:
        _rm_dfb01("dfb01a")
        _cleanup_assessment(lane_id)


@requires_db
@pytest.mark.asyncio
async def test_enrich_display_loan_id_is_owner_fallback():

    aid = _mk_pending_raw("dfb01b", {"loan_id": "C001", "amount": 300000000})
    try:
        rows = await store_approvals.list_pending("dfb01b")
        d = next(r for r in rows if r["id"] == aid)["display"]
        assert len(d["customer_name"].split()) == 3
        assert d["owner_id"] == "C001"
        assert d["loan_id"] == "C001"
        assert d["amount_vnd"] == 300000000
    finally:
        _rm_dfb01("dfb01b")


@requires_db
@pytest.mark.asyncio
async def test_enrich_display_ops_disburse_application_id_amount_vnd():

    aid = _mk_pending_raw("dfb01ops", {"application_id": "APP01", "amount_vnd": 250000000}, action="ops_disburse")
    try:
        rows = await store_approvals.list_pending("dfb01ops")
        d = next(r for r in rows if r["id"] == aid)["display"]
        assert len(d["customer_name"].split()) == 3
        assert d["owner_id"] == "C004"
        assert d["loan_id"] == "APP01"  # ref_id = application_id (COALESCE)
        assert d["amount_vnd"] == 250000000
    finally:
        _rm_dfb01("dfb01ops")


@requires_db
@pytest.mark.asyncio
async def test_enrich_display_garbage_payload_all_null_no_500():

    a_bad_amt = _mk_pending_raw("dfb01c", {"loan_id": "L001", "amount": "notanumber"})
    a_empty = _mk_pending_raw("dfb01c", {})
    a_no_loan = _mk_pending_raw("dfb01c", {"amount": 123})
    try:
        rows = await store_approvals.list_pending("dfb01c")
        by_id = {r["id"]: r["display"] for r in rows}

        assert by_id[a_bad_amt]["amount_vnd"] is None
        assert len(by_id[a_bad_amt]["customer_name"].split()) == 3

        assert all(by_id[a_empty][k] is None for k in ("customer_name", "owner_id", "loan_id", "amount_vnd", "lane"))

        assert by_id[a_no_loan]["customer_name"] is None
        assert by_id[a_no_loan]["loan_id"] is None
        assert by_id[a_no_loan]["amount_vnd"] == 123
    finally:
        _rm_dfb01("dfb01c")


@requires_db
@pytest.mark.asyncio
async def test_enrich_orphan_loan_owner_not_customer_name_null():

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO loans (loan_id, owner_id, principal, outstanding, monthly_payment, status) "
            "VALUES ('LDFB1','GHOST_OWNER',1,1,1,'active') ON CONFLICT (loan_id) DO NOTHING"
        )
    conn.close()
    aid = _mk_pending_raw("dfb01d", {"loan_id": "LDFB1", "amount": 1})
    try:
        d = next(r for r in (await store_approvals.list_pending("dfb01d")) if r["id"] == aid)["display"]
        assert d["owner_id"] == "GHOST_OWNER"
        assert d["customer_name"] is None
    finally:
        _rm_dfb01("dfb01d")
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM loans WHERE loan_id='LDFB1'")
        conn.close()


@requires_db
def test_enrich_api_endpoint_returns_display():

    aid = _mk_pending_raw("dfb01e", {"loan_id": "L001", "amount": 5000000000})
    try:
        r = client.get("/api/approvals?status=pending", cookies=_admin_cookie())
        assert r.status_code == 200
        rows = r.json()
        row = next(x for x in rows if x["id"] == aid)
        assert "display" in row and len(row["display"]["customer_name"].split()) == 3

        assert row["payload"] == {"loan_id": "L001", "amount": 5000000000}
        assert row["status"] == "pending" and "payload_hash" in row
    finally:
        _rm_dfb01("dfb01e")


def _cleanup_assessment(aid: int) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    conn.cursor().execute("DELETE FROM assessments WHERE id=%s", (aid,))
    conn.close()
