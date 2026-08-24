"""S19 D-71 webhook doorbell: allowlist, retry hữu hạn và hook hậu commit."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import httpx
import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.api import approvals as approvals_api
from app.db.config import DATABASE_URL
from app.main import app
from app.notify import channels
from app.orch import gated, gated_postcommit, registry

from .conftest import requires_db


def _approval(status: str = "pending") -> dict[str, Any]:
    return {
        "id": "018f0000-0000-7000-8000-000000000001",
        "approval_id": "ignored-secondary-id",
        "conv_id": "12345678-secret-tail",
        "action": "disburse",
        "status": status,
        "payload": {
            "loan_id": "L001-SECRET",
            "amount": 500_000_000,
            "customer_name": "Nguyễn Văn Bí Mật",
        },
        "display": {"owner_id": "C001-SECRET"},
        "receipt": {"bank_account": "0123456789"},
        "reason": "CIC secret",
        "decided_by": "director@example.com",
    }


def _fake_client(monkeypatch, outcomes: list[int | Exception]):
    seen: dict[str, Any] = {"calls": [], "timeouts": []}

    class FakeClient:
        def __init__(self, *, timeout: float):
            seen["timeouts"].append(timeout)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, *, json: dict[str, Any]):
            seen["calls"].append((url, json))
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return SimpleNamespace(status_code=outcome)

    monkeypatch.setattr(channels.httpx, "AsyncClient", FakeClient)
    return seen


async def _drain_tasks() -> None:
    tasks = tuple(channels._bg_tasks)
    if tasks:
        await __import__("asyncio").gather(*tasks)
    assert not channels._bg_tasks


@pytest.mark.asyncio
async def test_generic_default_exact_shape_and_nested_pii_absent(monkeypatch):
    monkeypatch.setenv("SHB_NOTIFY_WEBHOOK_URL", "https://hooks.example/token-secret")
    monkeypatch.delenv("SHB_NOTIFY_CHANNEL", raising=False)
    monkeypatch.setenv("SHB_NOTIFY_INCLUDE_AMOUNT", "01")  # chỉ đúng chuỗi "1" mới bật
    monkeypatch.setattr(channels, "app_url", lambda: "https://bank.example/")
    seen = _fake_client(monkeypatch, [204])

    channels.notify_channel_approval_pending(_approval())
    await _drain_tasks()

    assert seen["timeouts"] == [5.0]
    assert seen["calls"] == [
        (
            "https://hooks.example/token-secret",
            {
                "action": "disburse",
                "conv_id": "12345678",
                "status": "pending",
                "deep_link": "https://bank.example/?tab=approvals&approval=018f0000-0000-7000-8000-000000000001",
            },
        )
    ]
    nested = json.dumps(seen["calls"][0][1], ensure_ascii=False)
    for forbidden in (
        "Nguyễn",
        "L001-SECRET",
        "C001-SECRET",
        "0123456789",
        "CIC secret",
        "director@example.com",
        '"payload"',
        '"display"',
        '"receipt"',
        '"reason"',
        '"decided_by"',
    ):
        assert forbidden not in nested


@pytest.mark.asyncio
async def test_lark_exact_shape_with_amount(monkeypatch):
    monkeypatch.setenv("SHB_NOTIFY_WEBHOOK_URL", "https://open.larksuite.com/token-secret")
    monkeypatch.setenv("SHB_NOTIFY_CHANNEL", "lark")
    monkeypatch.setenv("SHB_NOTIFY_INCLUDE_AMOUNT", "1")
    monkeypatch.setattr(channels, "app_url", lambda: "https://bank.example")
    seen = _fake_client(monkeypatch, [200])

    channels.notify_channel_approval_decided(_approval("approved"))
    await _drain_tasks()

    assert seen["calls"][0][1] == {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "BANK Digital · Approval doorbell"}},
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "**disburse** · ca `12345678` · approved · 500000000 VND",
                    },
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "Open Control Tower"},
                            "type": "primary",
                            "url": "https://bank.example/?tab=approvals&approval=018f0000-0000-7000-8000-000000000001",
                        }
                    ],
                },
            ],
        },
    }
    nested = json.dumps(seen["calls"][0][1], ensure_ascii=False)
    for forbidden in ("Nguyễn", "L001-SECRET", "C001-SECRET", "0123456789", "CIC secret"):
        assert forbidden not in nested


@pytest.mark.asyncio
async def test_disabled_and_invalid_channel_schedule_nothing(monkeypatch, caplog):
    called = False

    class ShouldNotConstruct:
        def __init__(self, **kwargs):
            nonlocal called
            called = True

    monkeypatch.setattr(channels.httpx, "AsyncClient", ShouldNotConstruct)
    monkeypatch.delenv("SHB_NOTIFY_WEBHOOK_URL", raising=False)
    channels.notify_channel_approval_pending(_approval())
    assert not channels._bg_tasks

    monkeypatch.setenv("SHB_NOTIFY_WEBHOOK_URL", "https://hooks.example/token-secret")
    monkeypatch.setenv("SHB_NOTIFY_CHANNEL", "teams")
    with caplog.at_level(logging.WARNING, logger="notify.channels"):
        channels.notify_channel_approval_pending(_approval())
    assert not channels._bg_tasks
    assert called is False
    assert "token-secret" not in caplog.text


@pytest.mark.asyncio
async def test_retries_500_429_then_success_at_0_1_3(monkeypatch):
    seen = _fake_client(monkeypatch, [500, 429, 200])
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(channels.asyncio, "sleep", fake_sleep)
    event = channels._event_of(_approval(), "pending")
    assert event is not None
    await channels._post_with_retries("https://hooks.example/token-secret", "generic", event, {"safe": True})

    assert len(seen["calls"]) == 3
    assert delays == [1.0, 3.0]


@pytest.mark.asyncio
async def test_network_error_retries_but_other_4xx_drops(monkeypatch):
    request = httpx.Request("POST", "https://hooks.example")
    network = httpx.ReadTimeout("secret response", request=request)
    seen = _fake_client(monkeypatch, [network, 200])
    monkeypatch.setattr(channels.asyncio, "sleep", lambda seconds: _no_wait())
    event = channels._event_of(_approval(), "rejected")
    assert event is not None
    await channels._post_with_retries("https://hooks.example/token-secret", "generic", event, {})
    assert len(seen["calls"]) == 2

    for status_code in (400, 600):
        seen = _fake_client(monkeypatch, [status_code])
        await channels._post_with_retries("https://hooks.example/token-secret", "generic", event, {})
        assert len(seen["calls"]) == 1


async def _no_wait() -> None:
    return None


@pytest.mark.asyncio
async def test_failure_logs_only_safe_metadata(monkeypatch, caplog):
    _fake_client(monkeypatch, [500, 500, 500])
    monkeypatch.setattr(channels.asyncio, "sleep", lambda seconds: _no_wait())
    event = channels._event_of(_approval(), "approved")
    assert event is not None
    with caplog.at_level(logging.WARNING, logger="notify.channels"):
        await channels._post_with_retries(
            "https://hooks.example/token-secret", "lark", event, _lark_fixture_with_secret()
        )
    assert "channel=lark" in caplog.text
    assert "event_status=approved" in caplog.text
    assert "conv=12345678" in caplog.text
    for forbidden in ("token-secret", "L001-SECRET", "Nguyễn", "body-secret", "hooks.example"):
        assert forbidden not in caplog.text


def _lark_fixture_with_secret() -> dict[str, str]:
    return {"body": "body-secret"}


def test_postcommit_skips_auto_and_calls_human_once(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(channels, "notify_channel_approval_pending", lambda row: seen.append(row["approval_id"]))

    gated_postcommit.notify_pending_doorbell({"auto": True, "approval_id": "auto"})
    gated_postcommit.notify_pending_doorbell({"approval_id": "human"})

    assert seen == ["human"]


@requires_db
@pytest.mark.asyncio
async def test_below_threshold_auto_path_emits_no_pending_doorbell(monkeypatch):
    token = uuid4().hex[:12]
    conv, loan, owner = f"s19-auto-{token}", f"LNA{token}", f"ONA{token}"
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO loans(loan_id,owner_id,status) VALUES(%s,%s,'active')", (loan, owner))
    conn.close()

    seen: list[str] = []
    monkeypatch.setattr(channels, "notify_channel_approval_pending", lambda row: seen.append("pending"))
    monkeypatch.setattr(gated, "auto_approve_threshold", lambda: 500_000_000)
    monkeypatch.setattr(gated, "_emit_approval", lambda row: None)
    monkeypatch.setattr(gated, "_notify_disbursed", lambda conv_id, receipt: None)
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    try:
        result = await gated.gated("disburse", None)({"loan_id": loan, "amount": 50_000_000})
        body = json.loads(result["content"][0]["text"])
        assert body["auto_approved"] is True
        assert seen == []
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv,))
            cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv,))
            cur.execute("DELETE FROM loans WHERE loan_id=%s", (loan,))
        conn.close()


@pytest.mark.asyncio
async def test_pending_hook_runs_after_sse_and_not_on_replay(monkeypatch):
    order: list[str] = []
    human = gated._GatedResult(
        {"code": "approval_required"},
        emit={"approval_id": "human", "conv_id": "conv", "action": "disburse", "payload": {}},
    )
    replay = gated._GatedResult({"code": "approval_pending"})
    results = iter((human, replay))
    monkeypatch.setattr(gated, "auto_approve_threshold", lambda: 500_000_000)
    monkeypatch.setattr(gated, "_gated_txn", lambda *args: next(results))
    monkeypatch.setattr(gated, "_emit_approval", lambda row: order.append("sse"))
    monkeypatch.setattr(gated, "_notify_pending_doorbell", lambda row: order.append("channel"))
    registry.CTX_CONV.set("conv")
    registry.CTX_TASK.set("")

    handler = gated.gated("disburse", None)
    await handler({"loan_id": "L001", "amount": 600_000_000})
    await handler({"loan_id": "L001", "amount": 600_000_000})

    assert order == ["sse", "channel"]


@requires_db
def test_decide_still_200_when_channel_adapter_raises(monkeypatch):
    conv = f"s19-channel-{uuid4()}"
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO approvals (conv_id,action,payload,payload_hash,status) "
                "VALUES (%s,'disburse','{}',%s,'pending') RETURNING id",
                (conv, uuid4().hex[:16]),
            )
            approval_id = str(cur.fetchone()[0])
    finally:
        conn.close()

    order: list[str] = []
    monkeypatch.setattr(approvals_api, "_emit_and_wake", lambda row: order.append("sse"))
    monkeypatch.setattr(approvals_api, "_notify_decided", lambda row: order.append("email"))

    def channel_boom(row):
        order.append("channel")
        raise RuntimeError("webhook token-secret")

    monkeypatch.setattr(channels, "notify_channel_approval_decided", channel_boom)
    client = TestClient(app)
    cookies = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).cookies
    try:
        response = client.post(
            f"/api/approvals/{approval_id}/decide",
            json={"decision": "approved"},
            cookies=cookies,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "approved"
        assert order == ["sse", "channel", "email"]
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DELETE FROM shadow_reviews WHERE conv_id=%s", (conv,))
            cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv,))
        conn.close()
