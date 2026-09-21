from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import psycopg2
import psycopg2.extras

from app.db.config import DATABASE_URL
from app.storage import connect_core

log = logging.getLogger("orch.audit")


_AUDIT_FILTERS = {"task_id", "conv_id", "tool", "actor"}
_DEFAULT_DATABASE_URL = DATABASE_URL


def _connect():

    if DATABASE_URL != _DEFAULT_DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return connect_core()


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:

    return {
        "id": str(row["id"]),
        "task_id": str(row["task_id"]) if row.get("task_id") else None,
        "conv_id": row.get("conv_id"),
        "ts": row["ts"].isoformat() if row.get("ts") else None,
        "actor": row["actor"],
        "tool": row["tool"],
        "input": row.get("input"),
        "output": row.get("output"),
        "cost": row.get("cost"),
    }


def _safe_json(v: Any) -> str | None:

    if v is None:
        return None
    try:
        return json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        return json.dumps(str(v), ensure_ascii=False)


def _record_sync(
    task_id: str | None,
    conv_id: str | None,
    actor: str,
    tool: str,
    tool_input: Any,
    output: Any,
    cost: Any,
) -> dict[str, Any] | None:

    in_j, out_j, cost_j = _safe_json(tool_input), _safe_json(output), _safe_json(cost)
    try:
        conn = _connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO tool_calls (task_id, conv_id, actor, tool, input, output, cost) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                    "RETURNING id, task_id, conv_id, ts, actor, tool, input, output, cost",
                    (task_id or None, conv_id or None, actor, tool, in_j, out_j, cost_j),
                )
                row = cur.fetchone()
            conn.commit()
            return _row_to_dict(dict(row))
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        log.warning("failed to record tool_call (ignored; audit is best-effort): %s", e)
        return None


def _query_sync(filters: dict[str, str], limit: int, tenant_id: str | None = None) -> list[dict[str, Any]]:

    where = []
    params: list[Any] = []
    for k, v in filters.items():
        if k in _AUDIT_FILTERS and v:
            where.append(f"{k} = %s")
            params.append(v)
    if tenant_id is not None:
        where.append("tenant_id = %s")
        params.append(tenant_id)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(limit)
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT id, task_id, conv_id, ts, actor, tool, input, output, cost FROM tool_calls "
                f"{clause} ORDER BY ts DESC LIMIT %s",
                tuple(params),
            )
            return [_row_to_dict(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


# Async wrappers (D-22: run synchronous work through to_thread).
async def record_tool_call(
    task_id: str | None,
    conv_id: str | None,
    actor: str,
    tool: str,
    tool_input: Any = None,
    output: Any = None,
    cost: Any = None,
) -> dict[str, Any] | None:

    return await asyncio.to_thread(_record_sync, task_id, conv_id, actor, tool, tool_input, output, cost)


async def query_tool_calls(
    filters: dict[str, str], limit: int = 200, tenant_id: str | None = None
) -> list[dict[str, Any]]:

    return await asyncio.to_thread(_query_sync, filters, limit, tenant_id)
