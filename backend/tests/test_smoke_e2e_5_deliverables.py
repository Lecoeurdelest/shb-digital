from __future__ import annotations

import asyncio
import os
import subprocess
import sys

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db

_LIVE = os.environ.get("RUN_LIVE_SDK") == "1"

pytestmark = [
    requires_db,
    pytest.mark.skipif(not _LIVE, reason="Optional integration prerequisite is unavailable."),
]


LOAN_AUTO = ("L109", "C022", 300_000_000)
LOAN_MANUAL = ("L111", "C023", 700_000_000)


_SURVEY_PROMPT = (
    "Workshop X Mechanical LLC (B001) seeks a 5 billion VND loan to EXPAND PRODUCTION, secured by "
    "factory property COL06. Perform a quick overview of credit health, collateral legality, and suitable "
    "loan products. This is not yet a formal application."
)


def _disburse_prompt(loan_id: str, owner_id: str, amount: int) -> str:
    return (
        f"Customer {owner_id} (loan {loan_id}) has an approved limit. Ask Operations to disburse "
        f"{amount} VND immediately for loan {loan_id}, without reassessing credit or legal."
    )


def _reset_demo() -> None:

    result = subprocess.run(
        [sys.executable, "-m", "app.db.reset_demo"],
        cwd=str(__file__).rsplit("/tests/", 1)[0],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, "Expected invariant was not satisfied at source line 52."


def _restore_loans(loan_ids: list[str]) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        for loan_id in loan_ids:
            cur.execute("UPDATE loans SET status='active' WHERE loan_id=%s", (loan_id,))
        conn.commit()
    finally:
        conn.close()


def _cleanup_conv(conv_id: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
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
    assert r.status_code == 200, "Expected invariant was not satisfied at source line 82."
    r2 = await client.post("/api/conversations", json={"title": title})
    assert r2.status_code == 201, "Expected invariant was not satisfied at source line 84."
    return r2.json()["id"]


_TERMINAL_TASK_STATUS = {"done", "failed", "timeout"}


async def _wait_for_settled(client: AsyncClient, conv_id: str, timeout_s: float = 180.0) -> dict:

    elapsed = 0.0
    interval = 3.0
    state: dict | None = None
    while elapsed < timeout_s:
        r = await client.get(f"/api/conversations/{conv_id}")
        assert r.status_code == 200
        state = r.json()
        conv_status = state.get("conversation", {}).get("status")
        tasks = state.get("tasks", [])
        if conv_status == "idle" and tasks and all(t.get("status") in _TERMINAL_TASK_STATUS for t in tasks):
            return state
        await asyncio.sleep(interval)
        elapsed += interval
    pytest.fail("Expected condition was not met at source line 106.")


async def _wait_for_approval_pending(client: AsyncClient, conv_id: str, timeout_s: float = 90.0) -> str:
    elapsed = 0.0
    interval = 3.0
    state: dict | None = None
    while elapsed < timeout_s:
        r = await client.get(f"/api/conversations/{conv_id}")
        assert r.status_code == 200
        state = r.json()
        for c in state.get("cards", []):
            if c.get("type") == "approval":
                return c["approval_id"]
        await asyncio.sleep(interval)
        elapsed += interval
    pytest.fail("Expected condition was not met at source line 126.")


@pytest.mark.asyncio
async def test_smoke_5_deliverables_end_to_end():

    loan_auto_id, owner_auto, amount_auto = LOAN_AUTO
    loan_manual_id, owner_manual, amount_manual = LOAN_MANUAL

    _reset_demo()

    conv_survey: str | None = None
    conv_auto: str | None = None
    conv_manual: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=180.0) as client:
                conv_survey = await _login_and_create_conv(client, "smoke-d1-survey")
                r = await client.post(f"/api/conversations/{conv_survey}/chat", json={"content": _SURVEY_PROMPT})
                assert r.status_code == 202, "Expected invariant was not satisfied at source line 145."

                state1 = await _wait_for_settled(client, conv_survey, timeout_s=180.0)
                cards1 = state1.get("cards", [])
                assert len(cards1) > 0, "Expected invariant was not satisfied at source line 149."

                # Deliverable 2a: disburse below 500 million VND and auto-approve immediately.
                conv_auto = await _login_and_create_conv(client, "smoke-d2a-auto-approve")
                r = await client.post(
                    f"/api/conversations/{conv_auto}/chat",
                    json={"content": _disburse_prompt(loan_auto_id, owner_auto, amount_auto)},
                )
                assert r.status_code == 202, "Expected invariant was not satisfied at source line 161."

                await _wait_for_settled(client, conv_auto, timeout_s=90.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_auto_id,))
                    row = cur.fetchone()
                    assert row is not None, "Expected invariant was not satisfied at source line 170."
                    assert row[0] == "disbursed", "Expected invariant was not satisfied at source line 171."
                    cur.execute(
                        "SELECT status, decided_by FROM approvals WHERE conv_id=%s ORDER BY decided_at DESC LIMIT 1",
                        (conv_auto,),
                    )
                    appr_row = cur.fetchone()
                    assert appr_row is not None, "Expected invariant was not satisfied at source line 180."
                    assert appr_row[0] == "used", "Expected invariant was not satisfied at source line 181."
                    assert appr_row[1] == "auto-rule", "Expected invariant was not satisfied at source line 182."
                finally:
                    conn.close()

                conv_manual = await _login_and_create_conv(client, "smoke-d2b-manual-approve")
                r = await client.post(
                    f"/api/conversations/{conv_manual}/chat",
                    json={"content": _disburse_prompt(loan_manual_id, owner_manual, amount_manual)},
                )
                assert r.status_code == 202, "Expected invariant was not satisfied at source line 193."

                approval_id = await _wait_for_approval_pending(client, conv_manual, timeout_s=90.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_manual_id,))
                    assert cur.fetchone()[0] == "active", "Expected invariant was not satisfied at source line 201."
                finally:
                    conn.close()

                r_decide = await client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
                assert r_decide.status_code == 200, "Expected invariant was not satisfied at source line 208."

                await _wait_for_settled(client, conv_manual, timeout_s=90.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_manual_id,))
                    row = cur.fetchone()
                    assert row[0] == "disbursed", "Expected invariant was not satisfied at source line 217."
                    cur.execute("SELECT status, receipt FROM approvals WHERE id=%s", (approval_id,))
                    appr_row = cur.fetchone()
                    assert appr_row[0] == "used", "Expected invariant was not satisfied at source line 223."
                    assert appr_row[1] is not None, "Expected invariant was not satisfied at source line 224."
                finally:
                    conn.close()

                r_audit = await client.get(f"/api/audit?conv_id={conv_survey}")
                assert r_audit.status_code == 200, "Expected invariant was not satisfied at source line 229."
                audit_rows = r_audit.json()
                assert len(audit_rows) >= 1, "Expected invariant was not satisfied at source line 231."
                for row in audit_rows:
                    assert row["tool"], "Expected invariant was not satisfied at source line 236."
                    assert row["actor"] in ("main", "credit", "legal", "operations", "products"), (
                        "Expected invariant was not satisfied at source line 237."
                    )

                r_compare = await client.post(
                    "/api/compare",
                    json={"question": "Can customer C001 borrow 500 million VND?"},
                )
                assert r_compare.status_code == 200, "Expected invariant was not satisfied at source line 245."
                compare_body = r_compare.json()
                assert compare_body.get("single", {}).get("text"), (
                    "Expected invariant was not satisfied at source line 250."
                )
                multi = compare_body.get("multi", {})
                assert multi.get("timeout") or multi.get("tool_calls", 0) > 0, (
                    "Expected invariant was not satisfied at source line 254."
                )

                _restore_loans([loan_auto_id, loan_manual_id])
                for cid in (conv_survey, conv_auto, conv_manual):
                    if cid:
                        _cleanup_conv(cid)
    except AssertionError:
        raise
