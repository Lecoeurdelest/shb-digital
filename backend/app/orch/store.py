"""Store tasks (DB CRUD) cho orchestrator — psycopg2 sync chạy qua asyncio.to_thread (D-22:
không block event loop). DB = kho render (SPEC §8); nguồn "đang chạy" là registry sống.

Task = dataclass nhẹ (không ORM session — INSERT raw, id server_default D-28c). conv_id là TEXT
toàn hệ (D-31: tasks.conv_id text tự do — tester dùng 'tester-ca-a-conv'; T1-3 dùng str(uuid)).

D-34: store dùng `psycopg2.connect()` PER-CALL (KHÔNG qua pool get_pool()/acquire()/release()
của mount/pg_adapter.py) → 2 connection strategy. Có chủ đích S1: render DB (ops tables) ≠ tool
conn (business tables qua pool cho executor). Ổn dưới 1-worker (bounded to_thread executor cap).
S2 khi tải cao / connection churn → thống nhất về 1 pool. Xem D-34."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import psycopg2
import psycopg2.extras

from app.db.config import DATABASE_URL


@dataclass
class Task:
    """Bản ghi task (render). id/conv_id str; role là khoá idempotency + định danh trên mặt tool."""

    id: str
    conv_id: str
    role: str
    title: str
    status: str  # queued | running | done | failed | timeout
    input: str = ""
    result: dict[str, Any] | None = None
    queued_at: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    cost: dict[str, Any] | None = field(default=None)


def _row_to_task(row: dict[str, Any]) -> Task:
    return Task(
        id=str(row["id"]),
        conv_id=str(row["conv_id"]),
        role=row["role"],
        title=row["title"],
        status=row["status"],
        input=(row.get("input") or {}).get("brief", "") if isinstance(row.get("input"), dict) else "",
        result=row.get("result"),
        queued_at=row["queued_at"].isoformat() if row.get("queued_at") else None,
        started_at=row["started_at"].isoformat() if row.get("started_at") else None,
        ended_at=row["ended_at"].isoformat() if row.get("ended_at") else None,
        cost=row.get("cost"),
    )


def task_to_dict(task: Task) -> dict[str, Any]:
    """Serialize Task → dict cho SSE/REST (1 codepath render — CONTRACT §3 OrchTask shape).
    outcome timeout → status 'failed' ở render (§3); result.reason giữ chi tiết."""
    status = "failed" if task.status == "timeout" else task.status
    return {
        "id": task.id,
        "conv_id": task.conv_id,
        "role": task.role,
        "title": task.title,
        "status": status,
        "input": task.input,
        "result": task.result,
        "queued_at": task.queued_at,
        "started_at": task.started_at,
        "ended_at": task.ended_at,
        "cost": task.cost,
    }


def _create_task_sync(conv_id: str, role: str, title: str, brief: str) -> Task:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO tasks (conv_id, role, title, status, input, queued_at) "
                "VALUES (%s, %s, %s, 'queued', %s, now()) "
                "RETURNING id, conv_id, role, title, status, input, result, "
                "queued_at, started_at, ended_at, cost",
                (conv_id, role, title, json.dumps({"brief": brief})),
            )
            row = cur.fetchone()
        conn.commit()
        return _row_to_task(dict(row))
    finally:
        conn.close()


def _update_status_sync(task_id: str, status: str, result: dict | None = None, mark_started: bool = False) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            if mark_started:
                cur.execute("UPDATE tasks SET status=%s, started_at=now() WHERE id=%s", (status, task_id))
            elif status in ("done", "failed", "timeout"):
                cur.execute(
                    "UPDATE tasks SET status=%s, result=%s, ended_at=now() WHERE id=%s",
                    (status, json.dumps(result) if result is not None else None, task_id),
                )
            else:
                cur.execute("UPDATE tasks SET status=%s WHERE id=%s", (status, task_id))
        conn.commit()
    finally:
        conn.close()


def _get_task_sync(task_id: str) -> Task | None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, conv_id, role, title, status, input, result, "
                "queued_at, started_at, ended_at, cost FROM tasks WHERE id=%s",
                (task_id,),
            )
            row = cur.fetchone()
            return _row_to_task(dict(row)) if row else None
    finally:
        conn.close()


def _board_sync(conv_id: str) -> list[dict[str, Any]]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT role, status, title FROM tasks WHERE conv_id=%s ORDER BY queued_at", (conv_id,))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _get_conv_session_id_sync(conv_id: str) -> str | None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT sdk_session_id FROM conversations WHERE id::text=%s", (conv_id,))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def _set_conv_session_id_sync(conv_id: str, session_id: str | None) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE conversations SET sdk_session_id=%s WHERE id::text=%s", (session_id, conv_id))
        conn.commit()
    finally:
        conn.close()


def _cleanup_orphans_sync() -> int:
    """boot-cleanup (§7): task DB queued/running (cờ giả sau restart) → failed('server restart')."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tasks SET status='failed', result=%s, ended_at=now() WHERE status IN ('queued','running')",
                (json.dumps({"reason": "server restart"}),),
            )
            n = cur.rowcount
        conn.commit()
        return n
    finally:
        conn.close()


# ── Conversation + Message (T1-3: render + persist) ─────────────────────────
def _create_conversation_sync(user_id: str, title: str) -> dict[str, Any]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO conversations (user_id, title, status, created_at) "
                "VALUES (%s, %s, 'idle', now()) "
                "RETURNING id, user_id, title, status, sdk_session_id, created_at",
                (user_id, title),
            )
            row = cur.fetchone()
        conn.commit()
        return _conv_to_dict(dict(row))
    finally:
        conn.close()


def _conv_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": row.get("user_id"),
        "title": row.get("title"),
        "status": row.get("status"),
        "sdk_session_id": row.get("sdk_session_id"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def _get_conversation_sync(conv_id: str) -> dict[str, Any] | None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, user_id, title, status, sdk_session_id, created_at FROM conversations WHERE id::text=%s",
                (conv_id,),
            )
            row = cur.fetchone()
            return _conv_to_dict(dict(row)) if row else None
    finally:
        conn.close()


def _list_conversations_sync(user_id: str) -> list[dict[str, Any]]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, user_id, title, status, sdk_session_id, created_at "
                "FROM conversations WHERE user_id=%s ORDER BY created_at DESC",
                (user_id,),
            )
            return [_conv_to_dict(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


def _set_conv_status_sync(conv_id: str, status: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE conversations SET status=%s WHERE id::text=%s", (status, conv_id))
        conn.commit()
    finally:
        conn.close()


def _add_message_sync(conv_id: str, sender: str, content: str, meta: dict | None = None) -> dict[str, Any]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO messages (conv_id, ts, sender, content, meta) "
                "VALUES (%s, now(), %s, %s, %s) RETURNING id, conv_id, ts, sender, content, meta",
                (conv_id, sender, content, json.dumps(meta) if meta else None),
            )
            row = cur.fetchone()
        conn.commit()
        return _msg_to_dict(dict(row))
    finally:
        conn.close()


def _msg_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "conv_id": str(row["conv_id"]),
        "ts": row["ts"].isoformat() if row.get("ts") else None,
        "sender": row.get("sender"),
        "content": row.get("content"),
        "meta": row.get("meta"),
    }


def _list_messages_sync(conv_id: str) -> list[dict[str, Any]]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, conv_id, ts, sender, content, meta FROM messages WHERE conv_id=%s ORDER BY ts",
                (conv_id,),
            )
            return [_msg_to_dict(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


def _list_tasks_sync(conv_id: str) -> list[dict[str, Any]]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, conv_id, role, title, status, input, result, "
                "queued_at, started_at, ended_at, cost FROM tasks WHERE conv_id=%s ORDER BY queued_at",
                (conv_id,),
            )
            return [task_to_dict(_row_to_task(dict(r))) for r in cur.fetchall()]
    finally:
        conn.close()


# ── async wrappers (D-22: sync psycopg2 qua to_thread — không block event loop) ──
async def create_task(conv_id: str, role: str, title: str, brief: str) -> Task:
    return await asyncio.to_thread(_create_task_sync, conv_id, role, title, brief)


async def create_conversation(user_id: str, title: str) -> dict[str, Any]:
    return await asyncio.to_thread(_create_conversation_sync, user_id, title)


async def get_conversation(conv_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_conversation_sync, conv_id)


async def list_conversations(user_id: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_conversations_sync, user_id)


async def set_conv_status(conv_id: str, status: str) -> None:
    await asyncio.to_thread(_set_conv_status_sync, conv_id, status)


async def add_message(conv_id: str, sender: str, content: str, meta: dict | None = None) -> dict[str, Any]:
    return await asyncio.to_thread(_add_message_sync, conv_id, sender, content, meta)


async def list_messages(conv_id: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_messages_sync, conv_id)


async def list_tasks(conv_id: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_tasks_sync, conv_id)


async def mark_running(task_id: str) -> None:
    await asyncio.to_thread(_update_status_sync, task_id, "running", None, True)


async def finish_task(task_id: str, status: str, result: dict | None) -> None:
    await asyncio.to_thread(_update_status_sync, task_id, status, result, False)


async def get_task(task_id: str) -> Task | None:
    return await asyncio.to_thread(_get_task_sync, task_id)


async def task_board(conv_id: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_board_sync, conv_id)


async def get_conv_session_id(conv_id: str) -> str | None:
    return await asyncio.to_thread(_get_conv_session_id_sync, conv_id)


async def set_conv_session_id(conv_id: str, session_id: str | None) -> None:
    await asyncio.to_thread(_set_conv_session_id_sync, conv_id, session_id)


async def cleanup_orphans() -> int:
    return await asyncio.to_thread(_cleanup_orphans_sync)
