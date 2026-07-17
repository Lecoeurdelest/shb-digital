"""[BACKEND] Test present-tool THẬT (T2-1): shape-reject bad_card, persist+id-inject, enum, list_cards.

present_tool là SdkMcpTool → gọi qua .handler. id VỎ-inject (§15); approval NGOÀI enum (N2).
"""

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


# ── enum: approval NGOÀI 6 loại hiển thị (N2 rào cứng ở SDK schema) ──────────


def test_approval_not_in_present_enum():
    sch = present_tool.input_schema
    assert "approval" not in sch["properties"]["type"]["enum"]
    assert set(sch["properties"]["type"]["enum"]) == set(PRESENT_TYPES)
    assert sch["required"] == ["type", "title", "items"]


# ── bad_card: shape sai → 4-field, KHÔNG persist ────────────────────────────


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


# ── persist + id-inject + SSE (cần DB) ──────────────────────────────────────


@requires_db
@pytest.mark.asyncio
async def test_present_persist_id_inject_sse():
    registry.CTX_CONV.set("c-present")
    registry.CTX_TASK.set("")  # main gọi → task_id null
    q = bus.subscribe("c-present")
    out = _payload(
        await _present(
            {
                "type": "metric",
                "title": "Thẩm định C001",
                "items": [{"name": "DSCR", "value": 3.709, "source": "credit_assess"}],
            }
        )
    )
    assert out["rendered"] is True
    ev = q.get_nowait()
    assert ev["type"] == "card"
    card = ev["data"]["card"]
    assert card["id"]  # id VỎ sinh (model không bơm)
    assert card["task_id"] is None  # main gọi ngoài sub
    assert card["type"] == "metric"
    assert card["title"] == "Thẩm định C001"
    assert card["items"][0]["source"] == "credit_assess"


@requires_db
@pytest.mark.asyncio
async def test_present_model_injected_id_ignored():
    """N5/§15 (bug tester T2-1): model bơm 'id'/'conv_id'/'task_id' vào args → VỎ BỎ, tự sinh.
    2 lớp phòng thủ: (1) handler lọc VỎ-owned khỏi data; (2) _card_to_dict id thật thắng spread."""
    conv = f"c-idinject-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    q = bus.subscribe(conv)
    await _present(
        {
            "type": "metric",
            "title": "x",
            "items": [{"name": "y", "value": 1}],
            "id": "FAKE-ID-MODEL-BOM",  # model bơm id giả
            "conv_id": "FAKE-CONV",  # + conv_id giả
            "task_id": "FAKE-TASK",  # + task_id giả
        }
    )
    card = q.get_nowait()["data"]["card"]
    assert card["id"] != "FAKE-ID-MODEL-BOM"  # id vỏ sinh, KHÔNG model bơm
    assert len(card["id"]) == 36 and card["id"].count("-") == 4  # uuid thật
    assert card["conv_id"] == conv  # VỎ set, không FAKE-CONV
    assert card["task_id"] is None  # VỎ set, không FAKE-TASK
    # reload từ DB cũng đúng (2 lớp)
    cards = await store.list_cards(conv)
    assert cards[-1]["id"] != "FAKE-ID-MODEL-BOM"


@requires_db
@pytest.mark.asyncio
async def test_present_task_id_inject_from_ctx():
    """CTX_TASK = task.id uuid thật → card.task_id = task.id (sub gọi present)."""
    task = await store.create_task("c-present-task", "credit", "Thẩm định", "brief")
    registry.CTX_CONV.set("c-present-task")
    registry.CTX_TASK.set(task.id)
    q = bus.subscribe("c-present-task")
    await _present(
        {
            "type": "document",
            "title": "Tờ trình",
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
    conv = f"c-list-{uuid4()}"  # unique per-run — cards persist DB, tránh test pollution
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    await _present({"type": "checklist", "title": "Pháp lý", "items": [{"item": "GCN", "status": "ok"}]})
    await _present({"type": "metric", "title": "Chỉ số", "items": [{"name": "LTV", "value": 0.5}]})
    cards = await store.list_cards(conv)
    assert len(cards) == 2
    assert {c["type"] for c in cards} == {"checklist", "metric"}
    # id + ts có mặt (canvas reload)
    assert all(c["id"] and c["ts"] for c in cards)


@requires_db
@pytest.mark.asyncio
async def test_present_all_six_types_persist():
    conv = f"c-6types-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    for t in PRESENT_TYPES:
        out = _payload(await _present({"type": t, "title": f"card {t}", "items": []}))
        assert out["rendered"] is True, f"type {t} phải render"
    cards = await store.list_cards(conv)
    assert {c["type"] for c in cards} == set(PRESENT_TYPES)
