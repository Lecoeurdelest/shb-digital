from __future__ import annotations

import pytest

from app.orch import main_session, registry


@pytest.fixture(autouse=True)
def _clean():
    registry.reset_all()
    yield
    registry.reset_all()


class _Spy:
    def __init__(self):
        self.dispatched: list[tuple] = []
        self.claimed: list[str] = []
        self.marked_failed: list[str] = []

    async def dispatch(self, conv_id, role, title, brief):
        self.dispatched.append((conv_id, role, title, brief))
        return {"created": True, "role": role, "status": "running"}


def _patch(monkeypatch, grant, spy):
    async def fake_peek(conv_id):
        return grant

    async def fake_claim(approval_id):
        spy.claimed.append(approval_id)
        return (grant.get("exec_attempts", 0) + 1) if grant else 1

    async def fake_mark_failed(approval_id):
        spy.marked_failed.append(approval_id)

    monkeypatch.setattr("app.orch.store_approvals.peek_grant", fake_peek)
    monkeypatch.setattr("app.orch.store_approvals.claim_exec_attempt", fake_claim)
    monkeypatch.setattr("app.orch.store_approvals.mark_exec_failed", fake_mark_failed)
    monkeypatch.setattr("app.orch.dispatch.orch_dispatch_impl", spy.dispatch)


@pytest.mark.asyncio
async def test_A_approved_role_running_skips_main_no_dispatch(monkeypatch):
    spy = _Spy()
    _patch(monkeypatch, grant=None, spy=spy)
    registry.register_running("conv1", "operations", "task-ops-1")

    handled = await main_session._resume_dispatch_guard(
        "conv1", "approval_decided", {"action": "disburse", "decision": "approved", "payload": {"loan_id": "L1"}}
    )
    assert handled is True
    assert spy.dispatched == []


@pytest.mark.asyncio
async def test_Aprime_approved_role_free_normal_path(monkeypatch):

    spy = _Spy()
    _patch(monkeypatch, grant=None, spy=spy)

    handled = await main_session._resume_dispatch_guard(
        "conv1", "approval_decided", {"action": "disburse", "decision": "approved", "payload": {"loan_id": "L1"}}
    )
    assert handled is False


@pytest.mark.asyncio
async def test_reject_never_handled(monkeypatch):

    spy = _Spy()
    _patch(monkeypatch, grant=None, spy=spy)
    registry.register_running("conv1", "operations", "task-ops-1")

    handled = await main_session._resume_dispatch_guard(
        "conv1", "approval_decided", {"action": "disburse", "decision": "rejected", "payload": {"loan_id": "L1"}}
    )
    assert handled is False
    assert spy.dispatched == []


@pytest.mark.asyncio
async def test_B_task_done_with_grant_redispatches_and_skips(monkeypatch):
    grant = {
        "id": "ap1",
        "action": "disburse",
        "payload": {"loan_id": "L1", "amount": 5000000000},
        "status": "approved",
        "exec_attempts": 0,
    }
    spy = _Spy()
    _patch(monkeypatch, grant=grant, spy=spy)
    # operations is no longer running because _report unregisters it before task_done.

    handled = await main_session._resume_dispatch_guard("conv1", "task_done", {"role": "operations", "outcome": "done"})
    assert handled is True  # Skip MAIN reporting; the second operations task will report completion.
    assert len(spy.dispatched) == 1
    conv_id, role, title, brief = spy.dispatched[0]
    assert conv_id == "conv1" and role == "operations"
    assert "disburse" in brief and "APPROVED" in brief
    assert "loan_id=L1" in brief
    assert spy.claimed == ["ap1"]  # T4-0 increments only when redispatching the matching role.


@pytest.mark.asyncio
async def test_Bprime_task_done_no_grant_normal_report(monkeypatch):

    spy = _Spy()
    _patch(monkeypatch, grant=None, spy=spy)

    handled = await main_session._resume_dispatch_guard("conv1", "task_done", {"role": "operations", "outcome": "done"})
    assert handled is False
    assert spy.dispatched == []


@pytest.mark.asyncio
async def test_B_grant_but_role_still_running_no_double(monkeypatch):

    grant = {"id": "ap1", "action": "disburse", "payload": {"loan_id": "L1"}, "status": "approved", "exec_attempts": 0}
    spy = _Spy()
    _patch(monkeypatch, grant=grant, spy=spy)
    registry.register_running("conv1", "operations", "task-ops-still")

    handled = await main_session._resume_dispatch_guard("conv1", "task_done", {"role": "credit", "outcome": "done"})
    assert handled is False
    assert spy.dispatched == []
    assert spy.claimed == []


@pytest.mark.asyncio
async def test_B_grant_wrong_done_role_no_dispatch(monkeypatch):

    grant = {"id": "ap1", "action": "disburse", "payload": {"loan_id": "L1"}, "status": "approved", "exec_attempts": 0}
    spy = _Spy()
    _patch(monkeypatch, grant=grant, spy=spy)

    handled = await main_session._resume_dispatch_guard("conv1", "task_done", {"role": "credit", "outcome": "done"})
    assert handled is False
    assert spy.dispatched == []
    assert spy.claimed == []


@pytest.mark.asyncio
async def test_T40_exec_attempts_below_max_still_redispatches(monkeypatch):

    from app.orch import store_approvals

    grant = {
        "id": "ap1",
        "action": "disburse",
        "payload": {"loan_id": "L1"},
        "status": "approved",
        "exec_attempts": store_approvals.MAX_EXEC_ATTEMPTS - 1,
    }
    spy = _Spy()
    _patch(monkeypatch, grant=grant, spy=spy)

    handled = await main_session._resume_dispatch_guard("conv1", "task_done", {"role": "operations", "outcome": "done"})
    assert handled is True
    assert len(spy.dispatched) == 1
    assert spy.claimed == ["ap1"]
    assert spy.marked_failed == []


@pytest.mark.asyncio
async def test_T40_exec_attempts_at_max_stops_and_marks_failed(monkeypatch):

    from app.orch import store_approvals

    grant = {
        "id": "ap1",
        "action": "disburse",
        "payload": {"loan_id": "L1"},
        "status": "approved",
        "exec_attempts": store_approvals.MAX_EXEC_ATTEMPTS,
    }
    spy = _Spy()
    _patch(monkeypatch, grant=grant, spy=spy)

    data = {"role": "operations", "outcome": "done"}
    handled = await main_session._resume_dispatch_guard("conv1", "task_done", data)
    assert handled is False
    assert spy.dispatched == []
    assert spy.claimed == []
    assert spy.marked_failed == ["ap1"]

    assert data.get("exec_failed") is not None
    assert data["exec_failed"]["attempts"] == store_approvals.MAX_EXEC_ATTEMPTS
    assert data["exec_failed"]["action"] == "disburse"


def test_prompt_exec_failed_deterministic():
    """exec_failed produces an explicit manual-review prompt without model inference."""
    from app.orch.main_prompts import _build_event_prompt

    p = _build_event_prompt(
        "task_done",
        {
            "role": "operations",
            "outcome": "done",
            "exec_failed": {"action": "disburse", "attempts": 3, "payload_summary": "loan_id=L1"},
        },
    )
    assert "failed persistently" in p and "manual review" in p and "3 retries" in p
    assert "DO NOT retry automatically" in p


def test_prompt_disburse_done_dan_khong_present_lai():
    """T4-5 prevents MAIN from presenting a duplicate receipt card."""
    from app.orch.main_prompts import _build_event_prompt

    p = _build_event_prompt(
        "task_done",
        {
            "role": "operations",
            "outcome": "done",
            "result_summary": '{"disbursed": true, "loan_id": "L001", "amount": 5000000000}',
            "board": [],
        },
    )
    assert "Do NOT present another card" in p
    assert "one short sentence" in p


def test_prompt_non_disburse_task_done_normal():

    from app.orch.main_prompts import _build_event_prompt

    p_credit = _build_event_prompt(
        "task_done",
        {"role": "credit", "outcome": "done", "result_summary": "DSCR 1.5 is eligible", "board": []},
    )
    assert "DO NOT present" not in p_credit

    p_ops_plan = _build_event_prompt(
        "task_done",
        {"role": "operations", "outcome": "done", "result_summary": '{"steps": [...], "totalDays": 5}', "board": []},
    )
    assert "DO NOT present" not in p_ops_plan


@pytest.mark.asyncio
async def test_T40_exhausted_wrong_role_no_mark(monkeypatch):

    grant = {
        "id": "ap1",
        "action": "disburse",
        "payload": {"loan_id": "L1"},
        "status": "approved",
        "exec_attempts": 3,
    }
    spy = _Spy()
    _patch(monkeypatch, grant=grant, spy=spy)

    handled = await main_session._resume_dispatch_guard("conv1", "task_done", {"role": "credit", "outcome": "done"})
    assert handled is False
    assert spy.marked_failed == []
    assert spy.dispatched == []


@pytest.mark.asyncio
async def test_user_message_never_handled(monkeypatch):

    spy = _Spy()
    _patch(monkeypatch, grant=None, spy=spy)
    handled = await main_session._resume_dispatch_guard("conv1", "user_message", {"content": "hi"})
    assert handled is False
