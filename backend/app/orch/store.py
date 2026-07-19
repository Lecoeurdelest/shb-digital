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
from datetime import datetime
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
    """S6 guard-B (#2 race): terminal status BẤT BIẾN — NGOẠI LỆ DUY NHẤT `failed{server restart}`
    (cờ-giả hạ-tầng boot-cleanup) bị done/timeout THẬT đè. failed-THẬT (user hủy/lỗi tool) KHÔNG bị
    đè. rowcount=0 = write bị guard chặn → log warning (lộ nguồn-ghi-lạ, không nuốt im)."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            if mark_started:
                cur.execute("UPDATE tasks SET status=%s, started_at=now() WHERE id=%s", (status, task_id))
            elif status in ("done", "failed", "timeout"):
                # guard: chỉ ghi khi task CHƯA terminal, HOẶC terminal='failed{server restart}' (cờ-giả).
                cur.execute(
                    "UPDATE tasks SET status=%s, result=%s, ended_at=now() WHERE id=%s AND "
                    "(status NOT IN ('done','failed','timeout') "
                    " OR (status='failed' AND result->>'reason'='server restart'))",
                    (status, json.dumps(result) if result is not None else None, task_id),
                )
                if cur.rowcount == 0:
                    import logging

                    logging.getLogger("orch").warning(
                        "task %s: write status=%s bị GUARD CHẶN (đã terminal-thật) — nghi nguồn-ghi-lạ", task_id, status
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
    except psycopg2.errors.InvalidTextRepresentation:
        # task_id KHÔNG phải UUID hợp lệ (input user malformed) → coi như KHÔNG tồn tại (None → 404
        # tự nhiên ở caller), KHÔNG để psycopg2 DataError lọt ra 500. Nhất quán _exists_sync
        # (store_approvals) đã catch psycopg2.Error cho uuid sai. Tester T4-3 bắt: interrupt malformed→500.
        return None
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


def _cleanup_orphans_sync(boot_time: datetime | None = None) -> int:
    """boot-cleanup (§7): task ĐỜI TRƯỚC (queued/running mồ côi sau restart) → failed('server restart').

    S6 fix:
    - (A) TIME-SCOPE: chỉ quét task `queued_at < boot_time` — cleanup = "chôn task ĐỜI TRƯỚC", KHÔNG
      đụng task đời-này (tránh quét nhầm task vừa-tạo-sau-boot nếu request tới trước cleanup xong).
      boot_time None → quét tất (backward-compat / test không truyền).
    - (2) conv KẸT 'running' vĩnh viễn (task chết nhưng conv không reset): conv 'running' mà KHÔNG
      còn task sống (queued/running) → set 'idle' (user chat tiếp resume bình thường §8).
      waiting_approval GIỮ (hợp lệ — phiếu chờ người, không phải kẹt).
    """
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            if boot_time is not None:
                cur.execute(
                    "UPDATE tasks SET status='failed', result=%s, ended_at=now() "
                    "WHERE status IN ('queued','running') AND queued_at < %s",
                    (json.dumps({"reason": "server restart"}), boot_time),
                )
            else:
                cur.execute(
                    "UPDATE tasks SET status='failed', result=%s, ended_at=now() WHERE status IN ('queued','running')",
                    (json.dumps({"reason": "server restart"}),),
                )
            n = cur.rowcount
            # (2) conv kẹt 'running' mà KHÔNG còn task sống → 'idle' (waiting_approval giữ).
            cur.execute(
                "UPDATE conversations SET status='idle' WHERE status='running' "
                "AND id::text NOT IN (SELECT DISTINCT conv_id FROM tasks WHERE status IN ('queued','running'))"
            )
        conn.commit()
        return n
    finally:
        conn.close()


# ── Conversation + Message (T1-3: render + persist) ─────────────────────────
def _create_conversation_sync(
    user_id: str, title: str, provider: str | None = None, model: str | None = None
) -> dict[str, Any]:
    """D-45b (c): lưu provider/model per-conv (null → server-default lúc chạy). Resume-consistency."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO conversations (user_id, title, status, provider, model, created_at) "
                "VALUES (%s, %s, 'idle', %s, %s, now()) "
                "RETURNING id, user_id, title, status, sdk_session_id, provider, model, created_at",
                (user_id, title, provider or None, model or None),
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
        "provider": row.get("provider"),  # D-45b (c) — null = server-default
        "model": row.get("model"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def _get_conversation_sync(conv_id: str) -> dict[str, Any] | None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, user_id, title, status, sdk_session_id, provider, model, created_at "
                "FROM conversations WHERE id::text=%s",
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
                "SELECT id, user_id, title, status, sdk_session_id, provider, model, created_at "
                "FROM conversations WHERE user_id=%s ORDER BY created_at DESC",
                (user_id,),
            )
            return [_conv_to_dict(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


def _list_all_conversations_sync() -> list[dict[str, Any]]:
    """D-56: admin (ngân hàng) → MỌI ca (không filter user_id). Giám sát toàn cửa khách."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, user_id, title, status, sdk_session_id, provider, model, created_at "
                "FROM conversations ORDER BY created_at DESC"
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


# ── T15-2/T15-3: rename + switch provider/model + hard delete ────────────────
def _update_conversation_sync(
    conv_id: str, title: str | None, provider: str | None, model: str | None
) -> dict[str, Any] | None:
    """PATCH partial: chỉ set field TRUYỀN (None = không đổi). Trả conv mới, None nếu ca không tồn tại.
    Validate provider/model là việc của caller (router) — store chỉ ghi. id::text so khớp (conv_id text)."""
    sets: list[str] = []
    vals: list[Any] = []
    if title is not None:
        sets.append("title=%s")
        vals.append(title)
    if provider is not None:
        sets.append("provider=%s")
        vals.append(provider)
    if model is not None:
        sets.append("model=%s")
        vals.append(model)
    if not sets:  # không field nào → chỉ trả conv hiện tại (router đã chặn body rỗng, defensive)
        return _get_conversation_sync(conv_id)
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"UPDATE conversations SET {', '.join(sets)} WHERE id::text=%s "  # noqa: S608 — sets là literal cột, không phải input
                "RETURNING id, user_id, title, status, sdk_session_id, provider, model, created_at",
                (*vals, conv_id),
            )
            row = cur.fetchone()
        conn.commit()
        return _conv_to_dict(dict(row)) if row else None
    finally:
        conn.close()


def _delete_conversation_sync(conv_id: str) -> str:
    """HARD delete ca trong 1 TX: chặn nếu còn phiếu pending → 'pending'; chặn nếu đang chạy →
    'running'; ok → xoá messages+cards+tasks+conv (D-67: nội dung ca), GIỮ tool_calls + approvals
    ĐÃ QUYẾT (audit append-only) → 'deleted'. Ca không tồn tại → 'not_found'.
    1 TX (advisor): check-pending + mọi DELETE cùng conn — không nửa-xoá, không check-then-delete hở."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM conversations WHERE id::text=%s", (conv_id,))
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                return "not_found"
            # còn phiếu pending → chặn (quyết phiếu trước). Trong TX → không đua với decide.
            cur.execute("SELECT 1 FROM approvals WHERE conv_id=%s AND status='pending' LIMIT 1", (conv_id,))
            if cur.fetchone():
                conn.rollback()
                return "pending"
            # xoá NỘI DUNG ca (D-67). approvals ĐÃ QUYẾT + tool_calls KHÔNG xoá (audit append-only §11).
            cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
            cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
            cur.execute("DELETE FROM tasks WHERE conv_id=%s", (conv_id,))
            cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv_id,))
        conn.commit()
        return "deleted"
    except Exception:
        conn.rollback()
        raise
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


def _insert_card_sync(conv_id: str, task_id: str | None, card_type: str, data: dict) -> dict[str, Any]:
    """INSERT card → trả row với id VỎ sinh (server_default). task_id null OK (main gọi ngoài sub)."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO cards (conv_id, task_id, type, data, ts) "
                "VALUES (%s, %s, %s, %s, now()) RETURNING id, conv_id, task_id, type, data, ts",
                (conv_id, task_id or None, card_type, json.dumps(data)),
            )
            row = cur.fetchone()
        conn.commit()
        return _card_to_dict(dict(row))
    finally:
        conn.close()


def _card_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Card render dict. data (jsonb) merge lên top-level cho FE (type/title/items ở data).

    LỚP 2 phòng thủ (N5/§15): spread **data TRƯỚC, field VỎ-OWNED (id/conv_id/task_id/type/ts)
    đặt SAU → LUÔN THẮNG dù data lỡ chứa key trùng. id vỏ-inject không bao giờ bị agent ghi đè.
    """
    data = row.get("data") or {}
    return {
        **data,  # title, items, sources... (nội dung agent bơm — vỏ mù N3)
        "id": str(row["id"]),  # VỎ-owned — đặt SAU, thắng mọi key 'id' lọt trong data
        "conv_id": str(row["conv_id"]),
        "task_id": str(row["task_id"]) if row.get("task_id") else None,
        "type": row["type"],
        "ts": row["ts"].isoformat() if row.get("ts") else None,
    }


def _list_cards_sync(conv_id: str) -> list[dict[str, Any]]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, conv_id, task_id, type, data, ts FROM cards WHERE conv_id=%s ORDER BY ts",
                (conv_id,),
            )
            return [_card_to_dict(dict(r)) for r in cur.fetchall()]
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


async def create_conversation(
    user_id: str, title: str, provider: str | None = None, model: str | None = None
) -> dict[str, Any]:
    return await asyncio.to_thread(_create_conversation_sync, user_id, title, provider, model)


async def get_conversation(conv_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_conversation_sync, conv_id)


async def list_conversations(user_id: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_conversations_sync, user_id)


async def list_all_conversations() -> list[dict[str, Any]]:
    """D-56 admin: mọi ca (không scope user_id)."""
    return await asyncio.to_thread(_list_all_conversations_sync)


async def set_conv_status(conv_id: str, status: str) -> None:
    await asyncio.to_thread(_set_conv_status_sync, conv_id, status)


def _save_task_metrics_sync(task_id: str, m: dict[str, Any]) -> None:
    """T16-1: UPDATE task với chỉ số THẬT từ ResultMessage (token/duration/model + cost jsonb).
    Best-effort: id sai/lỗi → nuốt (không vỡ flow sub). Field None → cột NULL sạch (ADDITIVE)."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tasks SET input_tokens=%s, output_tokens=%s, cache_read_tokens=%s, "
                "cache_create_tokens=%s, duration_ms=%s, model=%s, "
                "cost=COALESCE(%s::jsonb, cost) WHERE id=%s",
                (
                    m.get("input_tokens"),
                    m.get("output_tokens"),
                    m.get("cache_read_tokens"),
                    m.get("cache_create_tokens"),
                    m.get("duration_ms"),
                    m.get("model"),
                    json.dumps({"cost_usd": m["cost_usd"]}) if m.get("cost_usd") is not None else None,
                    task_id,
                ),
            )
        conn.commit()
    except psycopg2.Error as e:
        import logging

        conn.rollback()
        logging.getLogger("orch").warning("save_task_metrics task=%s lỗi (bỏ qua): %s", task_id, e)
    finally:
        conn.close()


async def save_task_metrics(task_id: str, metrics: dict[str, Any]) -> None:
    """T16-1: lưu chỉ số ResultMessage vào task row. Best-effort (không vỡ sub nếu lỗi)."""
    await asyncio.to_thread(_save_task_metrics_sync, task_id, metrics)


async def update_conversation(
    conv_id: str, title: str | None = None, provider: str | None = None, model: str | None = None
) -> dict[str, Any] | None:
    """T15-2/T15-3: PATCH partial (title/provider/model). None = không đổi. None-return = ca không tồn tại."""
    return await asyncio.to_thread(_update_conversation_sync, conv_id, title, provider, model)


async def delete_conversation(conv_id: str) -> str:
    """T15-3 hard delete → 'deleted'|'pending'|'not_found' (running-check ở router qua registry)."""
    return await asyncio.to_thread(_delete_conversation_sync, conv_id)


async def add_message(conv_id: str, sender: str, content: str, meta: dict | None = None) -> dict[str, Any]:
    return await asyncio.to_thread(_add_message_sync, conv_id, sender, content, meta)


async def list_messages(conv_id: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_messages_sync, conv_id)


async def list_tasks(conv_id: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_tasks_sync, conv_id)


async def insert_card(conv_id: str, task_id: str | None, card_type: str, data: dict) -> dict[str, Any]:
    return await asyncio.to_thread(_insert_card_sync, conv_id, task_id, card_type, data)


async def list_cards(conv_id: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_cards_sync, conv_id)


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


async def cleanup_orphans(boot_time: datetime | None = None) -> int:
    return await asyncio.to_thread(_cleanup_orphans_sync, boot_time)
