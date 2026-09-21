"""T23-4 counter-offer checker uses fresh card/tool outputs, with negative proof fixtures."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import pytest
from bench.check_counter_offer import CounterOfferCheckError, verify_counter_offer

from app.orch.main_skill import CREDIT_MEMO_SECTIONS, CREDIT_MEMO_TITLE
from app.reason_taxonomy import get_reason_taxonomy

EXPECTED = {
    "owner_id": "C009",
    "requested_amount_vnd": 600_000_000,
    "proposed_amount_vnd": 500_000_000,
    "loan_type": "consumer",
    "product_id": "P001",
    "requested_dscr": 1.179,
    "proposed_dscr": 1.371,
    "required_wiki_citations": ["goi-tieu-dung-chuan", "qd-2026-laisuat"],
}


def _card() -> dict[str, Any]:
    items = [
        {"section": section, "content": f"Sourced content {index}", "source": "credit_assess"}
        for index, section in enumerate(CREDIT_MEMO_SECTIONS, 1)
    ]
    items[4].update(
        {
            "reason_codes": ["THU_NHAP_KHONG_DU_KHA_NANG_TRA_NO"],
            "reason_taxonomy": get_reason_taxonomy().proof(),
            "counter_offer": {
                "product_id": "P001",
                "product_name": "Standard consumer loan",
                "proposed_amount_vnd": 500_000_000,
                "loan_type": "consumer",
                "rationale": "The smaller alternative was matched to a product and reassessed.",
                "terms": [
                    {"field": "rate_annual", "value": 0.15, "source": "product_suggest"},
                    {"field": "term_max_months", "value": 60, "source": "product_suggest"},
                    {"field": "amount_min_vnd", "value": 20_000_000, "source": "product_suggest"},
                    {"field": "amount_max_vnd", "value": 500_000_000, "source": "product_suggest"},
                    {"field": "fee_pct", "value": 0.01, "source": "product_suggest"},
                ],
                "proof": {
                    "product_tool": "product_suggest",
                    "reassessment_tool": "credit_assess",
                    "wiki_citations": ["goi-tieu-dung-chuan", "qd-2026-laisuat"],
                },
            },
        }
    )
    return {
        "type": "document",
        "title": CREDIT_MEMO_TITLE,
        "items": items,
        "sources": ["credit_assess", "product_suggest", "wiki_lookup"],
    }


def _wrapped(payload: dict[str, Any]) -> list[dict[str, str]]:
    return [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]


def _credit(amount: int, verdict: str, dscr: float) -> dict[str, Any]:
    return {
        "tool": "credit_assess",
        "input": {"owner_id": "C009", "loan_amount_vnd": amount, "loan_type": "consumer"},
        "output": _wrapped(
            {
                "found": True,
                "item": {
                    "ownerId": "C009",
                    "verdict": verdict,
                    "metrics": {"dscr": dscr},
                    "inputs": {"loanAmountVnd": amount, "loanType": "consumer"},
                },
            }
        ),
    }


def _product(amount: int, eligible: bool) -> dict[str, Any]:
    option = {
        "id": "P001",
        "name": "Standard consumer loan",
        "loanType": "consumer",
        "rateAnnual": 0.15,
        "termMaxMonths": 60,
        "amountRangeVnd": [20_000_000, 500_000_000],
        "feePct": 0.01,
        "status": "active",
    }
    return {
        "tool": "product_suggest",
        "input": {"owner_id": "C009", "loan_amount_vnd": amount, "loan_type": "consumer"},
        "output": _wrapped(
            {
                "found": True,
                "item": {
                    "ownerId": "C009",
                    "eligibleOptions": [option] if eligible else [],
                    "inputsUsed": {"loanAmountVnd": amount, "loanTypesConsidered": ["consumer"]},
                },
            }
        ),
    }


def _wiki(page: str) -> dict[str, Any]:
    return {
        "tool": "wiki_lookup",
        "input": {"page": page},
        "output": _wrapped({"found": True, "citation": {"page": page, "status": "active"}}),
    }


def _calls() -> list[dict[str, Any]]:
    return [
        _credit(600_000_000, "ineligible", 1.179),
        _product(600_000_000, False),
        _product(500_000_000, True),
        _credit(500_000_000, "eligible", 1.371),
        _wiki("goi-tieu-dung-chuan"),
        _wiki("qd-2026-laisuat"),
    ]


def test_co01_structured_card_maps_every_claim_to_tool_and_active_wiki_proof():
    proof = verify_counter_offer(_card(), _calls(), EXPECTED)

    assert proof["ok"] is True
    assert proof["product_id"] == "P001"
    assert proof["proposed_amount_vnd"] == 500_000_000
    assert proof["wiki_citations"] == EXPECTED["required_wiki_citations"]


@pytest.mark.parametrize(
    "broken",
    ["candidate", "reassessment", "same_amount", "eligible", "citation"],
)
def test_missing_or_inconsistent_proof_makes_checker_fail(broken: str):
    calls = deepcopy(_calls())
    if broken == "candidate":
        calls[2] = _product(500_000_000, False)
    elif broken == "reassessment":
        calls.pop(3)
    elif broken == "same_amount":
        calls[3] = _credit(499_000_000, "eligible", 1.371)
    elif broken == "eligible":
        calls[3] = _credit(500_000_000, "ineligible", 1.371)
    else:
        calls.pop()

    with pytest.raises(CounterOfferCheckError):
        verify_counter_offer(_card(), calls, EXPECTED)


def test_tool_owned_numeric_term_tamper_fails_checker():
    card = _card()
    card["items"][4]["counter_offer"]["terms"][0]["value"] = 0.12

    with pytest.raises(CounterOfferCheckError, match="rate_annual"):
        verify_counter_offer(card, _calls(), EXPECTED)


def test_claimed_offer_without_structured_offer_is_a_hard_failure():
    card = _card()
    card["items"][4].pop("counter_offer")

    with pytest.raises(CounterOfferCheckError, match="exactly one"):
        verify_counter_offer(card, _calls(), EXPECTED)
