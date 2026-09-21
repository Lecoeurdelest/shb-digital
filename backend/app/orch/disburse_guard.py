from __future__ import annotations

import logging
from typing import Any

import psycopg2

log = logging.getLogger("orch.disburse_guard")

_NOT_YOUR_LOAN = {
    "code": "not_your_loan",
    "message": "The loan does not belong to the customer's case",
    "hint": "Only disburse a loan that belongs to the same customer case. Check the loan ID.",
    "retryable": False,
}


def cross_owner_refusal(cur: Any, conv_id: str, loan_id: str | None) -> dict[str, Any] | None:

    try:
        cur.execute(
            "SELECT u.role, u.owner_id FROM conversations c JOIN users u ON c.user_id=u.username WHERE c.id::text=%s",
            (conv_id,),
        )
        row = cur.fetchone()

        if not row or row["role"] != "customer":
            return None
        creator_owner = row["owner_id"]
        if not creator_owner:
            return dict(_NOT_YOUR_LOAN)
        cur.execute("SELECT owner_id FROM loans WHERE loan_id=%s", (loan_id,))
        lrow = cur.fetchone()
        if not lrow or lrow["owner_id"] != creator_owner:
            return dict(_NOT_YOUR_LOAN)
        return None
    except psycopg2.Error as e:
        log.warning("cross-owner guard lookup failed conv=%s loan=%s; refusing fail-closed: %s", conv_id, loan_id, e)
        return dict(_NOT_YOUR_LOAN)
