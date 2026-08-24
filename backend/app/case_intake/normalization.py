"""Data-minimizing normalization shared by intake, RFI and linked MAIN context (D-81/D-83)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

SAFE_MISSING_FIELD_CODES = frozenset(
    {
        "collateral_document",
        "collateral_valuation",
        "employment_proof",
        "financial_statements",
        "financial_statements_2025",
        "identity_document",
        "income_proof",
        "internal_identity_mapping",
        "legal_document",
        "residence_proof",
        "tax_return",
    }
)
UNKNOWN_MISSING_FIELD_CODE = "additional_information"
_SAFE_EXTERNAL_CASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


def normalize_missing_fields(values: Iterable[Any] | None) -> list[str]:
    """Return a deterministic code set; all unknown values collapse to one non-reversible sentinel."""
    normalized: set[str] = set()
    for raw in values or ():
        code = raw.strip() if isinstance(raw, str) else ""
        if code in SAFE_MISSING_FIELD_CODES:
            normalized.add(code)
        else:
            normalized.add(UNKNOWN_MISSING_FIELD_CODE)
    return sorted(normalized)


def external_case_id_or_fallback(external_case_id: Any, link_id: Any) -> str:
    """Only expose identifier-shaped source ids; arbitrary source text is replaced by our UUID."""
    if isinstance(external_case_id, str) and _SAFE_EXTERNAL_CASE_ID.fullmatch(external_case_id):
        return external_case_id
    return str(link_id)
