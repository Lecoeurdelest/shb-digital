from __future__ import annotations

import asyncio
import json
from typing import Any

import psycopg2
import psycopg2.extras

from app.orch import store_shadow
from app.storage import connect_core

# decision (API body) → approvals.status
_DECISION_STATUS = {"approved": "approved", "rejected": "rejected"}


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:

    return {
        "id": str(row["id"]),
        "conv_id": str(row["conv_id"]),
        "task_id": str(row["task_id"]) if row.get("task_id") else None,
        "action": row["action"],
        "payload": row.get("payload"),
        "payload_hash": row.get("payload_hash"),
        "status": row["status"],
        "decided_by": row.get("decided_by"),
        "decided_at": row["decided_at"].isoformat() if row.get("decided_at") else None,
        "reason": row.get("reason"),
        "used_at": row["used_at"].isoformat() if row.get("used_at") else None,
        "receipt": row.get("receipt"),
        "exec_attempts": row.get("exec_attempts", 0),  # T4-0 loop-bound
    }


#


#   · ops_disburse (Products/Ops): payload {application_id, amount_vnd} → applications.id → owner_id


#   eff_owner = COALESCE(loans.owner, applications.owner, customers.id=ref_id). customer_name follows eff_owner.

_ENRICH_SELECT = (
    "SELECT a.*, "
    "  COALESCE(a.payload->>'loan_id', a.payload->>'application_id') AS _disp_loan_id, "
    "  COALESCE(a.payload->>'amount', a.payload->>'amount_vnd') AS _disp_amount_raw, "
    "  COALESCE(l.owner_id, ap.owner_id, cf.id) AS _disp_owner_id, "
    "  COALESCE(cl.full_name, ca.full_name, cf.full_name) AS _disp_customer_name, "
    "  (SELECT s.lane FROM assessments s WHERE s.tenant_id=a.tenant_id "
    "     AND s.owner_id = COALESCE(l.owner_id, ap.owner_id, cf.id) "
    "     ORDER BY s.id DESC LIMIT 1) AS _disp_lane "
    "FROM approvals a "
    "LEFT JOIN loans l ON l.loan_id = a.payload->>'loan_id' "
    "LEFT JOIN customers cl ON cl.id = l.owner_id "
    "LEFT JOIN applications ap ON ap.id = a.payload->>'application_id' "
    "LEFT JOIN customers ca ON ca.id = ap.owner_id "
    "LEFT JOIN customers cf ON cf.id = COALESCE(a.payload->>'loan_id', a.payload->>'application_id') "
)


def _safe_int(raw: Any) -> int | None:

    if raw is None:
        return None
    try:
        return int(float(raw))
    except (ValueError, TypeError):
        return None


def _display_of(row: dict[str, Any]) -> dict[str, Any]:

    return {
        "customer_name": row.get("_disp_customer_name"),
        "owner_id": row.get("_disp_owner_id"),
        "loan_id": row.get("_disp_loan_id"),
        "amount_vnd": _safe_int(row.get("_disp_amount_raw")),
        "lane": row.get("_disp_lane"),
    }


def _enriched_dict(row: dict[str, Any]) -> dict[str, Any]:

    base = _row_to_dict(row)
    base["display"] = _display_of(row)
    return base


def _list_pending_sync(conv_id: str | None, tenant_id: str | None = None) -> list[dict[str, Any]]:
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            where = ["a.status='pending'"]
            params: list[Any] = []
            if tenant_id is not None:
                where.append("a.tenant_id=%s")
                params.append(tenant_id)
            if conv_id:
                where.append("a.conv_id=%s")
                params.append(conv_id)
            cur.execute(_ENRICH_SELECT + f" WHERE {' AND '.join(where)} ORDER BY a.id", tuple(params))
            return [_enriched_dict(dict(row)) for row in cur.fetchall()]
    finally:
        conn.close()


def _get_sync(approval_id: str, tenant_id: str | None = None) -> dict[str, Any] | None:

    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            tenant_clause = " AND a.tenant_id=%s" if tenant_id is not None else ""
            params = (approval_id, tenant_id) if tenant_id is not None else (approval_id,)
            cur.execute(_ENRICH_SELECT + f" WHERE a.id=%s{tenant_clause} LIMIT 1", params)
            row = cur.fetchone()
            return _enriched_dict(dict(row)) if row else None
    except psycopg2.errors.InvalidTextRepresentation:
        return None
    finally:
        conn.close()


def _decide_sync(
    approval_id: str,
    decision: str,
    decided_by: str,
    reason: str | None,
    tenant_id: str | None = None,
) -> dict[str, Any] | None:

    status = _DECISION_STATUS[decision]
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            tenant_clause = " AND tenant_id=%s" if tenant_id is not None else ""
            params: tuple[Any, ...] = (
                (status, decided_by, reason, approval_id, tenant_id)
                if tenant_id is not None
                else (status, decided_by, reason, approval_id)
            )
            cur.execute(
                "UPDATE approvals SET status=%s, decided_by=%s, decided_at=now(), reason=%s "
                f"WHERE id=%s AND status='pending'{tenant_clause} RETURNING *",
                params,
            )
            row = cur.fetchone()
            if row is None:
                conn.commit()
                return None

            store_shadow.insert_review(cur, dict(row))

            cur.execute(
                "UPDATE cards SET data = data || %s::jsonb "
                "WHERE conv_id=%s AND type='approval' AND data->>'approval_id'=%s "
                "RETURNING id, conv_id, task_id, type, data, ts",
                (
                    json.dumps({"status": status, "decided_by": decided_by, "reason": reason}),
                    str(row["conv_id"]),
                    approval_id,
                ),
            )
            card_row = cur.fetchone()
        conn.commit()
        decided = _row_to_dict(dict(row))
        decided["_card_row"] = dict(card_row) if card_row else None
        return decided
    except psycopg2.errors.InvalidTextRepresentation:
        return None
    finally:
        conn.close()


MAX_EXEC_ATTEMPTS = 3


def _peek_grant_sync(conv_id: str) -> dict[str, Any] | None:

    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM approvals WHERE conv_id=%s AND status='approved' AND used_at IS NULL "
                "ORDER BY id LIMIT 1",
                (conv_id,),
            )
            row = cur.fetchone()
            return _row_to_dict(dict(row)) if row else None
    finally:
        conn.close()


def _claim_exec_attempt_sync(approval_id: str) -> int:

    conn = connect_core()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE approvals SET exec_attempts = exec_attempts + 1 WHERE id=%s RETURNING exec_attempts",
                (approval_id,),
            )
            row = cur.fetchone()
        conn.commit()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def _mark_exec_failed_sync(approval_id: str) -> None:

    conn = connect_core()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE approvals SET status='exec_failed' WHERE id=%s AND status='approved' AND used_at IS NULL",
                (approval_id,),
            )
        conn.commit()
    finally:
        conn.close()


def _exists_sync(approval_id: str, tenant_id: str | None = None) -> bool:

    conn = connect_core()
    try:
        with conn.cursor() as cur:
            tenant_clause = " AND tenant_id=%s" if tenant_id is not None else ""
            params = (approval_id, tenant_id) if tenant_id is not None else (approval_id,)
            cur.execute(f"SELECT 1 FROM approvals WHERE id=%s{tenant_clause}", params)
            return cur.fetchone() is not None
    except psycopg2.Error:
        return False
    finally:
        conn.close()


# Async wrappers (D-22: run synchronous work through to_thread).
async def list_pending(conv_id: str | None = None, tenant_id: str | None = None) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_pending_sync, conv_id, tenant_id)


async def get_approval(approval_id: str, tenant_id: str | None = None) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_sync, approval_id, tenant_id)


async def decide(
    approval_id: str,
    decision: str,
    decided_by: str,
    reason: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any] | None:
    return await asyncio.to_thread(_decide_sync, approval_id, decision, decided_by, reason, tenant_id)


async def approval_exists(approval_id: str, tenant_id: str | None = None) -> bool:
    return await asyncio.to_thread(_exists_sync, approval_id, tenant_id)


async def peek_grant(conv_id: str) -> dict[str, Any] | None:

    return await asyncio.to_thread(_peek_grant_sync, conv_id)


async def claim_exec_attempt(approval_id: str) -> int:

    return await asyncio.to_thread(_claim_exec_attempt_sync, approval_id)


async def mark_exec_failed(approval_id: str) -> None:

    return await asyncio.to_thread(_mark_exec_failed_sync, approval_id)


def valid_decision(decision: str) -> bool:
    return decision in _DECISION_STATUS
