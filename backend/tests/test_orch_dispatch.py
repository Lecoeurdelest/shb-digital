from __future__ import annotations

import pytest

from app.orch import dispatch, registry, store, sub_runner

from .conftest import requires_db


@requires_db
@pytest.mark.asyncio
async def test_orch_dispatch_impl_created_true_then_false(monkeypatch):

    monkeypatch.setattr(sub_runner, "spawn_sub", lambda task: None)
    conv, role = "disp-impl-conv", "credit"

    r1 = await dispatch.orch_dispatch_impl(conv, role, "first run", "input A")
    assert r1["created"] is True
    assert r1["role"] == role
    assert r1["status"] == "running"
    assert "task_id" not in r1

    r2 = await dispatch.orch_dispatch_impl(conv, role, "second run", "input B")
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

    monkeypatch.setattr(sub_runner, "spawn_sub", lambda task: None)
    conv, role = "disp-redispatch-conv", "credit"

    r1 = await dispatch.orch_dispatch_impl(conv, role, "first run", "i")
    assert r1["created"] is True

    registry.unregister_running(conv, role)

    r2 = await dispatch.orch_dispatch_impl(conv, role, "second run after completion", "i")
    assert r2["created"] is True, "Expected invariant was not satisfied at source line 49."


@requires_db
@pytest.mark.asyncio
async def test_boot_cleanup_marks_orphans_failed():

    task = await store.create_task("boot-orphan-conv", "credit", "orphan", "i")
    assert task.status == "queued"

    n = await store.cleanup_orphans()
    assert n >= 1

    refetched = await store.get_task(task.id)
    assert refetched.status == "failed"
    assert refetched.result["reason"] == "server restart"
