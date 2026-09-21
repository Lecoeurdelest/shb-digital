from __future__ import annotations

import asyncio
import os

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db
from .conftest import wait_for_conversation_idle as _wait_for_conversation_idle

_LIVE = os.environ.get("RUN_LIVE_SDK") == "1"

pytestmark = [
    requires_db,
    pytest.mark.skipif(not _LIVE, reason="Optional integration prerequisite is unavailable."),
]


LOAN_HAPPY = ("L102", "C002", 50_000_000)
LOAN_REJECT = ("L103", "C009", 50_000_000)
LOAN_DECIDE_TWICE = ("L104", "C010", 300_000_000)


def _disburse_prompt(loan_id: str, owner_id: str, amount: int) -> str:
    return (
        f"Customer {owner_id} (loan {loan_id}) has an approved limit. Ask Operations to disburse "
        f"{amount} VND immediately for loan {loan_id}, without reassessing credit or legal."
    )


def _restore_state(loan_id: str, conv_id: str | None = None) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE loans SET status='active' WHERE loan_id=%s", (loan_id,))
        if conv_id:
            cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
            cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv_id,))
            cur.execute("DELETE FROM tasks WHERE conv_id=%s", (conv_id,))
            cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
            cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()


async def _login_and_create_conv(client: AsyncClient, title: str) -> str:
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, "Expected invariant was not satisfied at source line 54."
    r2 = await client.post("/api/conversations", json={"title": title})
    assert r2.status_code == 201, "Expected invariant was not satisfied at source line 56."
    return r2.json()["id"]


async def _wait_for_approval_pending(client: AsyncClient, conv_id: str, timeout_s: float = 90.0) -> str:

    elapsed = 0.0
    interval = 3.0
    while elapsed < timeout_s:
        r = await client.get(f"/api/conversations/{conv_id}")
        assert r.status_code == 200
        state = r.json()
        for c in state.get("cards", []):
            if c.get("type") == "approval":
                return c["approval_id"]
        await asyncio.sleep(interval)
        elapsed += interval
    pytest.fail("Expected condition was not met at source line 73.")


@pytest.mark.asyncio
async def test_gate_s3_happy_path_approve_resume_disburse_real():

    loan_id, owner_id, amount = LOAN_HAPPY
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s3-happy-path")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": _disburse_prompt(loan_id, owner_id, amount)},
                )
                assert r.status_code == 202

                approval_id = await _wait_for_approval_pending(client, conv_id)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_id,))
                    loan_status_before = cur.fetchone()[0]
                finally:
                    conn.close()
                assert loan_status_before == "active", "Expected invariant was not satisfied at source line 105."

                r_decide = await client.post(
                    f"/api/approvals/{approval_id}/decide",
                    json={"decision": "approved"},
                )
                assert r_decide.status_code == 200, "Expected invariant was not satisfied at source line 113."
                assert r_decide.json()["status"] == "approved"

                await _wait_for_conversation_idle(client, conv_id, timeout_s=90.0)

                r_state = await client.get(f"/api/conversations/{conv_id}")
                r_state.json()

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_id,))
                    loan_status_after = cur.fetchone()[0]
                    assert loan_status_after == "disbursed", "Expected invariant was not satisfied at source line 126."

                    cur.execute(
                        "SELECT status, receipt FROM approvals WHERE id=%s",
                        (approval_id,),
                    )
                    approval_row = cur.fetchone()
                    assert approval_row[0] == "used", "Expected invariant was not satisfied at source line 140."
                    assert approval_row[1] is not None, "Expected invariant was not satisfied at source line 141."
                finally:
                    conn.close()

                _restore_state(loan_id, conv_id)
    except AssertionError:
        raise
    finally:
        if conv_id is None:
            _restore_state(loan_id)


@pytest.mark.asyncio
async def test_gate_s3_reject_path_no_disburse():

    loan_id, owner_id, amount = LOAN_REJECT
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s3-reject-path")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": _disburse_prompt(loan_id, owner_id, amount)},
                )
                assert r.status_code == 202

                approval_id = await _wait_for_approval_pending(client, conv_id)

                r_decide = await client.post(
                    f"/api/approvals/{approval_id}/decide",
                    json={"decision": "rejected", "reason": "test rejection — ineligible"},
                )
                assert r_decide.status_code == 200
                assert r_decide.json()["status"] == "rejected"

                await _wait_for_conversation_idle(client, conv_id, timeout_s=90.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_id,))
                    assert cur.fetchone()[0] == "active", "Expected invariant was not satisfied at source line 184."

                    cur.execute("SELECT status, receipt FROM approvals WHERE id=%s", (approval_id,))
                    row = cur.fetchone()
                    assert row[0] == "rejected"
                    assert row[1] is None, "Expected invariant was not satisfied at source line 189."
                finally:
                    conn.close()

                _restore_state(loan_id, conv_id)
    except AssertionError:
        raise
    finally:
        if conv_id is None:
            _restore_state(loan_id)


@pytest.mark.asyncio
async def test_gate_s3_decide_twice_returns_409_no_double_wake():

    loan_id, owner_id, amount = LOAN_DECIDE_TWICE
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s3-decide-twice")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": _disburse_prompt(loan_id, owner_id, amount)},
                )
                assert r.status_code == 202
                approval_id = await _wait_for_approval_pending(client, conv_id)

                r1 = await client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
                assert r1.status_code == 200

                r2 = await client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
                assert r2.status_code == 409
                body = r2.json()
                assert body["code"] == "approval_already_decided"

                await _wait_for_conversation_idle(client, conv_id, timeout_s=90.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_id,))
                    assert cur.fetchone()[0] == "disbursed"
                    cur.execute(
                        "SELECT count(*) FROM approvals WHERE conv_id=%s AND status='used'",
                        (conv_id,),
                    )
                    assert cur.fetchone()[0] == 1, "Expected invariant was not satisfied at source line 237."
                finally:
                    conn.close()

                _restore_state(loan_id, conv_id)
    except AssertionError:
        raise
    finally:
        if conv_id is None:
            _restore_state(loan_id)
