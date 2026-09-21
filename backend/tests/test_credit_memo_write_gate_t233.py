"""T23-3 write-time memo validator runs before card persistence/SSE."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from app.orch import registry, store
from app.orch.common_tools import present_tool
from app.orch.main_skill import CREDIT_MEMO_SECTIONS, CREDIT_MEMO_TITLE
from app.reason_taxonomy import get_reason_taxonomy


def _memo() -> dict:
    items = [
        {"section": section, "content": f"Content {index}", "source": "credit_assess"}
        for index, section in enumerate(CREDIT_MEMO_SECTIONS, 1)
    ]
    items[4]["reason_codes"] = ["THU_NHAP_KHONG_DU_KHA_NANG_TRA_NO"]
    return {"type": "document", "title": CREDIT_MEMO_TITLE, "items": items, "sources": ["credit_assess"]}


def _payload(envelope: dict) -> dict:
    return json.loads(envelope["content"][0]["text"])


@pytest.mark.asyncio
async def test_valid_memo_injects_server_taxonomy_before_insert(monkeypatch: pytest.MonkeyPatch):
    original = _memo()
    captured: dict = {}

    async def insert(conv_id, task_id, card_type, data):
        captured.update({"conv_id": conv_id, "task_id": task_id, "type": card_type, "data": data})
        return {"id": "server-id", "conv_id": conv_id, "task_id": task_id, "type": card_type, **data}

    monkeypatch.setattr(store, "insert_card", insert)
    monkeypatch.setattr("app.sse.emit.emit", lambda *_args, **_kwargs: None)
    registry.CTX_CONV.set("memo-conv")
    registry.CTX_TASK.set("")

    assert _payload(await present_tool.handler(original))["rendered"] is True
    assert captured["data"]["items"][4]["reason_taxonomy"] == get_reason_taxonomy().proof()
    assert "reason_taxonomy" not in original["items"][4]


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown", "section", "order", "count"])
async def test_invalid_memo_is_four_field_and_zero_db_sse(monkeypatch: pytest.MonkeyPatch, mutation: str):
    args = _memo()
    if mutation == "missing":
        args["items"][4].pop("reason_codes")
    elif mutation == "duplicate":
        args["items"][4]["reason_codes"] *= 2
    elif mutation == "unknown":
        args["items"][4]["reason_codes"] = ["MODEL_SANG_TAC"]
    elif mutation == "section":
        args["items"][2]["section"] = "Invented section"
    elif mutation == "order":
        args["items"][0], args["items"][1] = args["items"][1], args["items"][0]
    else:
        args["items"].pop()
    insert = monkeypatch.setattr(store, "insert_card", pytest.fail)
    emit_calls: list = []
    monkeypatch.setattr("app.sse.emit.emit", lambda *values: emit_calls.append(values))

    payload = _payload(await present_tool.handler(args))

    assert set(payload) == {"code", "message", "hint", "retryable"}
    assert payload["code"] == "invalid_credit_memo"
    assert payload["retryable"] is True
    assert insert is None
    assert emit_calls == []


@pytest.mark.asyncio
async def test_generic_document_bypasses_memo_gate(monkeypatch: pytest.MonkeyPatch):
    captured: list[dict] = []

    async def insert(conv_id, task_id, card_type, data):
        captured.append(deepcopy(data))
        return {"id": "id", "conv_id": conv_id, "task_id": task_id, "type": card_type, **data}

    monkeypatch.setattr(store, "insert_card", insert)
    monkeypatch.setattr("app.sse.emit.emit", lambda *_args, **_kwargs: None)
    args = {"type": "document", "title": "Regular document", "items": []}

    assert _payload(await present_tool.handler(args))["rendered"] is True
    assert captured == [args]


@pytest.mark.asyncio
async def test_counter_offer_array_or_incomplete_proof_fails_before_write(monkeypatch: pytest.MonkeyPatch):
    args = _memo()
    args["items"][4]["counter_offer"] = []
    monkeypatch.setattr(store, "insert_card", pytest.fail)
    monkeypatch.setattr("app.sse.emit.emit", pytest.fail)

    assert _payload(await present_tool.handler(args))["code"] == "invalid_credit_memo"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_value", [10**1000, {"not": "a field name"}])
async def test_malformed_counter_offer_never_escapes_four_field_gate(monkeypatch, bad_value):
    args = _memo()
    args["items"][4]["counter_offer"] = {
        "product_id": "P001",
        "product_name": "Standard consumer loan",
        "proposed_amount_vnd": 500_000_000,
        "loan_type": "consumer",
        "rationale": "Reduce the amount after reassessment.",
        "terms": [{"field": "rate_annual", "value": 0.15, "source": "product_suggest"}],
        "proof": {
            "product_tool": "product_suggest",
            "reassessment_tool": "credit_assess",
            "wiki_citations": ["goi-tieu-dung-chuan", "qd-2026-laisuat"],
        },
    }
    if isinstance(bad_value, dict):
        args["items"][4]["counter_offer"]["terms"][0]["field"] = bad_value
    else:
        args["items"][4]["counter_offer"]["proposed_amount_vnd"] = bad_value
    monkeypatch.setattr(store, "insert_card", pytest.fail)
    monkeypatch.setattr("app.sse.emit.emit", pytest.fail)

    payload = _payload(await present_tool.handler(args))

    assert payload["code"] == "invalid_credit_memo"
    assert set(payload) == {"code", "message", "hint", "retryable"}
