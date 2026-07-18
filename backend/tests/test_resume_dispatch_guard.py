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
        self.claimed: list[str] = []  # T4-0: approval_id đã increment attempt
        self.marked_failed: list[str] = []  # T4-0: approval_id set exec_failed (vượt trần)

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
        "exec_attempts": 0,
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
    assert spy.claimed == ["ap1"]  # T4-0: increment attempt KHI re-dispatch (chắc role khớp)


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
    grant = {"id": "ap1", "action": "disburse", "payload": {"loan_id": "L1"}, "status": "approved", "exec_attempts": 0}
    spy = _Spy()
    _patch(monkeypatch, grant=grant, spy=spy)
    registry.register_running("conv1", "operations", "task-ops-still")  # operations CÒN chạy

    # task_done của role KHÁC (credit) đến — operations vẫn running → KHÔNG re-dispatch operations
    handled = await main_session._resume_dispatch_guard("conv1", "task_done", {"role": "credit", "outcome": "done"})
    assert handled is False  # credit done, không phải operations → path bình thường
    assert spy.dispatched == []
    assert spy.claimed == []  # T4-0: role không khớp → KHÔNG tốn quota attempt oan


@pytest.mark.asyncio
async def test_B_grant_wrong_done_role_no_dispatch(monkeypatch):
    """grant disburse (operations) nhưng task_done là credit → KHÔNG re-dispatch (chỉ role sở hữu)."""
    grant = {"id": "ap1", "action": "disburse", "payload": {"loan_id": "L1"}, "status": "approved", "exec_attempts": 0}
    spy = _Spy()
    _patch(monkeypatch, grant=grant, spy=spy)

    handled = await main_session._resume_dispatch_guard("conv1", "task_done", {"role": "credit", "outcome": "done"})
    assert handled is False
    assert spy.dispatched == []
    assert spy.claimed == []


# ── T4-0 loop-bound: vượt trần → DỪNG re-dispatch + exec_failed ──────────────


@pytest.mark.asyncio
async def test_T40_exec_attempts_below_max_still_redispatches(monkeypatch):
    """attempt < MAX (fail tạm 1-2 lần) → VẪN re-dispatch (retry hợp lệ, trần không quá chặt)."""
    from app.orch import store_approvals

    grant = {
        "id": "ap1",
        "action": "disburse",
        "payload": {"loan_id": "L1"},
        "status": "approved",
        "exec_attempts": store_approvals.MAX_EXEC_ATTEMPTS - 1,  # =2, còn 1 quota
    }
    spy = _Spy()
    _patch(monkeypatch, grant=grant, spy=spy)

    handled = await main_session._resume_dispatch_guard("conv1", "task_done", {"role": "operations", "outcome": "done"})
    assert handled is True  # còn quota → re-dispatch
    assert len(spy.dispatched) == 1
    assert spy.claimed == ["ap1"]
    assert spy.marked_failed == []  # chưa vượt trần


@pytest.mark.asyncio
async def test_T40_exec_attempts_at_max_stops_and_marks_failed(monkeypatch):
    """attempt >= MAX (fail BỀN) → DỪNG re-dispatch + mark exec_failed + KHÔNG SKIP (MAIN báo user)."""
    from app.orch import store_approvals

    grant = {
        "id": "ap1",
        "action": "disburse",
        "payload": {"loan_id": "L1"},
        "status": "approved",
        "exec_attempts": store_approvals.MAX_EXEC_ATTEMPTS,  # =3, chạm trần
    }
    spy = _Spy()
    _patch(monkeypatch, grant=grant, spy=spy)

    data = {"role": "operations", "outcome": "done"}
    handled = await main_session._resume_dispatch_guard("conv1", "task_done", data)
    assert handled is False  # KHÔNG SKIP → MAIN report báo user "lỗi bền"
    assert spy.dispatched == []  # DỪNG re-dispatch (chống loop vô hạn)
    assert spy.claimed == []  # vượt trần → không increment nữa
    assert spy.marked_failed == ["ap1"]  # phiếu → exec_failed
    # DETERMINISTIC escalation (không cược model): data có signal exec_failed → prompt rõ cho MAIN.
    assert data.get("exec_failed") is not None
    assert data["exec_failed"]["attempts"] == store_approvals.MAX_EXEC_ATTEMPTS
    assert data["exec_failed"]["action"] == "disburse"


def test_prompt_exec_failed_deterministic():
    """_build_event_prompt task_done + exec_failed → prompt RÕ 'thất bại bền, cần người' (không
    phụ suy luận model đọc result_summary). Không cần DB/async."""
    from app.orch.main_session import _build_event_prompt

    p = _build_event_prompt(
        "task_done",
        {
            "role": "operations",
            "outcome": "done",
            "exec_failed": {"action": "disburse", "attempts": 3, "payload_summary": "loan_id=L1"},
        },
    )
    assert "THẤT BẠI BỀN" in p and "CẦN NGƯỜI" in p and "3 lần" in p
    assert "KHÔNG tự thử lại" in p


def test_prompt_disburse_done_dan_khong_present_lai():
    """T4-5: task_done ops+done+disbursed → dặn MAIN KHÔNG present lại (Ops đã trình biên nhận) →
    chống 2-card-trùng. Predicate HẸP: chỉ path này."""
    from app.orch.main_session import _build_event_prompt

    p = _build_event_prompt(
        "task_done",
        {
            "role": "operations",
            "outcome": "done",
            "result_summary": '{"disbursed": true, "loan_id": "L001", "amount": 5000000000}',
            "board": [],
        },
    )
    assert "KHÔNG present" in p and "TRÌNH BIÊN NHẬN" in p
    assert "1 câu ngắn" in p


def test_prompt_non_disburse_task_done_normal():
    """T4-5 predicate KHÔNG fire cho task khác (credit done / ops không disbursed) → prompt generic
    (GIỮ #1 main summary + present bình thường)."""
    from app.orch.main_session import _build_event_prompt

    # credit done → generic (không dặn không-present)
    p_credit = _build_event_prompt(
        "task_done",
        {"role": "credit", "outcome": "done", "result_summary": "DSCR 1.5 đủ điều kiện", "board": []},
    )
    assert "KHÔNG present" not in p_credit

    # ops done nhưng KHÔNG disbursed (vd ops_plan lộ trình) → generic
    p_ops_plan = _build_event_prompt(
        "task_done",
        {"role": "operations", "outcome": "done", "result_summary": '{"steps": [...], "totalDays": 5}', "board": []},
    )
    assert "KHÔNG present" not in p_ops_plan


@pytest.mark.asyncio
async def test_T40_exhausted_wrong_role_no_mark(monkeypatch):
    """grant vượt trần NHƯNG task_done role KHÁC → KHÔNG mark (chờ role sở hữu done)."""
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
    assert spy.marked_failed == []  # role không khớp → chưa mark
    assert spy.dispatched == []


@pytest.mark.asyncio
async def test_user_message_never_handled(monkeypatch):
    """user_message → guard KHÔNG đụng (chỉ approval_decided + task_done)."""
    spy = _Spy()
    _patch(monkeypatch, grant=None, spy=spy)
    handled = await main_session._resume_dispatch_guard("conv1", "user_message", {"content": "hi"})
    assert handled is False
