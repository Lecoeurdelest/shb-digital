"""[BACKEND] Test T4-3: POST /interrupt — huỷ 1 sub, KHÔNG đụng sub khác (§4.3 "hủy từng con").

Quan trọng nhất (SPEC §4.3): 2 sub song song → huỷ 1 → sub kia VẪN chạy. + 404/409/400 4-field.
Dùng sub_runner seam (fake runner) + store thật (get_task validate). KHÔNG SDK.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.orch import registry, store, sub_runner

from .conftest import requires_db

client = TestClient(app)


def _user_cookie():
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    return r.cookies


@pytest.fixture(autouse=True)
def _clean():
    registry.reset_all()
    yield
    registry.reset_all()


# ── §4.3 SỐNG CÒN: huỷ 1 sub KHÔNG đụng sub kia ────────────────────────────


@requires_db
@pytest.mark.asyncio
async def test_cancel_one_sub_not_the_other():
    conv = "interrupt-two-subs"
    # 2 sub THẬT (DB row) chạy lâu (giữ running để huỷ)
    cancelled = {"a": False, "b": False}

    async def long_a(task):
        try:
            await asyncio.sleep(5)
            return {"ok": "a"}
        except asyncio.CancelledError:
            cancelled["a"] = True
            raise

    async def long_b(task):
        try:
            await asyncio.sleep(5)
            return {"ok": "b"}
        except asyncio.CancelledError:
            cancelled["b"] = True
            raise

    sub_runner.set_event_sink(_noop_sink)
    task_a = await store.create_task(conv, "credit", "A", "brief A")
    task_b = await store.create_task(conv, "legal", "B", "brief B")
    registry.register_running(conv, "credit", task_a.id)
    registry.register_running(conv, "legal", task_b.id)
    sub_runner.spawn_sub(task_a, runner=long_a)
    sub_runner.spawn_sub(task_b, runner=long_b)
    await asyncio.sleep(0.05)  # cho 2 sub vào running (mark_running)

    # huỷ CHỈ sub A qua API
    cookies = _user_cookie()
    r = client.post(f"/api/conversations/{conv}/interrupt", json={"target": task_a.id}, cookies=cookies)
    assert r.status_code == 200
    assert r.json()["cancelled"] is True
    assert r.json()["target"] == task_a.id

    await asyncio.sleep(0.1)  # cho CancelledError lan tới long_a
    assert cancelled["a"] is True, "sub A phải bị huỷ"
    assert cancelled["b"] is False, "sub B KHÔNG được đụng (§4.3 hủy từng con)"

    # dọn: huỷ B
    tb = registry.sub_tasks.get(task_b.id)
    if tb:
        tb.cancel()
    await asyncio.sleep(0.05)
    _cleanup(conv)


# ── 404 / 409 / 400 ────────────────────────────────────────────────────────


@requires_db
def test_interrupt_task_not_found_404():
    conv = "interrupt-404"
    cookies = _user_cookie()
    r = client.post(
        f"/api/conversations/{conv}/interrupt",
        json={"target": "00000000-0000-0000-0000-000000000000"},
        cookies=cookies,
    )
    assert r.status_code == 404
    assert r.json()["code"] == "task_not_found"


@requires_db
def test_interrupt_malformed_uuid_404_not_500():
    """target KHÔNG phải UUID hợp lệ (input user rác) → 404 (KHÔNG 500). tester T4-3 bắt:
    _get_task_sync raise InvalidTextRepresentation lọt ra 500 thô → giờ catch → None → 404."""
    conv = "interrupt-malformed"
    cookies = _user_cookie()
    r = client.post(
        f"/api/conversations/{conv}/interrupt",
        json={"target": "nonexistent-task-id-xyz"},  # chuỗi rác, không UUID
        cookies=cookies,
    )
    assert r.status_code == 404, f"malformed uuid PHẢI 404 không 500 — thấy {r.status_code}"
    assert r.json()["code"] == "task_not_found"


@requires_db
@pytest.mark.asyncio
async def test_interrupt_done_task_409():
    conv = "interrupt-done"
    task = await store.create_task(conv, "credit", "done task", "brief")
    await store.finish_task(task.id, "done", {"ok": True})  # đã xong
    cookies = _user_cookie()
    r = client.post(f"/api/conversations/{conv}/interrupt", json={"target": task.id}, cookies=cookies)
    assert r.status_code == 409
    assert r.json()["code"] == "task_not_running"
    _cleanup(conv)


@requires_db
@pytest.mark.asyncio
async def test_interrupt_running_db_but_no_registry_409():
    """DB running nhưng registry không còn (đã _report / double-cancel) → 409."""
    conv = "interrupt-noreg"
    task = await store.create_task(conv, "credit", "t", "brief")
    await store.mark_running(task.id)  # DB running
    # KHÔNG spawn_sub → registry.sub_tasks không có
    cookies = _user_cookie()
    r = client.post(f"/api/conversations/{conv}/interrupt", json={"target": task.id}, cookies=cookies)
    assert r.status_code == 409
    assert r.json()["code"] == "task_not_running"
    _cleanup(conv)


@requires_db
@pytest.mark.asyncio
async def test_interrupt_wrong_conv_404():
    """task tồn tại nhưng thuộc ca KHÁC → 404 (không cho huỷ task ca khác)."""
    task = await store.create_task("conv-owner", "credit", "t", "brief")
    await store.mark_running(task.id)
    cookies = _user_cookie()
    r = client.post("/api/conversations/conv-OTHER/interrupt", json={"target": task.id}, cookies=cookies)
    assert r.status_code == 404
    assert r.json()["code"] == "task_not_found"
    _cleanup("conv-owner")


def test_interrupt_target_main_400():
    """target='main' ngoài scope T4-3 → 400 (deviation ghi rõ)."""
    cookies = _user_cookie()
    r = client.post("/api/conversations/c/interrupt", json={"target": "main"}, cookies=cookies)
    assert r.status_code == 400
    assert r.json()["code"] == "target_not_supported"


def test_interrupt_requires_auth():
    fresh = TestClient(app)
    r = fresh.post("/api/conversations/c/interrupt", json={"target": "t1"})
    assert r.status_code == 401


# ── helpers ─────────────────────────────────────────────────────────────────


async def _noop_sink(conv_id, event, data):
    pass


def _cleanup(conv: str):
    import psycopg2

    from app.db.config import DATABASE_URL

    c = psycopg2.connect(DATABASE_URL)
    c.autocommit = True
    with c.cursor() as cur:
        cur.execute("DELETE FROM tasks WHERE conv_id=%s", (conv,))
    c.close()
