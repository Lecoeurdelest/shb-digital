from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.auth.deps import require_admin
from app.errors import ApiError
from app.orch import store_approvals
from app.tenancy import tenant_id_from_claims

log = logging.getLogger("api.approvals")

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class DecideBody(BaseModel):
    decision: str  # approved | rejected
    reason: str | None = None


@router.get("")
async def list_approvals(status: str = Query("pending"), claims: dict = Depends(require_admin)) -> list[dict[str, Any]]:

    if status != "pending":
        raise ApiError(
            400,
            "bad_status",
            f"status '{status}' is not supported.",
            "Only status=pending is supported in S3.",
            retryable=False,
        )
    return await store_approvals.list_pending(tenant_id=tenant_id_from_claims(claims))


@router.get("/{approval_id}")
async def get_approval(approval_id: str, claims: dict = Depends(require_admin)) -> dict[str, Any]:

    approval = await store_approvals.get_approval(approval_id, tenant_id_from_claims(claims))
    if approval is None:
        raise ApiError(
            404,
            "not_found",
            f"Approval '{approval_id}' does not exist.",
            "Check the ID or link.",
            retryable=False,
        )
    return approval


@router.post("/{approval_id}/decide")
async def decide(approval_id: str, body: DecideBody, claims: dict = Depends(require_admin)) -> dict[str, Any]:

    if not store_approvals.valid_decision(body.decision):
        raise ApiError(
            400,
            "bad_decision",
            f"decision '{body.decision}' is invalid.",
            "Use 'approved' or 'rejected'.",
            retryable=False,
        )

    decided = await store_approvals.decide(
        approval_id,
        body.decision,
        decided_by=claims.get("username", "admin"),
        reason=body.reason,
        tenant_id=tenant_id_from_claims(claims),
    )
    if decided is None:
        if await store_approvals.approval_exists(approval_id, tenant_id_from_claims(claims)):
            raise ApiError(
                409,
                "approval_already_decided",
                "The approval has already been decided.",
                "Reload the approval queue.",
                retryable=False,
            )
        raise ApiError(404, "not_found", f"Approval '{approval_id}' does not exist.", "Check the ID.", retryable=False)

    _emit_and_wake(decided)

    _notify_channel_decided(decided)

    _notify_decided(decided)
    decided.pop("_card_row", None)
    return decided


def _notify_channel_decided(decided: dict[str, Any]) -> None:

    try:
        from app.notify.channels import notify_channel_approval_decided

        notify_channel_approval_decided(decided)
    except Exception as exc:  # noqa: BLE001
        log.warning("failed to send approval decision notification exception=%s", type(exc).__name__)


def _notify_decided(decided: dict[str, Any]) -> None:

    from app.notify.email import render_email_html
    from app.notify.hooks import app_url, notify_conv_owner, owner_greeting

    approved = decided.get("status") in ("used", "approved")
    kind = "approved" if approved else "rejected"
    verb = "approved" if approved else "rejected"
    payload = decided.get("payload") or {}
    amount = int(float(payload.get("amount"))) if payload.get("amount") else 0
    loan_id = payload.get("loan_id", "")
    amount_str = f" for {amount:,} VND" if amount else ""
    reason_txt = "" if approved else (decided.get("reason") or "").strip()
    reason_line = f"\n\nReason: {reason_txt}" if reason_txt else ""  # plain fallback (client text-only)
    body = (
        f"Dear customer,\n\nYour request '{decided.get('action')}'{amount_str} has been "
        f"{verb}.{reason_line}\n\nSincerely,\nBANK Digital."
    )
    d = {
        "greeting_name": owner_greeting(decided["conv_id"]),
        "loan_id": loan_id,
        "amount_vnd": amount,
        "decided_by": decided.get("decided_by"),
        "decided_at": decided.get("decided_at"),
        "ref": decided.get("id"),
        "app_url": app_url(),
    }

    if not approved and (decided.get("reason") or "").strip():
        d["reject_reason"] = decided["reason"].strip()
    html_body = render_email_html(kind, d)
    icon = "✅" if approved else "✖️"
    subject = f"{icon} Loan {loan_id} was {verb} — BANK Digital"
    notify_conv_owner(decided["conv_id"], subject, body, html_body)


def _emit_and_wake(decided: dict[str, Any]) -> None:

    from app.orch.room import handle_room_event
    from app.sse.emit import emit

    conv_id = decided["conv_id"]

    emit(
        conv_id,
        "approval.decided",
        {
            "phieu": {
                "id": decided["id"],
                "action": decided["action"],
                "status": decided["status"],
                "decided_by": decided["decided_by"],
                "reason": decided["reason"],
            }
        },
    )

    card_row = decided.get("_card_row")
    if card_row is not None:
        from app.orch.store import _card_to_dict

        emit(conv_id, "card", {"card": _card_to_dict(card_row)})

    payload = {
        "approval_id": decided["id"],
        "action": decided["action"],
        "decision": decided["status"],  # approved | rejected
        "payload": decided.get("payload") or {},
        "reason": decided.get("reason"),
    }

    async def _wake_guarded() -> None:

        try:
            await handle_room_event(conv_id, "approval_decided", payload)
        except Exception as e:  # noqa: BLE001
            log.error("failed to resume after approval decision conv=%s: %s", conv_id, e)

    asyncio.ensure_future(_wake_guarded())
