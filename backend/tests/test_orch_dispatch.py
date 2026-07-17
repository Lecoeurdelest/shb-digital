"""[BACKEND] Test dispatch idempotent (full impl) + orch_status honest + boot-cleanup.

create_task_guarded chạm DB thật (tasks) → cần DB. Idempotency = registry (conv,role).
"""

from __future__ import annotations

import pytest

from app.orch import dispatch, registry, store, sub_runner

from .conftest import requires_db


@requires_db
@pytest.mark.asyncio
async def test_orch_dispatch_impl_created_true_then_false(monkeypatch):
    """dispatch_impl lần 1 created:true, lần 2 (role đang chạy) created:false — KHÔNG spawn đôi."""
    # chặn spawn_sub thật (không chạy SDK) — chỉ test idempotency dispatch
    monkeypatch.setattr(sub_runner, "spawn_sub", lambda task: None)
    conv, role = "disp-impl-conv", "credit"

    r1 = await dispatch.orch_dispatch_impl(conv, role, "lần 1", "input A")
    assert r1["created"] is True
    assert r1["role"] == role
    assert r1["status"] == "running"
    assert "task_id" not in r1  # ID KHÔNG lên mặt tool (spec §15)

    r2 = await dispatch.orch_dispatch_impl(conv, role, "lần 2", "input B")
    assert r2["created"] is False
    assert r2["role"] == role
    assert "hint" in r2


@pytest.mark.asyncio
async def test_orch_dispatch_impl_bad_role():
    r = await dispatch.orch_dispatch_impl("c", "nonexistent_role", "t", "i")
    assert r["code"] == "bad_role"
    assert r["retryable"] is False


@requires_db
@pytest.mark.asyncio
async def test_dispatch_after_report_allows_redispatch(monkeypatch):
    """Sau khi sub _report (gỡ registry), dispatch LẠI cùng role → created:true (không khoá vĩnh viễn)."""
    monkeypatch.setattr(sub_runner, "spawn_sub", lambda task: None)
    conv, role = "disp-redispatch-conv", "credit"

    r1 = await dispatch.orch_dispatch_impl(conv, role, "lần 1", "i")
    assert r1["created"] is True
    # mô phỏng sub xong: gỡ registry như _report làm
    registry.unregister_running(conv, role)

    r2 = await dispatch.orch_dispatch_impl(conv, role, "lần 2 sau khi xong", "i")
    assert r2["created"] is True, "sau _report role phải mở lại cho dispatch mới"


@requires_db
@pytest.mark.asyncio
async def test_boot_cleanup_marks_orphans_failed():
    """boot-cleanup: task DB queued/running (cờ giả sau restart) → failed('server restart')."""
    # tạo 1 task queued mồ côi
    task = await store.create_task("boot-orphan-conv", "credit", "mồ côi", "i")
    assert task.status == "queued"

    n = await store.cleanup_orphans()
    assert n >= 1

    refetched = await store.get_task(task.id)
    assert refetched.status == "failed"
    assert refetched.result["reason"] == "server restart"
