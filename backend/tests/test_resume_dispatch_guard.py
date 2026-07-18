"""[BACKEND] Test T3-4 race fix: _resume_dispatch_guard — 2 nhánh chặn resume-dispatch đua.

Unit (KHÔNG SDK): mock store_approvals.pending_execution + orch_dispatch_impl + registry running.
Kiểm 4 ràng buộc architect + 6 blind-spot advisor:
- A) approval_decided approved + role running → SKIP MAIN (return True), KHÔNG dispatch ngay.
- A') approval_decided approved + role KHÔNG running → path bình thường (return False, MAIN dispatch).
- B) task_done + grant treo + role vừa free → re-dispatch role (spawn) + SKIP MAIN (True).
- B') task_done KHÔNG grant → path bình thường (False, MAIN report). KHÔNG suppress oan.
- reject không tạo grant → không strand.
"""

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

    async def dispatch(self, conv_id, role, title, brief):
        self.dispatched.append((conv_id, role, title, brief))
        return {"created": True, "role": role, "status": "running"}


def _patch(monkeypatch, grant, spy):
    async def fake_pending(conv_id):
        return grant

    monkeypatch.setattr("app.orch.store_approvals.pending_execution", fake_pending)
    monkeypatch.setattr("app.orch.dispatch.orch_dispatch_impl", spy.dispatch)


# ── A: approval_decided approved + role running → hoãn (SKIP MAIN, không dispatch) ──


@pytest.mark.asyncio
async def test_A_approved_role_running_skips_main_no_dispatch(monkeypatch):
    spy = _Spy()
    _patch(monkeypatch, grant=None, spy=spy)
    registry.register_running("conv1", "operations", "task-ops-1")  # ops#1 CÒN running

    handled = await main_session._resume_dispatch_guard(
        "conv1", "approval_decided", {"action": "disburse", "decision": "approved", "payload": {"loan_id": "L1"}}
    )
    assert handled is True  # SKIP MAIN (grant treo ở approval row, nhánh B lo khi free)
    assert spy.dispatched == []  # KHÔNG dispatch đua trước ops#1 return


@pytest.mark.asyncio
async def test_Aprime_approved_role_free_normal_path(monkeypatch):
    """ops đã return (không running) → path bình thường → MAIN tự dispatch (return False)."""
    spy = _Spy()
    _patch(monkeypatch, grant=None, spy=spy)
    # KHÔNG register operations → get_running_task_id None

    handled = await main_session._resume_dispatch_guard(
        "conv1", "approval_decided", {"action": "disburse", "decision": "approved", "payload": {"loan_id": "L1"}}
    )
    assert handled is False  # path cũ không đổi — MAIN dispatch như hiện tại


@pytest.mark.asyncio
async def test_reject_never_handled(monkeypatch):
    """rejected → KHÔNG tạo grant, KHÔNG suppress — MAIN báo user từ chối bình thường."""
    spy = _Spy()
    _patch(monkeypatch, grant=None, spy=spy)
    registry.register_running("conv1", "operations", "task-ops-1")

    handled = await main_session._resume_dispatch_guard(
        "conv1", "approval_decided", {"action": "disburse", "decision": "rejected", "payload": {"loan_id": "L1"}}
    )
    assert handled is False
    assert spy.dispatched == []


# ── B: task_done + grant treo + role vừa free → re-dispatch (spawn) + SKIP MAIN ──


@pytest.mark.asyncio
async def test_B_task_done_with_grant_redispatches_and_skips(monkeypatch):
    grant = {
        "id": "ap1",
        "action": "disburse",
        "payload": {"loan_id": "L1", "amount": 5000000000},
        "status": "approved",
    }
    spy = _Spy()
    _patch(monkeypatch, grant=grant, spy=spy)
    # operations KHÔNG running (vừa unregister ở _report trước task_done)

    handled = await main_session._resume_dispatch_guard("conv1", "task_done", {"role": "operations", "outcome": "done"})
    assert handled is True  # SKIP MAIN report (ops#2 done sẽ báo hoàn tất)
    assert len(spy.dispatched) == 1
    conv_id, role, title, brief = spy.dispatched[0]
    assert conv_id == "conv1" and role == "operations"
    assert "disburse" in brief and "ĐÃ ĐƯỢC DUYỆT" in brief  # brief self-contained, canned
    assert "loan_id=L1" in brief


@pytest.mark.asyncio
async def test_Bprime_task_done_no_grant_normal_report(monkeypatch):
    """KHÔNG grant → MAIN report bình thường (không suppress oan message hợp lệ)."""
    spy = _Spy()
    _patch(monkeypatch, grant=None, spy=spy)

    handled = await main_session._resume_dispatch_guard("conv1", "task_done", {"role": "operations", "outcome": "done"})
    assert handled is False
    assert spy.dispatched == []


@pytest.mark.asyncio
async def test_B_grant_but_role_still_running_no_double(monkeypatch):
    """grant treo NHƯNG role vẫn running (task_done của role KHÁC) → KHÔNG re-dispatch (tránh 2 sub
    cùng role — ràng buộc 3)."""
    grant = {"id": "ap1", "action": "disburse", "payload": {"loan_id": "L1"}, "status": "approved"}
    spy = _Spy()
    _patch(monkeypatch, grant=grant, spy=spy)
    registry.register_running("conv1", "operations", "task-ops-still")  # operations CÒN chạy

    # task_done của role KHÁC (credit) đến — operations vẫn running → KHÔNG re-dispatch operations
    handled = await main_session._resume_dispatch_guard("conv1", "task_done", {"role": "credit", "outcome": "done"})
    assert handled is False  # credit done, không phải operations → path bình thường
    assert spy.dispatched == []


@pytest.mark.asyncio
async def test_B_grant_wrong_done_role_no_dispatch(monkeypatch):
    """grant disburse (operations) nhưng task_done là credit → KHÔNG re-dispatch (chỉ role sở hữu)."""
    grant = {"id": "ap1", "action": "disburse", "payload": {"loan_id": "L1"}, "status": "approved"}
    spy = _Spy()
    _patch(monkeypatch, grant=grant, spy=spy)

    handled = await main_session._resume_dispatch_guard("conv1", "task_done", {"role": "credit", "outcome": "done"})
    assert handled is False
    assert spy.dispatched == []


@pytest.mark.asyncio
async def test_user_message_never_handled(monkeypatch):
    """user_message → guard KHÔNG đụng (chỉ approval_decided + task_done)."""
    spy = _Spy()
    _patch(monkeypatch, grant=None, spy=spy)
    handled = await main_session._resume_dispatch_guard("conv1", "user_message", {"content": "hi"})
    assert handled is False
