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


@requires_db
@pytest.mark.asyncio
async def test_cleanup_time_scope_only_before_boot():
    conv = f"s6-scope-{uuid4()}"
    boot = datetime.now(UTC)

    old = _mk_task(conv, "credit", "running", boot - timedelta(minutes=1))
    new = _mk_task(conv, "legal", "running", boot + timedelta(minutes=1))
    try:
        await store.cleanup_orphans(boot)
        assert _task_status(old) == "failed", "Expected invariant was not satisfied at source line 82."
        assert _task_status(new) == "running", "Expected invariant was not satisfied at source line 83."
    finally:
        _cleanup_conv(conv)


@requires_db
@pytest.mark.asyncio
async def test_cleanup_no_boot_time_scans_all():

    conv = f"s6-noboot-{uuid4()}"
    t = _mk_task(conv, "credit", "queued", datetime.now(UTC))
    try:
        await store.cleanup_orphans(None)
        assert _task_status(t) == "failed"
    finally:
        _cleanup_conv(conv)


@requires_db
@pytest.mark.asyncio
async def test_cleanup_stuck_running_conv_to_idle():

    conv = _mk_conv("running")

    _mk_task(conv, "credit", "done", datetime.now(UTC) - timedelta(minutes=1))
    try:
        await store.cleanup_orphans(datetime.now(UTC))
        assert _conv_status(conv) == "idle", "Expected invariant was not satisfied at source line 110."
    finally:
        _cleanup_conv(conv)


@requires_db
@pytest.mark.asyncio
async def test_cleanup_waiting_approval_conv_kept():

    conv = _mk_conv("waiting_approval")
    try:
        await store.cleanup_orphans(datetime.now(UTC))
        assert _conv_status(conv) == "waiting_approval", "Expected invariant was not satisfied at source line 122."
    finally:
        _cleanup_conv(conv)


@requires_db
@pytest.mark.asyncio
async def test_cleanup_running_conv_with_live_task_kept():

    conv = _mk_conv("running")
    boot = datetime.now(UTC)
    _mk_task(conv, "credit", "running", boot + timedelta(minutes=1))
    try:
        await store.cleanup_orphans(boot)
        assert _conv_status(conv) == "running", "Expected invariant was not satisfied at source line 136."
    finally:
        _cleanup_conv(conv)


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

    conv = f"s6-guardB-1-{uuid4()}"
    tid = _mk_task(conv, "credit", "running", datetime.now(UTC))
    _set_task_status_result(tid, "failed", {"reason": "server restart"})
    try:
        await store.finish_task(tid, "done", {"ok": True})
        st, res = _task_result(tid)
        assert st == "done", "Expected invariant was not satisfied at source line 172."
        assert res.get("ok") is True
    finally:
        _cleanup_conv(conv)


@requires_db
@pytest.mark.asyncio
async def test_guardB_done_NOT_override_user_huy():

    conv = f"s6-guardB-2-{uuid4()}"
    tid = _mk_task(conv, "credit", "running", datetime.now(UTC))
    _set_task_status_result(tid, "failed", {"reason": "cancelled by user"})
    try:
        await store.finish_task(tid, "done", {"ok": True})
        st, res = _task_result(tid)
        assert st == "failed", "Expected invariant was not satisfied at source line 188."
        assert res.get("reason") == "cancelled by user"
    finally:
        _cleanup_conv(conv)


@requires_db
@pytest.mark.asyncio
async def test_guardB_cogia_after_done_blocked():

    conv = f"s6-guardB-3-{uuid4()}"
    tid = _mk_task(conv, "credit", "running", datetime.now(UTC))
    _set_task_status_result(tid, "done", {"result": "complete"})
    try:
        await store.finish_task(tid, "failed", {"reason": "server restart"})
        st, _ = _task_result(tid)
        assert st == "done", "Expected invariant was not satisfied at source line 204."
    finally:
        _cleanup_conv(conv)
