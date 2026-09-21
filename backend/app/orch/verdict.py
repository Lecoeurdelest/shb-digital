from __future__ import annotations

import logging
import math
from typing import Any

import psycopg2
import psycopg2.extras

from app.db.config import DATABASE_URL
from app.storage import connect_core
from app.tenancy import DEFAULT_TENANT_ID

log = logging.getLogger("orch.verdict")


AUTO_APPROVE_THRESHOLD = 500_000_000  # VND
_AUTO_MAX_FALLBACK = 2_000_000_000.0
_DEFAULT_DATABASE_URL = DATABASE_URL


def _connect():

    if DATABASE_URL != _DEFAULT_DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return connect_core()


def auto_approve_threshold() -> float:

    conn = None
    try:
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM assumptions WHERE key='auto_approve_threshold_vnd'")
            row = cur.fetchone()
            if row is None:
                return float(AUTO_APPROVE_THRESHOLD)
            value = float(row[0])
            if not math.isfinite(value):
                raise ValueError("threshold must be finite")
            return value
    except (psycopg2.Error, TypeError, ValueError) as e:
        log.warning("failed to read auto_approve_threshold_vnd (fail-closed at 0): %s", e)
        return 0.0
    finally:
        if conn is not None:
            conn.close()


def auto_approve_max(conn: Any) -> float:

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM assumptions WHERE key='auto_approve_max_vnd'")
            row = cur.fetchone()
            if row and row[0] is not None:
                return float(row[0])
    except (psycopg2.Error, TypeError, ValueError) as e:
        log.warning("failed to read auto_approve_max_vnd (fallback 2e9): %s", e)
    return _AUTO_MAX_FALLBACK


def latest_verdict_for_action(action: str, args: dict[str, Any]) -> dict[str, Any] | None:

    conn = None
    try:
        conn = _connect()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            from app.orch import registry

            tenant_id = DEFAULT_TENANT_ID
            conv_id = registry.CTX_CONV.get()
            if conv_id:
                cur.execute("SELECT tenant_id::text FROM conversations WHERE id::text=%s", (conv_id,))
                tenant_row = cur.fetchone()
                if tenant_row:
                    tenant_id = tenant_row["tenant_id"]
            if action == "disburse":
                ref = args.get("loan_id")
                query = "SELECT owner_id FROM loans WHERE loan_id=%s"
            elif action == "ops_disburse":
                ref = args.get("application_id")
                query = "SELECT owner_id FROM applications WHERE id=%s"
            else:
                return None
            if not ref:
                return None
            cur.execute(query, (ref,))
            lrow = cur.fetchone()
            if not lrow or not lrow["owner_id"]:
                return None
            cur.execute(
                "SELECT id, lane FROM assessments WHERE tenant_id=%s AND owner_id=%s "
                "ORDER BY created_at DESC, id DESC LIMIT 1",
                (tenant_id, lrow["owner_id"]),
            )
            arow = cur.fetchone()
            return dict(arow) if arow else None
    except psycopg2.Error as e:
        log.warning("failed to read assessment verdict action=%s (treating as no verdict): %s", action, e)
        return None
    finally:
        if conn is not None:
            conn.close()


def latest_verdict(loan_id: str) -> dict[str, Any] | None:

    return latest_verdict_for_action("disburse", {"loan_id": loan_id})


def gated_decision(
    action: str, conn: Any, args: dict[str, Any], threshold_vnd: float
) -> tuple[str, str | None, dict[str, Any]]:

    amount_key = "amount" if action == "disburse" else "amount_vnd"
    try:
        amount = float(args.get(amount_key))
        if not math.isfinite(amount):
            raise ValueError("amount must be finite")
    except (TypeError, ValueError):
        amount = None

    verdict = latest_verdict_for_action(action, args)
    lane = verdict.get("lane") if verdict else None
    assessment_id = verdict.get("id") if verdict else None

    policy_threshold = threshold_vnd if threshold_vnd > 0 else float(AUTO_APPROVE_THRESHOLD)
    tier1_auto = action == "disburse" and amount is not None and amount < policy_threshold and lane != "red"
    tier2_auto = False
    if action == "disburse" and amount is not None and lane == "green" and not tier1_auto:
        tier2_auto = amount <= auto_approve_max(conn)

    if lane == "red":
        recommendation = "reject-recommended"
    elif tier1_auto or tier2_auto:
        recommendation = "auto-eligible"
    else:
        recommendation = "human-review"
    snapshot = {
        "system_assessment_id": assessment_id,
        "system_lane": lane,
        "system_recommendation": recommendation,
    }

    if action != "disburse" or amount is None or threshold_vnd <= 0 or lane == "red":
        return ("human", None, snapshot)
    if tier1_auto:
        reason = f"Automatically approved by rule: amount is below the {threshold_vnd:,.0f} VND threshold"
        return ("auto", reason, snapshot)
    if tier2_auto:
        reason = f"GREEN case — assessment #{assessment_id} (green lane, auto_approve_eligible)"
        return ("auto", reason, snapshot)
    return ("human", None, snapshot)


def disburse_decision(conn: Any, args: dict[str, Any], threshold_vnd: float | None = None) -> tuple[str, str | None]:

    threshold = float(AUTO_APPROVE_THRESHOLD) if threshold_vnd is None else threshold_vnd
    decision, reason, _snapshot = gated_decision("disburse", conn, args, threshold)
    return decision, reason
