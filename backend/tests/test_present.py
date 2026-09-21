from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.orch import registry, store
from app.orch.common_tools import PRESENT_TYPES, present_tool
from app.sse import bus, emit

from .conftest import requires_db

_present = present_tool.handler


@pytest.fixture(autouse=True)
def _reset():
    bus.reset()
    emit.reset()
    registry.CTX_CONV.set("")
    registry.CTX_TASK.set("")
    yield
    bus.reset()
    emit.reset()


def _payload(env: dict) -> dict:
    return json.loads(env["content"][0]["text"])


def test_approval_not_in_present_enum():
    sch = present_tool.input_schema
    assert "approval" not in sch["properties"]["type"]["enum"]
    assert set(sch["properties"]["type"]["enum"]) == set(PRESENT_TYPES)
    assert sch["properties"]["sources"]["items"] == {"type": "string"}
    assert sch["required"] == ["type", "title", "items"]


@pytest.mark.asyncio
async def test_bad_card_wrong_type():
    registry.CTX_CONV.set("c-bad")
    out = _payload(await _present({"type": "approval", "title": "x", "items": []}))
    assert out["code"] == "bad_card"
    assert out["retryable"] is False


@pytest.mark.asyncio
async def test_bad_card_items_not_list():
    registry.CTX_CONV.set("c-bad2")
    out = _payload(await _present({"type": "metric", "title": "x", "items": "not-list"}))
    assert out["code"] == "bad_card"


@pytest.mark.asyncio
async def test_bad_card_title_not_str():
    registry.CTX_CONV.set("c-bad3")
    out = _payload(await _present({"type": "metric", "title": 123, "items": []}))
    assert out["code"] == "bad_card"


@requires_db
@pytest.mark.asyncio
async def test_present_persist_id_inject_sse():
    registry.CTX_CONV.set("c-present")
    registry.CTX_TASK.set("")
    q = bus.subscribe("c-present")
    out = _payload(
        await _present(
            {
                "type": "metric",
                "title": "Assessment C001",
                "items": [{"name": "DSCR", "value": 3.709, "source": "credit_assess"}],
            }
        )
    )
    assert out["rendered"] is True
    ev = q.get_nowait()
    assert ev["type"] == "card"
    card = ev["data"]["card"]
    assert card["id"]
    assert card["task_id"] is None
    assert card["type"] == "metric"
    assert card["title"] == "Assessment C001"
    assert card["items"][0]["source"] == "credit_assess"


@requires_db
@pytest.mark.asyncio
async def test_present_model_injected_id_ignored():

    conv = f"c-idinject-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    q = bus.subscribe(conv)
    await _present(
        {
            "type": "metric",
            "title": "x",
            "items": [{"name": "y", "value": 1}],
            "id": "FAKE-ID-MODEL-BOM",
            "conv_id": "FAKE-CONV",
            "task_id": "FAKE-TASK",
        }
    )
    card = q.get_nowait()["data"]["card"]
    assert card["id"] != "FAKE-ID-MODEL-BOM"
    assert len(card["id"]) == 36 and card["id"].count("-") == 4
    assert card["conv_id"] == conv
    assert card["task_id"] is None

    cards = await store.list_cards(conv)
    assert cards[-1]["id"] != "FAKE-ID-MODEL-BOM"


@requires_db
@pytest.mark.asyncio
async def test_present_task_id_inject_from_ctx():

    task = await store.create_task("c-present-task", "credit", "Assessment", "brief")
    registry.CTX_CONV.set("c-present-task")
    registry.CTX_TASK.set(task.id)
    q = bus.subscribe("c-present-task")
    await _present(
        {
            "type": "document",
            "title": "Credit memo",
            "items": [{"section": "A", "content": "x"}],
            "sources": ["credit_assess"],
        }
    )
    card = q.get_nowait()["data"]["card"]
    assert card["task_id"] == task.id
    assert card["sources"] == ["credit_assess"]


@requires_db
@pytest.mark.asyncio
async def test_list_cards_reload():
    conv = f"c-list-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    await _present({"type": "checklist", "title": "Legal", "items": [{"item": "Certificate", "status": "ok"}]})
    await _present({"type": "metric", "title": "Metrics", "items": [{"name": "LTV", "value": 0.5}]})
    cards = await store.list_cards(conv)
    assert len(cards) == 2
    assert {c["type"] for c in cards} == {"checklist", "metric"}

    assert all(c["id"] and c["ts"] for c in cards)


@requires_db
@pytest.mark.asyncio
async def test_present_all_six_types_persist():
    conv = f"c-6types-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    for t in PRESENT_TYPES:
        out = _payload(await _present({"type": t, "title": f"card {t}", "items": []}))
        assert out["rendered"] is True, "Expected invariant was not satisfied at source line 160."
    cards = await store.list_cards(conv)
    assert {c["type"] for c in cards} == set(PRESENT_TYPES)
