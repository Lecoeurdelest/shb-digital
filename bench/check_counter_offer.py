#!/usr/bin/env python3
"""Machine-check one fresh counter-offer card against structured tool-call evidence (T23-4)."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psycopg2.extras
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.orch.credit_memo import CreditMemoValidationError, validate_credit_memo  # noqa: E402
from app.orch.main_skill import CREDIT_MEMO_TITLE  # noqa: E402
from app.reason_taxonomy import get_reason_taxonomy  # noqa: E402
from app.storage import connect_core  # noqa: E402

_TERM_OUTPUT_FIELDS: dict[str, tuple[str, int | None]] = {
    "rate_annual": ("rateAnnual", None),
    "term_max_months": ("termMaxMonths", None),
    "amount_min_vnd": ("amountRangeVnd", 0),
    "amount_max_vnd": ("amountRangeVnd", 1),
    "fee_pct": ("feePct", None),
}


class CounterOfferCheckError(ValueError):
    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__("; ".join(issues))


def _decode_output(value: Any, depth: int = 0) -> dict[str, Any] | None:
    """Normalize DB JSONB from ToolResultBlock.content (usually [{type,text:JSON}])."""
    if depth > 4 or value is None:
        return None
    if isinstance(value, dict):
        if "content" in value and len(value) == 1:
            return _decode_output(value["content"], depth + 1)
        if value.get("type") == "text" and isinstance(value.get("text"), str):
            return _decode_output(value["text"], depth + 1)
        return value
    if isinstance(value, list):
        for item in value:
            decoded = _decode_output(item, depth + 1)
            if decoded is not None:
                return decoded
        return None
    if isinstance(value, str):
        try:
            return _decode_output(json.loads(value), depth + 1)
        except json.JSONDecodeError:
            return None
    return None


def _number_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    try:
        return math.isclose(float(left), float(right), rel_tol=0, abs_tol=1e-9)
    except (TypeError, ValueError, OverflowError):
        return False


def _matching_call(
    calls: list[dict[str, Any]], tool: str, predicate: Callable[[dict[str, Any]], bool]
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    for row in calls:
        tool_input = row.get("input")
        if (
            row.get("tool") != tool
            or not isinstance(tool_input, dict)
            or not predicate(tool_input)
        ):
            continue
        output = _decode_output(row.get("output"))
        if output is not None:
            return tool_input, output
    return None


def _tool_input_matches(
    raw: dict[str, Any], owner: str, amount: Any, loan_type: str
) -> bool:
    return (
        raw.get("owner_id") == owner
        and _number_equal(raw.get("loan_amount_vnd"), amount)
        and raw.get("loan_type") == loan_type
    )


def _item(output: dict[str, Any]) -> dict[str, Any]:
    value = output.get("item")
    return value if isinstance(value, dict) else {}


def verify_counter_offer(
    card: dict[str, Any], tool_calls: list[dict[str, Any]], expected: dict[str, Any]
) -> dict[str, Any]:
    """Raise on any unsupported claim; return compact proof summary when all evidence agrees."""
    issues: list[str] = []
    if card.get("title") != CREDIT_MEMO_TITLE:
        issues.append("fresh card is not the canonical credit memo")
    try:
        validate_credit_memo(card)
    except CreditMemoValidationError as exc:
        issues.append(f"credit memo write contract invalid: {exc}")
    items = card.get("items") if isinstance(card.get("items"), list) else []
    recommendation = items[4] if len(items) > 4 and isinstance(items[4], dict) else {}
    taxonomy = get_reason_taxonomy()
    if recommendation.get("reason_taxonomy") != taxonomy.proof():
        issues.append("stored reason_taxonomy proof is not server canonical")
    if "counter_offers" in recommendation:
        issues.append(
            "counter_offers array is forbidden; only one counter_offer object is allowed"
        )
    offer = recommendation.get("counter_offer")
    if not isinstance(offer, dict):
        issues.append("exactly one structured counter_offer is required")
        raise CounterOfferCheckError(issues)

    owner = expected["owner_id"]
    requested_amount = expected["requested_amount_vnd"]
    proposed_amount = expected["proposed_amount_vnd"]
    loan_type = expected["loan_type"]
    product_id = expected["product_id"]
    if not _number_equal(offer.get("proposed_amount_vnd"), proposed_amount):
        issues.append("offer amount differs from expected proposed amount")
    if offer.get("loan_type") != loan_type or offer.get("product_id") != product_id:
        issues.append("offer product/type differs from expected candidate")

    original_credit = _matching_call(
        tool_calls,
        "credit_assess",
        lambda raw: _tool_input_matches(raw, owner, requested_amount, loan_type),
    )
    if original_credit is None:
        issues.append("missing original credit_assess at requested amount/type")
    else:
        original_item = _item(original_credit[1])
        original_inputs = (
            original_item.get("inputs")
            if isinstance(original_item.get("inputs"), dict)
            else {}
        )
        if (
            original_item.get("ownerId") != owner
            or original_item.get("verdict") == "eligible"
        ):
            issues.append("original credit assessment must fail before a counter-offer")
        if (
            not _number_equal(original_inputs.get("loanAmountVnd"), requested_amount)
            or original_inputs.get("loanType") != loan_type
        ):
            issues.append(
                "original credit output does not confirm requested amount/type"
            )
        expected_dscr = expected.get("requested_dscr")
        if expected_dscr is not None and not _number_equal(
            original_item.get("metrics", {}).get("dscr"), expected_dscr
        ):
            issues.append("original DSCR differs from fixture proof")

    original_product = _matching_call(
        tool_calls,
        "product_suggest",
        lambda raw: _tool_input_matches(raw, owner, requested_amount, loan_type),
    )
    original_product_item = (
        _item(original_product[1]) if original_product is not None else {}
    )
    original_product_inputs = (
        original_product_item.get("inputsUsed")
        if isinstance(original_product_item.get("inputsUsed"), dict)
        else {}
    )
    if (
        original_product is None
        or original_product_item.get("ownerId") != owner
        or original_product_item.get("eligibleOptions") != []
        or not _number_equal(
            original_product_inputs.get("loanAmountVnd"), requested_amount
        )
        or loan_type not in (original_product_inputs.get("loanTypesConsidered") or [])
    ):
        issues.append("requested amount must have product_suggest eligibleOptions=[]")

    candidate_product = _matching_call(
        tool_calls,
        "product_suggest",
        lambda raw: _tool_input_matches(raw, owner, proposed_amount, loan_type),
    )
    eligible_product: dict[str, Any] | None = None
    if candidate_product is None:
        issues.append("missing product_suggest at exact proposed amount/type")
    else:
        candidate_item = _item(candidate_product[1])
        options = candidate_item.get("eligibleOptions")
        product_inputs = (
            candidate_item.get("inputsUsed")
            if isinstance(candidate_item.get("inputsUsed"), dict)
            else {}
        )
        if (
            candidate_item.get("ownerId") != owner
            or not _number_equal(product_inputs.get("loanAmountVnd"), proposed_amount)
            or loan_type not in (product_inputs.get("loanTypesConsidered") or [])
        ):
            issues.append(
                "product_suggest output does not confirm proposed owner/amount/type"
            )
        if isinstance(options, list):
            eligible_product = next(
                (
                    item
                    for item in options
                    if isinstance(item, dict) and item.get("id") == product_id
                ),
                None,
            )
        if eligible_product is None:
            issues.append("candidate product is not in product_suggest eligibleOptions")

    reassessment = _matching_call(
        tool_calls,
        "credit_assess",
        lambda raw: _tool_input_matches(raw, owner, proposed_amount, loan_type),
    )
    if reassessment is None:
        issues.append("missing same-amount/type credit reassessment")
    else:
        reassessed_item = _item(reassessment[1])
        inputs = (
            reassessed_item.get("inputs")
            if isinstance(reassessed_item.get("inputs"), dict)
            else {}
        )
        if (
            reassessed_item.get("ownerId") != owner
            or reassessed_item.get("verdict") != "eligible"
            or not _number_equal(inputs.get("loanAmountVnd"), proposed_amount)
            or inputs.get("loanType") != loan_type
        ):
            issues.append(
                "credit reassessment is not eligible at the exact proposed amount/type"
            )
        expected_dscr = expected.get("proposed_dscr")
        if expected_dscr is not None and not _number_equal(
            reassessed_item.get("metrics", {}).get("dscr"), expected_dscr
        ):
            issues.append("reassessment DSCR differs from fixture proof")

    terms = offer.get("terms") if isinstance(offer.get("terms"), list) else []
    if eligible_product is not None:
        if offer.get("product_name") != eligible_product.get("name"):
            issues.append("offer product name is not tool-owned")
        for term in terms:
            if not isinstance(term, dict) or term.get("source") != "product_suggest":
                issues.append("every numeric term must cite product_suggest")
                continue
            mapping = _TERM_OUTPUT_FIELDS.get(str(term.get("field")))
            if mapping is None:
                issues.append("offer contains an unsupported numeric term")
                continue
            tool_value = eligible_product.get(mapping[0])
            if mapping[1] is not None:
                tool_value = (
                    tool_value[mapping[1]]
                    if isinstance(tool_value, list) and len(tool_value) > mapping[1]
                    else None
                )
            if not _number_equal(term.get("value"), tool_value):
                issues.append(
                    f"numeric term {term.get('field')} does not map to product_suggest"
                )

    proof = offer.get("proof") if isinstance(offer.get("proof"), dict) else {}
    citations = (
        proof.get("wiki_citations")
        if isinstance(proof.get("wiki_citations"), list)
        else []
    )
    required_citations = expected.get("required_wiki_citations", [])
    if not set(required_citations).issubset(citations):
        issues.append("counter-offer is missing a required wiki citation")
    for page in citations:
        citation_call = _matching_call(
            tool_calls, "wiki_lookup", lambda raw, page=page: raw.get("page") == page
        )
        citation = _item({})
        if citation_call is not None:
            value = citation_call[1].get("citation")
            citation = value if isinstance(value, dict) else {}
        if citation.get("page") != page or citation.get("status") != "active":
            issues.append(f"wiki citation {page!r} lacks active retrieval proof")

    if issues:
        raise CounterOfferCheckError(issues)
    return {
        "ok": True,
        "product_id": product_id,
        "proposed_amount_vnd": proposed_amount,
        "loan_type": loan_type,
        "wiki_citations": citations,
        "reason_taxonomy": taxonomy.proof(),
    }


def load_fresh_evidence(conv_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read latest canonical memo and only audit rows available before that card was persisted."""
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT data,ts FROM cards WHERE conv_id=%s AND type='document' "
                "AND data->>'title'=%s ORDER BY ts DESC LIMIT 1",
                (conv_id, CREDIT_MEMO_TITLE),
            )
            card_row = cur.fetchone()
            if card_row is None:
                raise CounterOfferCheckError(
                    ["fresh conversation has no canonical credit memo card"]
                )
            cur.execute(
                "SELECT tool,input,output,ts FROM tool_calls WHERE conv_id=%s AND ts<=%s ORDER BY ts,id",
                (conv_id, card_row["ts"]),
            )
            calls = [dict(row) for row in cur.fetchall()]
        conn.rollback()
        return dict(card_row["data"]), calls
    finally:
        conn.close()


def check_conversation(conv_id: str, expected: dict[str, Any]) -> dict[str, Any]:
    card, calls = load_fresh_evidence(conv_id)
    return verify_counter_offer(card, calls, expected)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check a fresh counter-offer card against DB tool_calls"
    )
    parser.add_argument("--conv-id", required=True)
    parser.add_argument("--case", default="CO-01-counter-offer")
    args = parser.parse_args()
    case_path = REPO_ROOT / "bench" / "cases" / f"{args.case}.yaml"
    case = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    try:
        result = check_conversation(args.conv_id, case["counter_offer_expected"])
    except CounterOfferCheckError as exc:
        print(
            json.dumps(
                {"ok": False, "issues": exc.issues}, ensure_ascii=False, indent=2
            )
        )
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
