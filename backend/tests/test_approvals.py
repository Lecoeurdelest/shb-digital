from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.db.config import DATABASE_URL
from app.main import app
from app.orch import gated, registry, room, store_approvals
from app.orch.main_prompts import _build_event_prompt
from app.sse import bus

from .conftest import requires_db

client = TestClient(app)


def _admin_cookie():
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    return r.cookies


async def _make_pending(conv: str) -> str:
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


def _set_loan(lid: str, st: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE loans SET status=%s WHERE loan_id=%s", (st, lid))
        conn.commit()
    finally:
        conn.close()


def test_prompt_approved_says_action_not_ticket_id():
    p = _build_event_prompt(
        "approval_decided",
        {"action": "disburse", "decision": "approved", "payload": {"loan_id": "L001", "amount": 5000000000}},
    )
    assert "approved" in p and "Dispatch" in p and "operations" in p
    assert "approval_id" not in p


def test_prompt_rejected_says_no_execute():
    p = _build_event_prompt(
        "approval_decided",
        {"action": "disburse", "decision": "rejected", "payload": {"loan_id": "L001"}},
    )
    assert "rejected" in p and "DO NOT execute" in p


def test_prompt_rejected_with_reason_verbatim():

    p = _build_event_prompt(
        "approval_decided",
        {
            "action": "disburse",
            "decision": "rejected",
            "payload": {"loan_id": "L001"},
            "reason": "DSCR is below the 1.2 threshold; additional collateral is required",
        },
    )
    assert "rejected" in p and "DO NOT execute" in p
    assert "DSCR is below the 1.2 threshold; additional collateral is required" in p
    assert "verbatim" in p


def test_prompt_rejected_no_reason_no_none():

    for data in (
        {"action": "disburse", "decision": "rejected", "payload": {"loan_id": "L001"}},
        {"action": "disburse", "decision": "rejected", "payload": {"loan_id": "L001"}, "reason": None},
        {"action": "disburse", "decision": "rejected", "payload": {"loan_id": "L001"}, "reason": "  "},  # whitespace
    ):
        p = _build_event_prompt("approval_decided", data)
        assert "rejected" in p and "None" not in p
        assert "did not provide a specific reason" in p


def test_valid_decision():
    assert store_approvals.valid_decision("approved")
    assert store_approvals.valid_decision("rejected")
    assert not store_approvals.valid_decision("maybe")


@requires_db
@pytest.mark.asyncio
async def test_decide_atomic_pending_to_approved():
    conv = f"appr-decide-{uuid4()}"
    aid = await _make_pending(conv)
    decided = await store_approvals.decide(aid, "approved", "admin", "approved")
    assert decided is not None
    assert decided["status"] == "approved"
    assert decided["decided_by"] == "admin"
    assert decided["reason"] == "approved"
    assert decided["conv_id"] == conv


@requires_db
@pytest.mark.asyncio
async def test_decide_twice_second_none_no_double_wake():
    conv = f"appr-twice-{uuid4()}"
    aid = await _make_pending(conv)
    d1 = await store_approvals.decide(aid, "approved", "admin", None)
    d2 = await store_approvals.decide(aid, "approved", "admin2", None)
    assert d1 is not None
    assert d2 is None


@requires_db
@pytest.mark.asyncio
async def test_decide_rejected():
    conv = f"appr-rej-{uuid4()}"
    aid = await _make_pending(conv)
    decided = await store_approvals.decide(aid, "rejected", "admin", "ineligible")
    assert decided["status"] == "rejected"


@requires_db
@pytest.mark.asyncio
async def test_list_pending():
    conv = f"appr-list-{uuid4()}"
    aid = await _make_pending(conv)
    pend = await store_approvals.list_pending(conv)
    assert len(pend) == 1
    assert pend[0]["id"] == aid
    assert pend[0]["status"] == "pending"


@requires_db
@pytest.mark.asyncio
async def test_approval_exists():
    conv = f"appr-exist-{uuid4()}"
    aid = await _make_pending(conv)
    assert await store_approvals.approval_exists(aid)
    assert not await store_approvals.approval_exists("00000000-0000-0000-0000-000000000000")


@pytest.mark.asyncio
async def test_emit_and_wake_reuses_handle_room_event():
    registry.reset_room("wake-t32")
    seen = []

    async def tr(conv_id, event, data):
        seen.append((event, data.get("action"), data.get("decision")))

    room.set_turn_runner(tr)
    try:
        from app.api.approvals import _emit_and_wake

        _emit_and_wake(
            {
                "id": "a1",
                "conv_id": "wake-t32",
                "action": "disburse",
                "status": "approved",
                "decided_by": "admin",
                "reason": None,
                "payload": {"loan_id": "L001"},
            }
        )
        await asyncio.sleep(0.05)
        assert seen == [("approval_decided", "disburse", "approved")]
    finally:
        room.set_turn_runner(None)
        registry.reset_room("wake-t32")


@pytest.mark.asyncio
async def test_emit_and_wake_carries_reason_in_payload():

    registry.reset_room("wake-reason")
    captured = {}

    async def tr(conv_id, event, data):
        captured.update(data)

    room.set_turn_runner(tr)
    try:
        from app.api.approvals import _emit_and_wake

        _emit_and_wake(
            {
                "id": "a2",
                "conv_id": "wake-reason",
                "action": "disburse",
                "status": "rejected",
                "decided_by": "admin",
                "reason": "Branch authority limit exceeded",
                "payload": {"loan_id": "L001"},
            }
        )
        await asyncio.sleep(0.05)
        assert captured.get("reason") == "Branch authority limit exceeded"
        assert captured.get("decision") == "rejected"
    finally:
        room.set_turn_runner(None)
        registry.reset_room("wake-reason")


@requires_db
def test_api_decide_bad_decision_400():
    cookies = _admin_cookie()
    r = client.post(f"/api/approvals/{uuid4()}/decide", json={"decision": "maybe"}, cookies=cookies)
    assert r.status_code == 400
    assert r.json()["code"] == "bad_decision"


@requires_db
def test_api_decide_not_found_404():
    cookies = _admin_cookie()
    r = client.post(f"/api/approvals/{uuid4()}/decide", json={"decision": "approved"}, cookies=cookies)
    assert r.status_code == 404
    assert r.json()["code"] == "not_found"


@requires_db
def test_api_decide_malformed_uuid_404_not_500():

    cookies = _admin_cookie()
    r = client.post("/api/approvals/nonexistent-xyz/decide", json={"decision": "approved"}, cookies=cookies)
    assert r.status_code == 404, f"malformed approval_id must return 404, not 500; got {r.status_code}"
    assert r.json()["code"] == "not_found"


@requires_db
@pytest.mark.asyncio
async def test_api_decide_already_decided_409():
    conv = f"appr-409-{uuid4()}"
    aid = await _make_pending(conv)
    await store_approvals.decide(aid, "approved", "admin", None)
    cookies = _admin_cookie()
    r = client.post(f"/api/approvals/{aid}/decide", json={"decision": "approved"}, cookies=cookies)
    assert r.status_code == 409
    assert r.json()["code"] == "approval_already_decided"


def test_api_list_bad_status_400():
    cookies = _admin_cookie()
    r = client.get("/api/approvals?status=used", cookies=cookies)
    assert r.status_code == 400
    assert r.json()["code"] == "bad_status"


def test_api_approvals_requires_auth_no_cookie_401():

    fresh = TestClient(app)
    r = fresh.get("/api/approvals")
    assert r.status_code == 401


@requires_db
@requires_db
def test_api_approvals_customer_forbidden_D56():

    r = client.post("/api/auth/login", json={"username": "c001", "password": "c001"})
    if r.status_code != 200:
        pytest.skip("seed customer account is unavailable")
    r2 = client.get("/api/approvals?status=pending", cookies=r.cookies)
    assert r2.status_code == 403
    assert r2.json()["code"] == "forbidden"


@pytest.mark.asyncio
async def test_emit_and_wake_guarded_logs_not_swallow(caplog):

    import logging

    registry.reset_room("wake-err")

    async def boom_runner(conv_id, event, data):
        raise RuntimeError("demo resume failure")

    room.set_turn_runner(boom_runner)
    try:
        from app.api.approvals import _emit_and_wake

        with caplog.at_level(logging.ERROR, logger="api.approvals"):
            _emit_and_wake(
                {
                    "id": "a1",
                    "conv_id": "wake-err",
                    "action": "disburse",
                    "status": "approved",
                    "decided_by": "admin",
                    "reason": None,
                    "payload": {"loan_id": "L001"},
                }
            )
            await asyncio.sleep(0.05)
        assert any("failed to resume after approval decision" in r.message for r in caplog.records), (
            "resume failures must be logged"
        )
    finally:
        room.set_turn_runner(None)
        registry.reset_room("wake-err")


def _payload(env: dict) -> dict:
    return json.loads(env["content"][0]["text"])
