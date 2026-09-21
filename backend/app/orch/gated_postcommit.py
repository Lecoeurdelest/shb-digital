from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger("orch.gated")


def notify_disbursed(conv_id: str, receipt: dict[str, Any]) -> None:

    from app.notify.email import render_email_html
    from app.notify.hooks import app_url, notify_conv_owner, owner_greeting

    amount = int(float(receipt.get("amount"))) if receipt.get("amount") else 0
    loan = receipt.get("loan_id", "")
    amount_str = f" for {amount:,} VND" if amount else ""
    body = f"Dear customer,\n\nLoan {loan}{amount_str} was successfully DISBURSED.\n\nSincerely,\nBANK Digital."
    data = {
        "greeting_name": owner_greeting(conv_id),
        "loan_id": loan,
        "amount_vnd": amount,
        "decided_by": receipt.get("approved_by"),
        "ref": loan,
        "app_url": app_url(),
    }
    html_body = render_email_html("disbursed", data)
    amount_disp = f"{amount:,}".replace(",", ".")
    notify_conv_owner(
        conv_id,
        f"💸 Disbursement completed {amount_disp} VND — BANK Digital",
        body,
        html_body,
    )


def emit_approval(emit_data: dict[str, Any]) -> None:

    try:
        from app.orch.store import _card_to_dict
        from app.sse.emit import emit, emit_conversation_status

        card = _card_to_dict(emit_data["card"])
        emit(emit_data["conv_id"], "card", {"card": card})
        if emit_data.get("auto"):
            return
        emit(
            emit_data["conv_id"],
            "approval.pending",
            {"phieu": {"id": emit_data["approval_id"], "action": emit_data["action"], "status": "pending"}},
        )
        emit_conversation_status(emit_data["conv_id"], "waiting_approval")
    except Exception:  # noqa: BLE001
        log.exception("failed to emit approval event (ignored)")


def notify_pending_doorbell(emit_data: dict[str, Any]) -> None:

    if emit_data.get("auto"):
        return
    try:
        from app.notify.channels import notify_channel_approval_pending

        notify_channel_approval_pending(emit_data)
    except Exception as exc:  # noqa: BLE001
        log.warning("failed to send pending approval notification exception=%s", type(exc).__name__)


def text_payload(payload: dict[str, Any]) -> dict[str, Any]:

    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}
