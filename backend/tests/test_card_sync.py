"""[BACKEND] Test T3-2 gap: decide → sync card.data.status (reload-safe). CÙNG tx decide."""

from __future__ import annotations

from uuid import uuid4

import psycopg2
import pytest

from app.db.config import DATABASE_URL
from app.orch import gated, registry, store_approvals
from app.sse import bus
from tests.conftest import requires_db


def _set_loan(lid, st):
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE loans SET status=%s WHERE loan_id=%s", (st, lid))
        conn.commit()
    finally:
        conn.close()


async def _make_pending(conv):
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    bus.subscribe(conv)
    _set_loan("L001", "active")
    await gated.gated("disburse", None)({"loan_id": "L001", "amount": 5000000000})
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM approvals WHERE conv_id=%s AND status='pending'", (conv,))
            return str(cur.fetchone()[0])
    finally:
        conn.close()


def _card_status(conv, approval_id):
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT data->>'status', data->>'decided_by', data->>'reason' FROM cards "
                "WHERE conv_id=%s AND type='approval' AND data->>'approval_id'=%s",
                (conv, approval_id),
            )
            return cur.fetchone()
    finally:
        conn.close()


@requires_db
@pytest.mark.asyncio
async def test_decide_approved_syncs_card_data():
    conv = f"card-sync-appr-{uuid4()}"
    aid = await _make_pending(conv)
    # trước decide: card pending
    assert _card_status(conv, aid)[0] == "pending"
    decided = await store_approvals.decide(aid, "approved", "admin", "ok duyệt")
    # sau decide: card.data.status = approved + decided_by + reason (CÙNG tx)
    st, by, reason = _card_status(conv, aid)
    assert st == "approved"
    assert by == "admin"
    assert reason == "ok duyệt"
    # _card_row kèm trong decided (cho emit SSE) — có id
    assert decided["_card_row"] is not None
    assert str(decided["_card_row"]["id"])


@requires_db
@pytest.mark.asyncio
async def test_decide_rejected_syncs_card_data():
    conv = f"card-sync-rej-{uuid4()}"
    aid = await _make_pending(conv)
    await store_approvals.decide(aid, "rejected", "admin", "thiếu điều kiện")
    st, by, reason = _card_status(conv, aid)
    assert st == "rejected"
    assert reason == "thiếu điều kiện"
