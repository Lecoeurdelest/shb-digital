"""[BACKEND] Test S6 cleanup fix: (3) time-scope task đời-trước + (2) conv kẹt 'running' → 'idle'.

cleanup_orphans(boot_time): task queued_at < boot_time → failed; task SAU boot KHÔNG đụng. conv
'running' không-còn-task-sống → 'idle'; waiting_approval GIỮ. DB thật (requires_db).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg2
import pytest

from app.db.config import DATABASE_URL
from app.orch import store

from .conftest import requires_db


def _mk_task(conv: str, role: str, status: str, queued_at: datetime) -> str:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tasks (conv_id, role, title, status, queued_at) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                (conv, role, "t", status, queued_at),
            )
            return str(cur.fetchone()[0])
    finally:
        conn.close()


def _mk_conv(status: str) -> str:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (title, status, created_at) VALUES ('t',%s,now()) RETURNING id::text",
                (status,),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def _task_status(tid: str) -> str:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM tasks WHERE id=%s", (tid,))
            return cur.fetchone()[0]
    finally:
        conn.close()


def _conv_status(cid: str) -> str:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM conversations WHERE id::text=%s", (cid,))
            return cur.fetchone()[0]
    finally:
        conn.close()


def _cleanup_conv(cid: str):
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM tasks WHERE conv_id=%s", (cid,))
        cur.execute("DELETE FROM conversations WHERE id::text=%s", (cid,))
    conn.close()


# ── (3) TIME-SCOPE: task đời-trước bị quét, task sau-boot KHÔNG ──────────────


@requires_db
@pytest.mark.asyncio
async def test_cleanup_time_scope_only_before_boot():
    conv = f"s6-scope-{uuid4()}"
    boot = datetime.now(UTC)
    # task ĐỜI TRƯỚC (queued 1 phút trước boot) + task SAU boot (queued 1 phút sau)
    old = _mk_task(conv, "credit", "running", boot - timedelta(minutes=1))
    new = _mk_task(conv, "legal", "running", boot + timedelta(minutes=1))
    try:
        await store.cleanup_orphans(boot)
        assert _task_status(old) == "failed", "task đời-trước PHẢI bị quét"
        assert _task_status(new) == "running", "task SAU boot KHÔNG được đụng (S6 fix — chống race #2)"
    finally:
        _cleanup_conv(conv)


@requires_db
@pytest.mark.asyncio
async def test_cleanup_no_boot_time_scans_all():
    """boot_time None (backward-compat) → quét tất (hành vi cũ)."""
    conv = f"s6-noboot-{uuid4()}"
    t = _mk_task(conv, "credit", "queued", datetime.now(UTC))
    try:
        await store.cleanup_orphans(None)
        assert _task_status(t) == "failed"
    finally:
        _cleanup_conv(conv)


# ── (2) conv kẹt 'running' → 'idle' ─────────────────────────────────────────


@requires_db
@pytest.mark.asyncio
async def test_cleanup_stuck_running_conv_to_idle():
    """conv 'running' KHÔNG còn task sống → 'idle' (user chat tiếp resume)."""
    conv = _mk_conv("running")
    # task của conv đã terminal (done) — không còn sống
    _mk_task(conv, "credit", "done", datetime.now(UTC) - timedelta(minutes=1))
    try:
        await store.cleanup_orphans(datetime.now(UTC))
        assert _conv_status(conv) == "idle", "conv kẹt running → idle"
    finally:
        _cleanup_conv(conv)


@requires_db
@pytest.mark.asyncio
async def test_cleanup_waiting_approval_conv_kept():
    """conv 'waiting_approval' (phiếu chờ người) — HỢP LỆ, KHÔNG đổi (không phải kẹt)."""
    conv = _mk_conv("waiting_approval")
    try:
        await store.cleanup_orphans(datetime.now(UTC))
        assert _conv_status(conv) == "waiting_approval", "waiting_approval GIỮ (phiếu chờ, không kẹt)"
    finally:
        _cleanup_conv(conv)


@requires_db
@pytest.mark.asyncio
async def test_cleanup_running_conv_with_live_task_kept():
    """conv 'running' CÒN task sống (queued sau boot) → KHÔNG reset (ca đang chạy thật)."""
    conv = _mk_conv("running")
    boot = datetime.now(UTC)
    _mk_task(conv, "credit", "running", boot + timedelta(minutes=1))  # task sống sau boot
    try:
        await store.cleanup_orphans(boot)
        assert _conv_status(conv) == "running", "conv còn task sống → KHÔNG reset idle"
    finally:
        _cleanup_conv(conv)


# ── guard-B: terminal bất biến, NGOẠI LỆ failed{server restart} bị done/timeout thật đè ──


def _set_task_status_result(tid: str, status: str, result: dict):
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE tasks SET status=%s, result=%s, ended_at=now() WHERE id=%s",
            (status, __import__("json").dumps(result), tid),
        )
    conn.close()


def _task_result(tid: str):
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status, result FROM tasks WHERE id=%s", (tid,))
            return cur.fetchone()
    finally:
        conn.close()


@requires_db
@pytest.mark.asyncio
async def test_guardB_done_overrides_failed_server_restart():
    """done THẬT đè failed{server restart} (cờ-giả hạ-tầng) — task thật xong thắng cờ-giả."""
    conv = f"s6-guardB-1-{uuid4()}"
    tid = _mk_task(conv, "credit", "running", datetime.now(UTC))
    _set_task_status_result(tid, "failed", {"reason": "server restart"})  # cờ-giả boot-cleanup
    try:
        await store.finish_task(tid, "done", {"ok": True})  # sub thật xong SAU
        st, res = _task_result(tid)
        assert st == "done", "done PHẢI đè failed{server restart} (cờ-giả)"
        assert res.get("ok") is True
    finally:
        _cleanup_conv(conv)


@requires_db
@pytest.mark.asyncio
async def test_guardB_done_NOT_override_user_huy():
    """failed-THẬT (user hủy) KHÔNG bị done đè — terminal-thật bất biến."""
    conv = f"s6-guardB-2-{uuid4()}"
    tid = _mk_task(conv, "credit", "running", datetime.now(UTC))
    _set_task_status_result(tid, "failed", {"reason": "user hủy"})  # failed THẬT (interrupt)
    try:
        await store.finish_task(tid, "done", {"ok": True})  # đến sau — KHÔNG được đè
        st, res = _task_result(tid)
        assert st == "failed", "failed-thật (user hủy) KHÔNG bị đè"
        assert res.get("reason") == "user hủy"
    finally:
        _cleanup_conv(conv)


@requires_db
@pytest.mark.asyncio
async def test_guardB_cogia_after_done_blocked():
    """cờ-giả failed{server restart} tới SAU done → bị guard chặn (done bất biến giữ)."""
    conv = f"s6-guardB-3-{uuid4()}"
    tid = _mk_task(conv, "credit", "running", datetime.now(UTC))
    _set_task_status_result(tid, "done", {"result": "xong"})  # done thật trước
    try:
        # cờ-giả server-restart đến sau (nếu race) → guard chặn (done không phải server-restart)
        await store.finish_task(tid, "failed", {"reason": "server restart"})
        st, _ = _task_result(tid)
        assert st == "done", "done bất biến — cờ-giả tới sau bị chặn"
    finally:
        _cleanup_conv(conv)
