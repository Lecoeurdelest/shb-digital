from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, StrictBool

from app import consent
from app.auth.deps import can_access_conv, require_user
from app.errors import ApiError
from app.orch.common_tools import FORM_REQUIRED
from app.orch.store import get_conversation
from app.storage import connect_core
from app.tenancy import tenant_id_from_claims

log = logging.getLogger("api.form_intake")

router = APIRouter(prefix="/api/conversations", tags=["form-intake"])


_MINT_LOCK_KEY = 0x0900000000000001


_CUSTOMER_COLS = ("full_name", "id_number", "address", "occupation", "monthly_income")


class FormSubmitBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_id: UUID
    values: dict[str, Any]
    consent_granted: StrictBool = False


@router.post("/{conv_id}/form-submit")
async def form_submit(conv_id: str, body: FormSubmitBody, claims: dict = Depends(require_user)) -> dict[str, Any]:

    if claims.get("role") != "customer":
        raise ApiError(
            403,
            "forbidden",
            "Only customers may submit this application form.",
            "Sign in with the customer account that owns this case.",
            retryable=False,
        )

    conv = await get_conversation(conv_id)
    if conv is None or not can_access_conv(conv, claims):
        raise ApiError(404, "not_found", "The conversation was not found.", "Check the ID.", retryable=False)

    if body.consent_granted is not True:
        raise ApiError(
            400,
            "consent_required",
            "Consent to data processing is required before submitting the application.",
            "Read the form wording and select the consent checkbox if you agree.",
            retryable=True,
        )
    try:
        wording = consent.load_wording()
    except consent.ConsentWordingError as exc:
        raise ApiError(
            400,
            "consent_wording_invalid",
            "The server-side consent wording is invalid.",
            "Stop the submission and ask an administrator to check the wording.",
            retryable=False,
        ) from exc

    values = body.values or {}
    missing = [f for f in FORM_REQUIRED if not str(values.get(f, "")).strip()]
    if missing:
        raise ApiError(
            400,
            "missing_fields",
            f"Required information is missing: {missing}",
            "Complete all required fields and submit again.",
            retryable=True,
        )
    try:
        income = int(float(values["monthly_income"]))
    except (TypeError, ValueError) as e:
        raise ApiError(
            400, "bad_income", "Income must be numeric.", "Enter a VND amount, for example 15000000.", retryable=True
        ) from e

    import asyncio

    result = await asyncio.to_thread(
        _submit_txn,
        conv_id,
        str(claims.get("sub") or ""),
        tenant_id_from_claims(claims),
        str(body.card_id),
        values,
        income,
        wording,
    )
    if result == "already_submitted":
        raise ApiError(
            409,
            "form_already_submitted",
            "The application has already been submitted.",
            "Do not submit it again.",
            retryable=False,
        )
    if result == "card_not_found":
        raise ApiError(404, "not_found", "The application form was not found.", "Reload the page.", retryable=False)
    if result == "consent_wording_unavailable":
        raise ApiError(
            409,
            "consent_wording_unavailable",
            "The legacy form has no consent wording snapshot.",
            "Reload and ask the system to create a new form.",
            retryable=False,
        )
    if result == "consent_wording_invalid":
        raise ApiError(
            400,
            "consent_wording_invalid",
            "The form consent wording snapshot is invalid.",
            "Reload the form; if the error persists, contact an administrator.",
            retryable=False,
        )

    await _wake_main(conv_id, result, values)
    return {"owner_id": result["owner_id"], "customer_created": True}


def _submit_txn(
    conv_id: str,
    user_id: str,
    tenant_id: str,
    card_id: str,
    values: dict,
    income: int,
    wording: consent.ConsentWording,
) -> Any:
    """1 tx: lock+validate card → flip → customer → user link → consent append."""
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT data FROM cards WHERE id=%s AND conv_id=%s AND type='form' FOR UPDATE",
                (card_id, conv_id),
            )
            card = cur.fetchone()
            if card is None:
                conn.rollback()
                return "card_not_found"
            card_data = card["data"] if isinstance(card["data"], dict) else {}
            if card_data.get("status") == "submitted":
                conn.rollback()
                return "already_submitted"
            if "consent" not in card_data:
                conn.rollback()
                return "consent_wording_unavailable"
            if card_data.get("status") != "pending" or not consent.snapshot_matches(card_data["consent"], wording):
                conn.rollback()
                return "consent_wording_invalid"
            cur.execute(
                "UPDATE cards SET data = jsonb_set(data, '{status}', '\"submitted\"') WHERE id=%s",
                (card_id,),
            )

            cur.execute("SELECT pg_advisory_xact_lock(%s)", (_MINT_LOCK_KEY,))
            owner_id = _next_c9xx(cur)
            cur.execute(
                f"INSERT INTO customers (id, {', '.join(_CUSTOMER_COLS)}) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    owner_id,
                    values["full_name"],
                    values["id_number"],
                    values["address"],
                    values["occupation"],
                    income,
                ),
            )

            cur.execute(
                "UPDATE users SET owner_id=%s WHERE id::text=%s AND tenant_id=%s",
                (owner_id, user_id, tenant_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError("form submit actor is not present in the JWT tenant")
            consent.insert_record(
                cur,
                tenant_id=tenant_id,
                subject_ref=user_id,
                actor=user_id,
                source_ref=card_id,
                wording=wording,
            )
            conn.commit()
            return {"owner_id": owner_id, "full_name": values["full_name"]}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _next_c9xx(cur: Any) -> str:

    cur.execute("SELECT id FROM customers WHERE id LIKE 'C9%%' ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    n = (int(row["id"][2:]) + 1) if row else 1
    return f"C9{n:02d}"


async def _wake_main(conv_id: str, result: dict, values: dict) -> None:

    from app.orch.room import handle_room_event

    content = (
        f"[APPLICATION SUBMITTED] Full name: {values.get('full_name')} · ID number: {values.get('id_number')} · "
        f"Occupation: {values.get('occupation')} · Income: {values.get('monthly_income')} VND · "
        f"Loan purpose: {values.get('loan_purpose')}. Application created (ID {result['owner_id']}); "
        f"continue the assessment or request more information if needed."
    )
    try:
        await handle_room_event(conv_id, "user_message", {"content": content})
    except Exception as e:  # noqa: BLE001
        log.error("failed to wake MAIN after form submission conv=%s: %s", conv_id, e)
