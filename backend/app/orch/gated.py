from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import psycopg2
import psycopg2.extras

from app.orch import registry
from app.orch.disburse_guard import cross_owner_refusal
from app.orch.gated_postcommit import emit_approval as _emit_approval
from app.orch.gated_postcommit import notify_disbursed as _notify_disbursed
from app.orch.gated_postcommit import notify_pending_doorbell as _notify_pending_doorbell
from app.orch.gated_postcommit import text_payload as _text
from app.orch.gated_types import ConnLike, Receipt
from app.orch.ops_bridge import OpsDisburseBlocked
from app.orch.verdict import auto_approve_threshold, gated_decision
from app.storage import connect_core

log = logging.getLogger("orch.gated")


GATED_WHITELIST = {"disburse", "ops_disburse"}


NON_BIZ_FIELDS = {"ts", "timestamp", "note", "ghi_chu", "_meta"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def payload_hash(action: str, args: dict[str, Any]) -> str:

    biz = {
        k: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
        for k, v in sorted(args.items())
        if v is not None and k not in NON_BIZ_FIELDS
    }
    canon = json.dumps({"action": action, **biz}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:16]


def approval_idempotency_key(conv_id: str, action: str, digest: str) -> str:
    """Stable business-intent key. DB trigger mirrors this for legacy/raw writers."""
    return f"idem:v1:{conv_id}:{action}:{digest}"


def _summarize(args: dict[str, Any]) -> str:

    parts = [f"{k}={v}" for k, v in args.items() if k not in NON_BIZ_FIELDS and v is not None]
    return ", ".join(parts)


def disburse(conn: ConnLike, loan_id: str, amount: float = 0) -> Receipt:

    with conn.cursor() as cur:
        cur.execute("UPDATE loans SET status='disbursed' WHERE loan_id=%s", (loan_id,))
        if cur.rowcount == 0:
            raise ValueError(f"loan '{loan_id}' does not exist")
    return {"disbursed": True, "loan_id": loan_id, "amount": amount, "asOf": _now()}


def _ops_disburse_inner(conn: ConnLike, **args: Any) -> Receipt:

    from app.orch.ops_bridge import run_ops_disburse

    return run_ops_disburse(conn, **args)  # type: ignore[return-value]


GATED_TOOLS: dict[str, Callable[..., Receipt]] = {"disburse": disburse, "ops_disburse": _ops_disburse_inner}


GATED_ROLE: dict[str, str] = {"disburse": "operations", "ops_disburse": "operations"}


class _GatedResult:
    def __init__(
        self, payload: dict[str, Any], emit: dict[str, Any] | None = None, fresh_disburse: bool = False
    ) -> None:
        self.payload = payload
        self.emit = emit

        self.fresh_disburse = fresh_disburse


def _finalize_receipt(cur: Any, out: Receipt, approval_id: Any) -> None:
    """Final state is one statement so the DB can enforce used iff receipt+used_at."""
    cur.execute(
        "UPDATE approvals SET status='used',receipt=%s,used_at=now() WHERE id=%s AND status='approved'",
        (json.dumps(out), approval_id),
    )
    if cur.rowcount != 1:
        raise RuntimeError("approval claim was lost before receipt finalization")


def _branch_receipt_replay(conn: ConnLike, cur: Any, ctx: dict[str, Any]) -> _GatedResult | None:

    cur.execute(
        "SELECT receipt FROM approvals WHERE idempotency_key=%s AND status='used' LIMIT 1",
        (ctx["idempotency_key"],),
    )
    row = cur.fetchone()
    if row and row["receipt"] is not None:
        conn.commit()
        return _GatedResult({**row["receipt"], "hint": "This action was already executed; this is its receipt."})
    return None


def _branch_claim(conn: ConnLike, cur: Any, ctx: dict[str, Any]) -> _GatedResult | None:
    """2. Lock approved row, run once, then atomically write used+receipt+used_at."""
    cur.execute(
        "SELECT id FROM approvals WHERE idempotency_key=%s AND status='approved' FOR UPDATE LIMIT 1",
        (ctx["idempotency_key"],),
    )
    claimed = cur.fetchone()
    if not claimed:
        return None
    # Advisory lock serializes the intent; row lock protects direct DB writers as a second layer.
    out = GATED_TOOLS[ctx["action"]](conn, **ctx["args"])
    _finalize_receipt(cur, out, claimed["id"])
    conn.commit()
    return _GatedResult(out, fresh_disburse=True)


def _branch_pending(conn: ConnLike, cur: Any, ctx: dict[str, Any]) -> _GatedResult | None:

    cur.execute(
        "SELECT id FROM approvals WHERE idempotency_key=%s AND status='pending' LIMIT 1",
        (ctx["idempotency_key"],),
    )
    if not cur.fetchone():
        return None
    conn.commit()
    return _GatedResult(
        {
            "code": "approval_pending",
            "message": f"'{ctx['action']}' with these exact parameters is awaiting approval",
            "hint": "Notify main and end the turn; the session resumes when a decision is available.",
            "retryable": False,
        }
    )


def _branch_terminal(conn: ConnLike, cur: Any, ctx: dict[str, Any]) -> _GatedResult | None:
    """A rejected/failed intent is terminal; retry needs a changed intent instead of a duplicate row."""
    cur.execute(
        "SELECT status,reason FROM approvals WHERE idempotency_key=%s AND status IN ('rejected','exec_failed') LIMIT 1",
        (ctx["idempotency_key"],),
    )
    row = cur.fetchone()
    if row is None:
        return None
    conn.commit()
    failed = row["status"] == "exec_failed"
    return _GatedResult(
        {
            "code": "approval_execution_failed" if failed else "approval_rejected",
            "message": "This action failed and requires manual review."
            if failed
            else "This action was rejected by the approver.",
            "hint": row["reason"]
            or ("Contact operations for resolution." if failed else "Change the request before resubmitting it."),
            "retryable": False,
        }
    )


def _branch_auto(conn: ConnLike, cur: Any, ctx: dict[str, Any], reason: str) -> _GatedResult:

    conv_id, action, task_id, args, ph = ctx["conv_id"], ctx["action"], ctx["task_id"], ctx["args"], ctx["ph"]
    inner_out = GATED_TOOLS[action](conn, **args)
    out: Receipt = {**inner_out, "auto_approved": True, "approved_by": "auto-rule", "note": reason}
    cur.execute(
        "INSERT INTO approvals (conv_id,task_id,action,payload,payload_hash,idempotency_key,status,"
        "decided_by,decided_at,reason,used_at,receipt) "
        "VALUES (%s,%s,%s,%s,%s,%s,'used','auto-rule',now(),%s,now(),%s)",
        (
            conv_id,
            task_id or None,
            action,
            json.dumps(args),
            ph,
            ctx["idempotency_key"],
            reason,
            json.dumps(out),
        ),
    )

    notice = {
        "type": "document",
        "title": f"✅ Automatically approved and executed: {action} ({_summarize(args)})",
        "items": [
            {"section": "Mechanism", "content": reason},
            {"section": "Result", "content": json.dumps(out, ensure_ascii=False)},
        ],
        "sources": ["tiered brake — auto-rule"],
    }
    cur.execute(
        "INSERT INTO cards (conv_id, task_id, type, data, ts) "
        "VALUES (%s, %s, 'document', %s, now()) RETURNING id, conv_id, task_id, type, data, ts",
        (conv_id, task_id or None, json.dumps(notice)),
    )
    card_row = dict(cur.fetchone())
    conn.commit()
    return _GatedResult(out, emit={"card": card_row, "conv_id": conv_id, "auto": True}, fresh_disburse=True)


def _branch_human(conn: ConnLike, cur: Any, ctx: dict[str, Any]) -> _GatedResult:

    conv_id, action, task_id, args, ph = ctx["conv_id"], ctx["action"], ctx["task_id"], ctx["args"], ctx["ph"]
    snapshot = ctx["snapshot"]
    cur.execute(
        "INSERT INTO approvals (conv_id, task_id, action, payload, payload_hash, idempotency_key, status, "
        "system_assessment_id, system_lane, system_recommendation) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s) RETURNING id",
        (
            conv_id,
            task_id or None,
            action,
            json.dumps(args),
            ph,
            ctx["idempotency_key"],
            snapshot["system_assessment_id"],
            snapshot["system_lane"],
            snapshot["system_recommendation"],
        ),
    )
    approval_id = str(cur.fetchone()["id"])

    card_data = {
        "type": "approval",
        "title": f"Approve: {action} ({_summarize(args)})",
        "action": action,
        "approval_id": approval_id,
        "items": [{"label": k, "value": v} for k, v in args.items() if k not in NON_BIZ_FIELDS],
        "options": ["Approve", "Reject"],
        "status": "pending",
    }
    cur.execute(
        "INSERT INTO cards (conv_id, task_id, type, data, ts) "
        "VALUES (%s, %s, 'approval', %s, now()) RETURNING id, conv_id, task_id, type, data, ts",
        (conv_id, task_id or None, json.dumps(card_data)),
    )
    card_row = dict(cur.fetchone())
    cur.execute("UPDATE conversations SET status='waiting_approval' WHERE id::text=%s", (conv_id,))
    conn.commit()
    return _GatedResult(
        {
            "code": "approval_required",
            "message": f"'{action}' ({_summarize(args)}) requires human approval",
            "hint": "The approval request was submitted. End the turn immediately and reply only that it is awaiting "
            "approval; do not add analysis or narration. The system resumes after approval.",
            "retryable": False,
        },
        emit={"card": card_row, "approval_id": approval_id, "conv_id": conv_id, "action": action, "payload": args},
    )


def _linked_preassessment_refusal(cur: Any, conv_id: str) -> dict[str, Any] | None:
    """D-81 choke point: a tenant-consistent intake link makes every money branch unreachable."""
    cur.execute(
        "SELECT 1 FROM conversations c JOIN external_case_links e "
        "ON e.conversation_id=c.id AND e.tenant_id=c.tenant_id "
        "WHERE c.id::text=%s LIMIT 1",
        (conv_id,),
    )
    if cur.fetchone() is None:
        return None
    return {
        "code": "preassessment_only",
        "message": "This intake session is for pre-assessment only and cannot perform disbursement actions.",
        "hint": "Hand the case over to the bank's separately configured approval process.",
        "retryable": False,
    }


def _gated_txn(
    action: str,
    conv_id: str,
    task_id: str | None,
    args: dict[str, Any],
    threshold_vnd: float | None = None,
) -> _GatedResult:

    guard_conn = connect_core()
    try:
        with guard_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as guard_cur:
            refusal = _linked_preassessment_refusal(guard_cur, conv_id)
        guard_conn.rollback()
    finally:
        guard_conn.close()
    if refusal is not None:
        return _GatedResult(refusal)

    if threshold_vnd is None:
        threshold_vnd = auto_approve_threshold()
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            refusal = _linked_preassessment_refusal(cur, conv_id)
            if refusal is not None:
                conn.rollback()
                return _GatedResult(refusal)

            if action == "disburse":
                refusal = cross_owner_refusal(cur, conv_id, args.get("loan_id"))
                if refusal is not None:
                    conn.rollback()
                    return _GatedResult(refusal)

            ph = payload_hash(action, args)

            idempotency_key = approval_idempotency_key(conv_id, action, ph)
            lock_key = int(hashlib.sha256(idempotency_key.encode()).hexdigest()[:15], 16) & 0x7FFFFFFFFFFFFFFF
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))

            ctx = {
                "action": action,
                "conv_id": conv_id,
                "task_id": task_id,
                "args": args,
                "ph": ph,
                "idempotency_key": idempotency_key,
            }

            for branch in (_branch_receipt_replay, _branch_claim, _branch_pending, _branch_terminal):
                result = branch(conn, cur, ctx)
                if result is not None:
                    return result

            decision, reason, snapshot = gated_decision(action, conn, args, threshold_vnd)
            if decision == "auto":
                return _branch_auto(conn, cur, ctx, reason)
            ctx["snapshot"] = snapshot
            return _branch_human(conn, cur, ctx)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def gated(action: str, inner_read_handler: Callable) -> Callable:

    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        conv_id = registry.CTX_CONV.get()
        task_id = registry.CTX_TASK.get() or None
        try:
            result: _GatedResult = await asyncio.to_thread(_gated_txn, action, conv_id, task_id, args)
        except OpsDisburseBlocked as e:
            return _text(e.payload)
        except Exception as e:  # noqa: BLE001
            log.exception("gated action %s failed", action)
            return _text(
                {
                    "code": "gated_error",
                    "message": str(e)[:200],
                    "hint": "Internal brake error; retry once, then report it to main if the error recurs.",
                    "retryable": True,
                }
            )

        if result.emit is not None:
            _emit_approval(result.emit)

            _notify_pending_doorbell(result.emit)

        if action == "disburse" and result.fresh_disburse:
            _notify_disbursed(conv_id, result.payload)
        return _text(result.payload)

    return handler
