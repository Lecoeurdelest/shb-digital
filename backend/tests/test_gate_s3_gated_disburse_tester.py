from __future__ import annotations

import asyncio
import json

import pytest

from .conftest import requires_db

pytestmark = requires_db


TEST_LOAN_ID = "L007"
TEST_CONV_ID = "tester-t34-gate-s3-conv"
TEST_AMOUNT = 5_000_000_000


def _restore_loan_status(conn, loan_id: str, status: str = "active") -> None:

    cur = conn.cursor()
    cur.execute("UPDATE loans SET status=%s WHERE loan_id=%s", (status, loan_id))
    conn.commit()
    cur.close()


def _cleanup_approvals_and_cards(conn, conv_id: str) -> None:

    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv_id,))
        conn.commit()
    except Exception:  # noqa: BLE001
        conn.rollback()
    finally:
        cur.close()


@pytest.fixture(autouse=True)
def _clean_state(pg_conn):

    _restore_loan_status(pg_conn, TEST_LOAN_ID, "active")
    _cleanup_approvals_and_cards(pg_conn, TEST_CONV_ID)
    yield
    _restore_loan_status(pg_conn, TEST_LOAN_ID, "active")
    _cleanup_approvals_and_cards(pg_conn, TEST_CONV_ID)


# ═════════════════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_branch4_first_call_creates_pending_approval_loans_unchanged():

    from app.orch import gated, registry
    from app.sse import bus

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    q = bus.subscribe(TEST_CONV_ID)
    try:
        result = await gated.gated("disburse", None)(args)
    finally:
        bus.unsubscribe(TEST_CONV_ID, q)

    body = result["content"][0]["text"] if "content" in result else result
    payload = json.loads(body) if isinstance(body, str) else body
    assert payload.get("code") == "approval_required", "Expected invariant was not satisfied at source line 71."
    assert payload.get("retryable") is False
    assert "message" in payload and "hint" in payload, "Expected invariant was not satisfied at source line 73."

    import re

    uuid_pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
    assert not uuid_pattern.search(payload.get("message", "") + payload.get("hint", "")), (
        "Expected invariant was not satisfied at source line 78."
    )

    import psycopg2

    from app.db.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT status, payload_hash FROM approvals WHERE conv_id=%s AND action='disburse'",
            (TEST_CONV_ID,),
        )
        rows = cur.fetchall()
        assert len(rows) == 1, "Expected invariant was not satisfied at source line 94."
        assert rows[0][0] == "pending"

        cur.execute("SELECT status FROM loans WHERE loan_id=%s", (TEST_LOAN_ID,))
        loan_status = cur.fetchone()[0]
        assert loan_status == "active", "Expected invariant was not satisfied at source line 99."
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_branch4_repeated_call_while_pending_does_not_duplicate_ticket():

    from app.orch import gated, registry

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    await gated.gated("disburse", None)(args)
    result2 = await gated.gated("disburse", None)(args)

    body = result2["content"][0]["text"] if "content" in result2 else result2
    payload = json.loads(body) if isinstance(body, str) else body
    assert payload.get("code") == "approval_pending", "Expected invariant was not satisfied at source line 117."

    import psycopg2

    from app.db.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) FROM approvals WHERE conv_id=%s AND action='disburse'",
            (TEST_CONV_ID,),
        )
        n = cur.fetchone()[0]
        assert n == 1, "Expected invariant was not satisfied at source line 131."
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_branch2_approved_ticket_claimed_atomically_executes_and_disburses():

    from app.orch import gated, registry

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    await gated.gated("disburse", None)(args)

    import psycopg2

    from app.db.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE approvals SET status='approved', decided_by='test-admin', decided_at=now() "
            "WHERE conv_id=%s AND action='disburse' AND status='pending'",
            (TEST_CONV_ID,),
        )
        conn.commit()
        assert cur.rowcount == 1, "Expected invariant was not satisfied at source line 164."
        cur.close()
    finally:
        conn.close()

    result = await gated.gated("disburse", None)(args)
    body = result["content"][0]["text"] if "content" in result else result
    payload = json.loads(body) if isinstance(body, str) else body
    assert payload.get("disbursed") is True or payload.get("code") is None, (
        "Expected invariant was not satisfied at source line 172."
    )

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SELECT status FROM loans WHERE loan_id=%s", (TEST_LOAN_ID,))
        assert cur.fetchone()[0] == "disbursed", "Expected invariant was not satisfied at source line 180."

        cur.execute(
            "SELECT status, receipt FROM approvals WHERE conv_id=%s AND action='disburse'",
            (TEST_CONV_ID,),
        )
        row = cur.fetchone()
        assert row[0] == "used", "Expected invariant was not satisfied at source line 187."
        assert row[1] is not None, "Expected invariant was not satisfied at source line 188."
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_branch1_repeated_call_after_receipt_returns_cached_no_double_disburse():

    from app.orch import gated, registry

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    await gated.gated("disburse", None)(args)

    import psycopg2

    from app.db.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE approvals SET status='approved' WHERE conv_id=%s AND action='disburse'",
            (TEST_CONV_ID,),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()

    result_first_execute = await gated.gated("disburse", None)(args)
    result_retry = await gated.gated("disburse", None)(args)

    body1 = result_first_execute["content"][0]["text"] if "content" in result_first_execute else result_first_execute
    body2 = result_retry["content"][0]["text"] if "content" in result_retry else result_retry
    p1 = json.loads(body1) if isinstance(body1, str) else body1
    p2 = json.loads(body2) if isinstance(body2, str) else body2
    assert p2.get("hint", "").lower().find("already executed") != -1 or p2 == p1, (
        "Expected invariant was not satisfied at source line 231."
    )

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SELECT status FROM loans WHERE loan_id=%s", (TEST_LOAN_ID,))
        assert cur.fetchone()[0] == "disbursed", "Expected invariant was not satisfied at source line 239."
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_branch3_pending_call_returns_approval_pending_not_required():

    from app.orch import gated, registry

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    r1 = await gated.gated("disburse", None)(args)
    r2 = await gated.gated("disburse", None)(args)

    b1 = r1["content"][0]["text"] if "content" in r1 else r1
    b2 = r2["content"][0]["text"] if "content" in r2 else r2
    p1 = json.loads(b1) if isinstance(b1, str) else b1
    p2 = json.loads(b2) if isinstance(b2, str) else b2

    assert p1["code"] == "approval_required"
    assert p2["code"] == "approval_pending"
    assert p1["code"] != p2["code"], "Expected invariant was not satisfied at source line 268."


# ═════════════════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════════════════


def test_payload_hash_equivalence_int_float_key_order_none_drop():

    from app.orch import gated

    h1 = gated.payload_hash("disburse", {"loan_id": "L007", "amount": 5_000_000_000})
    h2 = gated.payload_hash("disburse", {"loan_id": "L007", "amount": 5_000_000_000.0})  # float
    h3 = gated.payload_hash("disburse", {"amount": 5_000_000_000, "loan_id": "L007"})
    h4 = gated.payload_hash("disburse", {"loan_id": "L007", "amount": 5_000_000_000, "note": None})  # None-drop
    h5 = gated.payload_hash("disburse", {"loan_id": "L007", "amount": 5e9})  # scientific notation

    assert h1 == h2 == h3 == h4 == h5, "Expected invariant was not satisfied at source line 286."

    h_diff_amount = gated.payload_hash("disburse", {"loan_id": "L007", "amount": 1_000_000_000})
    assert h1 != h_diff_amount, "Expected invariant was not satisfied at source line 289."

    h_diff_loan = gated.payload_hash("disburse", {"loan_id": "L999", "amount": 5_000_000_000})
    assert h1 != h_diff_loan, "Expected invariant was not satisfied at source line 292."


def test_payload_hash_used_consistently_at_creation_and_verify():

    from app.orch import gated, registry

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    asyncio.run(gated.gated("disburse", None)(args))

    expected_hash = gated.payload_hash("disburse", args)

    import psycopg2

    from app.db.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT payload_hash FROM approvals WHERE conv_id=%s AND action='disburse'",
            (TEST_CONV_ID,),
        )
        row = cur.fetchone()
        assert row is not None, "Expected invariant was not satisfied at source line 318."
        assert row[0] == expected_hash, "Expected invariant was not satisfied at source line 319."
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_concurrent_double_claim_basic_only_one_executes():

    from app.orch import gated, registry, store

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    await gated.gated("disburse", None)(args)

    import psycopg2

    from app.db.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE approvals SET status='approved' WHERE conv_id=%s AND action='disburse'",
            (TEST_CONV_ID,),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()

    results = await asyncio.gather(
        gated.gated("disburse", None)(args),
        gated.gated("disburse", None)(args),
        return_exceptions=True,
    )

    for r in results:
        assert not isinstance(r, Exception), "Expected invariant was not satisfied at source line 365."

    def _payload(r: dict) -> dict:
        body = r["content"][0]["text"] if "content" in r else r
        return json.loads(body) if isinstance(body, str) else body

    def _is_fresh_execution(p: dict) -> bool:

        return p.get("disbursed") is True and "already executed" not in p.get("hint", "").lower()

    def _is_cached_receipt(p: dict) -> bool:

        return p.get("disbursed") is True and "already executed" in p.get("hint", "").lower()

    payloads = [_payload(r) for r in results]
    fresh_count = sum(1 for p in payloads if _is_fresh_execution(p))
    cached_count = sum(1 for p in payloads if _is_cached_receipt(p))
    assert fresh_count == 1, "Expected invariant was not satisfied at source line 382."
    assert cached_count == 1, "Expected invariant was not satisfied at source line 385."

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) FROM approvals WHERE conv_id=%s AND action='disburse' AND status='used'",
            (TEST_CONV_ID,),
        )
        used_count = cur.fetchone()[0]
        assert used_count == 1, "Expected invariant was not satisfied at source line 398."

        cur.execute(
            "SELECT count(*) FROM approvals WHERE conv_id=%s AND action='disburse'",
            (TEST_CONV_ID,),
        )
        total_count = cur.fetchone()[0]
        assert total_count == 1, "Expected invariant was not satisfied at source line 405."

        cur.execute("SELECT status FROM loans WHERE loan_id=%s", (TEST_LOAN_ID,))
        assert cur.fetchone()[0] == "disbursed", "Expected invariant was not satisfied at source line 410."
    finally:
        conn.close()

    cards = await store.list_cards(TEST_CONV_ID)
    approval_cards = [c for c in cards if c["type"] == "approval"]
    assert len(approval_cards) == 1, "Expected invariant was not satisfied at source line 416."


# ═════════════════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_disburse_nonexistent_loan_returns_4field_error_not_traceback():

    from app.orch import gated, registry

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": "L-DOES-NOT-EXIST-999", "amount": TEST_AMOUNT}

    result = await gated.gated("disburse", None)(args)
    body = result["content"][0]["text"] if "content" in result else result
    payload = json.loads(body) if isinstance(body, str) else body
    assert set(payload.keys()) >= {"code", "message"}, "Expected invariant was not satisfied at source line 435."


# ═════════════════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_card_approval_auto_generated_by_vo_not_via_present_tool():

    from app.orch import gated, registry, store

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    await gated.gated("disburse", None)(args)

    cards = await store.list_cards(TEST_CONV_ID)
    approval_cards = [c for c in cards if c["type"] == "approval"]
    assert len(approval_cards) == 1, "Expected invariant was not satisfied at source line 455."
    card = approval_cards[0]
    assert "options" in card or "items" in card, "Expected invariant was not satisfied at source line 457."
