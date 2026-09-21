"""Write-time gate for the canonical six-section credit memo (S23 · D-82)."""

from __future__ import annotations

import copy
import math
from typing import Any

from app.orch.main_skill import CREDIT_MEMO_SECTIONS, CREDIT_MEMO_TITLE
from app.reason_taxonomy import ReasonTaxonomy, get_reason_taxonomy

_COUNTER_KEYS = {
    "product_id",
    "product_name",
    "proposed_amount_vnd",
    "loan_type",
    "rationale",
    "terms",
    "proof",
}
_TERM_FIELDS = {"rate_annual", "term_max_months", "amount_min_vnd", "amount_max_vnd", "fee_pct"}


class CreditMemoValidationError(ValueError):
    """Safe validation error suitable for the model-facing four-field envelope."""


def is_credit_memo(args: dict[str, Any]) -> bool:
    return args.get("type") == "document" and args.get("title") == CREDIT_MEMO_TITLE


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def _validate_counter_offer(raw: Any) -> None:
    if not isinstance(raw, dict) or set(raw) != _COUNTER_KEYS:
        raise CreditMemoValidationError("The alternative offer must follow counter-offer v1.")
    if any(not _nonempty_string(raw.get(key)) for key in ("product_id", "product_name", "loan_type", "rationale")):
        raise CreditMemoValidationError("The alternative offer is missing required content.")
    amount = raw.get("proposed_amount_vnd")
    if not _finite_number(amount) or amount <= 0:
        raise CreditMemoValidationError("The alternative offer amount is invalid.")
    terms = raw.get("terms")
    if not isinstance(terms, list) or not terms:
        raise CreditMemoValidationError("The alternative offer must include terms from product_suggest.")
    seen_fields: set[str] = set()
    for term in terms:
        if not isinstance(term, dict) or set(term) != {"field", "value", "source"}:
            raise CreditMemoValidationError("An alternative offer term has an invalid shape.")
        field, value = term.get("field"), term.get("value")
        if (
            not isinstance(field, str)
            or field not in _TERM_FIELDS
            or field in seen_fields
            or term.get("source") != "product_suggest"
        ):
            raise CreditMemoValidationError("The source or name of an alternative offer term is invalid.")
        if not _finite_number(value):
            raise CreditMemoValidationError("An alternative offer term value is invalid.")
        seen_fields.add(field)
    proof = raw.get("proof")
    if not isinstance(proof, dict) or set(proof) != {"product_tool", "reassessment_tool", "wiki_citations"}:
        raise CreditMemoValidationError("The alternative offer is missing structured proof.")
    citations = proof.get("wiki_citations")
    if (
        proof.get("product_tool") != "product_suggest"
        or proof.get("reassessment_tool") != "credit_assess"
        or not isinstance(citations, list)
        or len(citations) < 2
        or any(not _nonempty_string(item) for item in citations)
        or len(citations) != len(set(citations))
    ):
        raise CreditMemoValidationError("The alternative offer structured proof is invalid.")


def validate_credit_memo(args: dict[str, Any], taxonomy: ReasonTaxonomy | None = None) -> dict[str, Any]:
    """Return a defensive copy with server-owned taxonomy proof injected.

    Callers must invoke this before any card persistence or SSE emission. Generic documents are
    returned unchanged by the present handler and do not enter this function.
    """
    active = taxonomy or get_reason_taxonomy()
    items = args.get("items")
    if not isinstance(items, list) or len(items) != len(CREDIT_MEMO_SECTIONS):
        raise CreditMemoValidationError("The credit memo must contain exactly six required sections.")
    normalized = copy.deepcopy(args)
    for index, (item, expected_section) in enumerate(zip(normalized["items"], CREDIT_MEMO_SECTIONS, strict=True)):
        if not isinstance(item, dict):
            raise CreditMemoValidationError("Each credit memo section must be an object.")
        if item.get("section") != expected_section:
            raise CreditMemoValidationError("The credit memo section name or order violates the contract.")
        if not _nonempty_string(item.get("content")) or not _nonempty_string(item.get("source")):
            raise CreditMemoValidationError("Every credit memo section requires non-empty content and source fields.")
        if index != 4:
            continue
        reason_codes = item.get("reason_codes")
        if (
            not isinstance(reason_codes, list)
            or not reason_codes
            or any(not isinstance(code, str) or code not in active.allowed_ids for code in reason_codes)
            or len(reason_codes) != len(set(reason_codes))
        ):
            raise CreditMemoValidationError(
                "The recommendation section requires unique reason_codes from the taxonomy."
            )
        if "counter_offers" in item:
            raise CreditMemoValidationError("The credit memo may contain only one counter_offer object.")
        if "counter_offer" in item and item["counter_offer"] is not None:
            _validate_counter_offer(item["counter_offer"])
        item["reason_taxonomy"] = active.proof()
    return normalized
