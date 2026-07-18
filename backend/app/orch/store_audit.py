"""Audit tool_calls (T4-1) — APPEND-ONLY persist + query. psycopg2 sync qua to_thread (D-22).

SPEC §10: tool_calls bất biến (KHÔNG update/delete — audit). Ghi lúc sub/main gọi tool → nền
trace/Control Tower/F1 + cost meter. §12 "audit lỗi KHÔNG fail request chính" → caller bọc
fire-and-forget (record_tool_call KHÔNG raise ra ngoài; lỗi DB → log, best-effort).

Tách khỏi store.py (D-34: file ≤400) — audit là concern riêng (append-only, không CRUD vòng đời).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import psycopg2
import psycopg2.extras

from app.db.config import DATABASE_URL

log = logging.getLogger("orch.audit")

# filter hợp lệ cho GET /api/audit (whitelist — chống SQL injection qua tên cột động).
_AUDIT_FILTERS = {"task_id", "conv_id", "tool", "actor"}


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Serialize tool_call row cho API/SSE (resource trần). id/task_id str; ts iso."""
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
    """Serialize jsonb TỪNG field độc lập — non-serializable (vd ToolResultBlock lạ) → str() fallback,
    KHÔNG để 1 field hỏng làm mất CẢ row (audit append-only: thà giữ input + output-dạng-str còn hơn
    mất record). None → None."""
    if v is None:
        return None
    try:
        return json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        return json.dumps(str(v), ensure_ascii=False)  # fallback: chuỗi hoá, vẫn là JSON hợp lệ


def _record_sync(
    task_id: str | None,
    conv_id: str | None,
    actor: str,
    tool: str,
    tool_input: Any,
    output: Any,
    cost: Any,
) -> dict[str, Any] | None:
    """INSERT 1 tool_call (append-only). Trả row (cho SSE emit). Lỗi → None + log (best-effort §12).

    Serialize từng field qua _safe_json (str fallback) TRƯỚC INSERT → 1 field non-serializable
    KHÔNG làm mất cả row (audit không được mất record vì output tool lạ)."""
    in_j, out_j, cost_j = _safe_json(tool_input), _safe_json(output), _safe_json(cost)
    try:
        conn = psycopg2.connect(DATABASE_URL)
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
    except Exception as e:  # noqa: BLE001 — audit best-effort: lỗi KHÔNG fail turn (§12)
        log.warning("record tool_call lỗi (bỏ qua — audit best-effort): %s", e)
        return None


def _query_sync(filters: dict[str, str], limit: int) -> list[dict[str, Any]]:
    """Query tool_calls theo filter (whitelist cột). Mới nhất trước. limit cap."""
    where = []
    params: list[Any] = []
    for k, v in filters.items():
        if k in _AUDIT_FILTERS and v:
            where.append(f"{k} = %s")
            params.append(v)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(limit)
    conn = psycopg2.connect(DATABASE_URL)
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


# ── async wrappers (D-22: sync qua to_thread) ───────────────────────────────
async def record_tool_call(
    task_id: str | None,
    conv_id: str | None,
    actor: str,
    tool: str,
    tool_input: Any = None,
    output: Any = None,
    cost: Any = None,
) -> dict[str, Any] | None:
    """Persist 1 tool_call (append-only). Trả row dict (cho SSE) hoặc None nếu lỗi (best-effort §12)."""
    return await asyncio.to_thread(_record_sync, task_id, conv_id, actor, tool, tool_input, output, cost)


async def query_tool_calls(filters: dict[str, str], limit: int = 200) -> list[dict[str, Any]]:
    """GET /api/audit — list tool_calls theo filter (whitelist cột)."""
    return await asyncio.to_thread(_query_sync, filters, limit)
