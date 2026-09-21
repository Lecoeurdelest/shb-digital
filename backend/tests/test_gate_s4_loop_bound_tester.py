from __future__ import annotations

import asyncio
import os
import uuid

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db
from .conftest import wait_for_conversation_idle as _wait_for_conversation_idle

_LIVE = os.environ.get("RUN_LIVE_SDK") == "1"


def _guard_b_landed() -> bool:

    try:
        from app.orch import store_approvals

        return hasattr(store_approvals, "MAX_EXEC_ATTEMPTS")
    except Exception:
        return False


pytestmark = [
    requires_db,
    pytest.mark.skipif(not _LIVE, reason="live SDK opt-in: RUN_LIVE_SDK=1"),
    pytest.mark.skipif(
        not _guard_b_landed(), reason="T4-0 is unavailable because store_approvals lacks MAX_EXEC_ATTEMPTS"
    ),
]


LOAN_HAPPY = ("L109", "C022", 20_000_000)
LOAN_FAIL_BEN = ("L110", "C022", 20_000_000)
LOAN_FAIL_TAM = ("L111", "C023", 50_000_000)


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
    assert r.status_code == 200, "Login must succeed."
    r2 = await client.post("/api/conversations", json={"title": title})
    assert r2.status_code == 201, "Case creation must succeed."
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
    pytest.fail(f"No approval card appeared after {timeout_s}s (conv_id={conv_id})")


@pytest.mark.asyncio
async def test_gate_s4_happy_path_no_regression():

    loan_id, owner_id, amount = LOAN_HAPPY
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s4-happy-no-regress")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": _disburse_prompt(loan_id, owner_id, amount)},
                )
                assert r.status_code == 202

                approval_id = await _wait_for_approval_pending(client, conv_id)

                r_decide = await client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
                assert r_decide.status_code == 200

                await _wait_for_conversation_idle(client, conv_id, timeout_s=90.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_id,))
                    assert cur.fetchone()[0] == "disbursed", "The happy path must complete disbursement."
                    cur.execute("SELECT status, receipt, exec_attempts FROM approvals WHERE id=%s", (approval_id,))
                    row = cur.fetchone()
                    assert row[0] == "used"
                    assert row[1] is not None

                    from app.orch.store_approvals import MAX_EXEC_ATTEMPTS

                    assert row[2] < MAX_EXEC_ATTEMPTS, "The happy path must remain below the retry limit."
                finally:
                    conn.close()
                _restore_state(loan_id, conv_id)
    except AssertionError:
        raise
    finally:
        if conv_id is None:
            _restore_state(loan_id)


@pytest.mark.asyncio
async def test_gate_s4_fail_persistent_stops_at_bound():

    loan_id, owner_id, amount = LOAN_FAIL_BEN
    fake_loan_id = f"GHOST-{uuid.uuid4().hex[:8]}"
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s4-fail-persistent")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": _disburse_prompt(fake_loan_id, owner_id, amount)},
                )
                assert r.status_code == 202

                approval_id = await _wait_for_approval_pending(client, conv_id)

                r_decide = await client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
                assert r_decide.status_code == 200

                await _wait_for_conversation_idle(client, conv_id, timeout_s=180.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status, receipt, exec_attempts FROM approvals WHERE id=%s", (approval_id,))
                    row = cur.fetchone()
                    from app.orch.store_approvals import MAX_EXEC_ATTEMPTS

                    assert row[2] == MAX_EXEC_ATTEMPTS, "Persistent failure must stop exactly at the retry limit."
                    assert row[1] is None, "Persistent failure must not produce a receipt."
                    assert row[0] not in ("used", "approved"), "The approval must leave all redispatchable states."

                    cur.execute(
                        "SELECT count(*) FROM tasks WHERE conv_id=%s AND role='operations'",
                        (conv_id,),
                    )
                    task_count = cur.fetchone()[0]

                    assert task_count <= 2 + MAX_EXEC_ATTEMPTS, "The operations task count must remain bounded."
                finally:
                    conn.close()
                _restore_state(loan_id, conv_id)
    except AssertionError:
        raise
    finally:
        if conv_id is None:
            _restore_state(loan_id)


@pytest.mark.asyncio
async def test_gate_s4_fail_transient_then_success_not_over_bounded():

    loan_id, owner_id, amount = LOAN_FAIL_TAM
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s4-fail-transient")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": _disburse_prompt(loan_id, owner_id, amount)},
                )
                assert r.status_code == 202

                approval_id = await _wait_for_approval_pending(client, conv_id)

                r_decide = await client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
                assert r_decide.status_code == 200

                await _wait_for_conversation_idle(client, conv_id, timeout_s=120.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_id,))
                    assert cur.fetchone()[0] == "disbursed", "A valid loan must succeed without over-bounding retries."
                finally:
                    conn.close()
                _restore_state(loan_id, conv_id)
    except AssertionError:
        raise
    finally:
        if conv_id is None:
            _restore_state(loan_id)
