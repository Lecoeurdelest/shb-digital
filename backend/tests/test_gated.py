from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import psycopg2
import pytest

from app.db.config import DATABASE_URL
from app.orch import registry
from app.orch.gated import GATED_WHITELIST, gated, payload_hash
from app.sse import bus, emit

from .conftest import requires_db


def _payload(env: dict) -> dict:
    return json.loads(env["content"][0]["text"])


def _loan_status(lid: str) -> str | None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM loans WHERE loan_id=%s", (lid,))
            r = cur.fetchone()
            return r[0] if r else None
    finally:
        conn.close()


def _set_loan(lid: str, st: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE loans SET status=%s WHERE loan_id=%s", (st, lid))
        conn.commit()
    finally:
        conn.close()


def _approve(conv: str, action: str, ph: str) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE approvals SET status='approved' WHERE conv_id=%s AND action=%s "
                "AND payload_hash=%s AND status='pending'",
                (conv, action, ph),
            )
            n = cur.rowcount
        conn.commit()
        return n
    finally:
        conn.close()


def _count_approvals(conv: str) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM approvals WHERE conv_id=%s", (conv,))
            return cur.fetchone()[0]
    finally:
        conn.close()


def test_payload_hash_int_float_order_same():
    h1 = payload_hash("disburse", {"loan_id": "L001", "amount": 5000000000})
    h2 = payload_hash("disburse", {"amount": 5e9, "loan_id": "L001"})  # order + 5e9≡5000000000
    assert h1 == h2


def test_payload_hash_drops_non_biz_fields():
    h1 = payload_hash("disburse", {"loan_id": "L001", "amount": 5000000000})
    h2 = payload_hash("disburse", {"loan_id": "L001", "amount": 5000000000, "ts": "2026-01-01"})
    assert h1 == h2


def test_payload_hash_drops_none():
    h1 = payload_hash("disburse", {"loan_id": "L001", "amount": 5000000000})
    h2 = payload_hash("disburse", {"loan_id": "L001", "amount": 5000000000, "extra": None})
    assert h1 == h2


def test_payload_hash_different_amount_different_hash():
    h5 = payload_hash("disburse", {"loan_id": "L001", "amount": 5000000000})
    h1 = payload_hash("disburse", {"loan_id": "L001", "amount": 1000000000})
    assert h5 != h1


def test_disburse_in_whitelist():
    assert "disburse" in GATED_WHITELIST


@pytest.fixture
def _reset_sse():
    bus.reset()
    emit.reset()
    yield
    bus.reset()
    emit.reset()


@requires_db
@pytest.mark.asyncio
async def test_branch1_first_call_creates_pending_loans_unchanged(_reset_sse):
    conv = f"gated-b1-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    h = gated("disburse", None)
    args = {"loan_id": "L001", "amount": 5000000000}
    out = _payload(await h(args))
    assert out["code"] == "approval_required"
    assert out["retryable"] is False
    assert _loan_status("L001") == "active"
    assert _count_approvals(conv) == 1


@requires_db
@pytest.mark.asyncio
async def test_branch4_pending_idempotent_no_new(_reset_sse):
    conv = f"gated-b4-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    h = gated("disburse", None)
    args = {"loan_id": "L001", "amount": 5000000000}
    await h(args)
    out = _payload(await h(args))
    assert out["code"] == "approval_pending"
    assert _count_approvals(conv) == 1


@requires_db
@pytest.mark.asyncio
async def test_branch2_approved_claim_executes_disbursed_receipt(_reset_sse):
    conv = f"gated-b2-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    h = gated("disburse", None)
    args = {"loan_id": "L001", "amount": 5000000000}
    ph = payload_hash("disburse", args)
    await h(args)  # pending
    assert _approve(conv, "disburse", ph) == 1
    out = _payload(await h(args))
    assert out["disbursed"] is True
    assert _loan_status("L001") == "disbursed"  # loans ghi status

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, receipt FROM approvals WHERE conv_id=%s AND payload_hash=%s",
                (conv, ph),
            )
            status, receipt = cur.fetchone()
    finally:
        conn.close()
    assert status == "used"
    assert receipt is not None
    _set_loan("L001", "active")


@requires_db
@pytest.mark.asyncio
async def test_branch1_receipt_no_double_execute(_reset_sse):

    conv = f"gated-b1r-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    h = gated("disburse", None)
    args = {"loan_id": "L001", "amount": 5000000000}
    ph = payload_hash("disburse", args)
    await h(args)
    _approve(conv, "disburse", ph)
    await h(args)
    _set_loan("L001", "active")
    out = _payload(await h(args))
    assert "receipt" in out.get("hint", "")
    assert _loan_status("L001") == "active"


@requires_db
@pytest.mark.asyncio
async def test_card_approval_vo_sinh_sse(_reset_sse):
    conv = f"gated-card-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    q = bus.subscribe(conv)
    h = gated("disburse", None)
    await h({"loan_id": "L001", "amount": 5000000000})
    evs = []
    while not q.empty():
        evs.append(q.get_nowait())
    types = [e["type"] for e in evs]
    assert "card" in types
    assert "approval.pending" in types
    assert "conversation.status" in types
    card = next(e for e in evs if e["type"] == "card")["data"]["card"]
    assert card["type"] == "approval"
    assert card["id"]
    assert card["options"] == ["Approve", "Reject"]
    status = next(e for e in evs if e["type"] == "conversation.status")["data"]["status"]
    assert status == "waiting_approval"


@requires_db
@pytest.mark.asyncio
async def test_disburse_loan_not_found_error(_reset_sse):

    conv = f"gated-nf-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    h = gated("disburse", None)

    args = {"loan_id": "NONEXISTENT", "amount": 5_000_000_000}
    ph = payload_hash("disburse", args)
    await h(args)  # pending
    _approve(conv, "disburse", ph)
    out = _payload(await h(args))
    assert out["code"] == "gated_error"

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM approvals WHERE conv_id=%s AND payload_hash=%s", (conv, ph))
            assert cur.fetchone()[0] == "approved"
    finally:
        conn.close()


@requires_db
@pytest.mark.asyncio
async def test_concurrent_claim_no_spurious_ticket(_reset_sse):

    conv = f"gated-race-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    h = gated("disburse", None)
    args = {"loan_id": "L001", "amount": 5000000000}
    ph = payload_hash("disburse", args)
    await h(args)  # pending
    _approve(conv, "disburse", ph)

    await asyncio.gather(h(args), h(args), return_exceptions=True)
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM approvals WHERE conv_id=%s AND status='used'", (conv,))
            used = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM approvals WHERE conv_id=%s AND status='pending'", (conv,))
            pending = cur.fetchone()[0]
    finally:
        conn.close()
    assert used == 1, "Expected invariant was not satisfied at source line 262."
    assert pending == 0, "Expected invariant was not satisfied at source line 263."
    assert _loan_status("L001") == "disbursed"
    _set_loan("L001", "active")


@requires_db
@pytest.mark.asyncio
async def test_tiered_under_threshold_auto_approve_executes(_reset_sse):

    conv = f"gated-auto-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    h = gated("disburse", None)
    args = {"loan_id": "L001", "amount": 400_000_000}  # < 500tr
    out = _payload(await h(args))

    assert out.get("disbursed") is True
    assert out.get("auto_approved") is True
    assert out.get("approved_by") == "auto-rule"
    assert _loan_status("L001") == "disbursed"

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status, decided_by, reason, receipt FROM approvals WHERE conv_id=%s", (conv,))
            status, decided_by, reason, receipt = cur.fetchone()
            cur.execute("SELECT status FROM conversations WHERE id::text=%s", (conv,))
            conv_row = cur.fetchone()
            cur.execute("SELECT type, data->>'title' FROM cards WHERE conv_id=%s", (conv,))
            card = cur.fetchone()
    finally:
        conn.close()
    assert status == "used"
    assert decided_by == "auto-rule"
    assert "threshold" in reason
    assert receipt is not None  # INVARIANT used ⟺ receipt

    assert conv_row is None or conv_row[0] != "waiting_approval"

    assert card is not None
    assert card[0] == "document"
    assert "Automatically approved" in card[1]
    _set_loan("L001", "active")


@requires_db
@pytest.mark.asyncio
async def test_tiered_at_threshold_waits_human(_reset_sse):

    conv = f"gated-boundary-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    h = gated("disburse", None)
    args = {"loan_id": "L001", "amount": 500_000_000}
    out = _payload(await h(args))
    assert out["code"] == "approval_required"
    assert _loan_status("L001") == "active"
    assert _count_approvals(conv) == 1


@requires_db
@pytest.mark.asyncio
async def test_tiered_over_threshold_s3_unchanged(_reset_sse):

    conv = f"gated-over-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    _set_loan("L001", "active")
    h = gated("disburse", None)
    args = {"loan_id": "L001", "amount": 5_000_000_000}
    out = _payload(await h(args))
    assert out["code"] == "approval_required"
    assert _loan_status("L001") == "active"
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM approvals WHERE conv_id=%s", (conv,))
            assert cur.fetchone()[0] == "pending"
            cur.execute("SELECT type FROM cards WHERE conv_id=%s", (conv,))
            assert cur.fetchone()[0] == "approval"

    finally:
        conn.close()


@requires_db
@pytest.mark.asyncio
async def test_tiered_auto_inner_throw_rollback_no_ticket(_reset_sse):

    conv = f"gated-auto-nf-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    h = gated("disburse", None)
    args = {"loan_id": "NONEXISTENT", "amount": 400_000_000}
    out = _payload(await h(args))
    assert out["code"] == "gated_error"  # inner throw → error 4-field

    assert _count_approvals(conv) == 0, "Expected invariant was not satisfied at source line 362."
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM cards WHERE conv_id=%s", (conv,))
            assert cur.fetchone()[0] == 0, "Expected invariant was not satisfied at source line 367."
    finally:
        conn.close()
