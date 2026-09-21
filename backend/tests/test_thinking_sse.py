from __future__ import annotations

from uuid import uuid4

from app.orch.audit_emit import _emit_thinking
from app.sse import bus


def test_emit_thinking_sub_shape():
    """sub think → SSE thinking {task_id (str), text} §9."""
    conv = f"think-sub-{uuid4()}"
    q = bus.subscribe(conv)
    try:
        _emit_thinking(conv, "task-abc", "Considering the customer's DSCR...")
        assert not q.empty(), "Expected invariant was not satisfied at source line 15."
        ev = q.get_nowait()
        assert ev["type"] == "thinking"
        d = ev["data"]
        assert set(d.keys()) == {"task_id", "text"}
        assert d["task_id"] == "task-abc"
        assert "DSCR" in d["text"]
    finally:
        bus.unsubscribe(conv, q)


def test_emit_thinking_main_task_id_null():

    conv = f"think-main-{uuid4()}"
    q = bus.subscribe(conv)
    try:
        _emit_thinking(conv, None, "Orchestration: dispatch credit and legal")
        ev = q.get_nowait()
        assert ev["data"]["task_id"] is None
        assert "orchestration" in ev["data"]["text"].lower()
    finally:
        bus.unsubscribe(conv, q)


def test_emit_thinking_empty_text_no_emit():

    conv = f"think-empty-{uuid4()}"
    q = bus.subscribe(conv)
    try:
        _emit_thinking(conv, "t1", "")
        assert q.empty(), "Expected invariant was not satisfied at source line 45."
        _emit_thinking(conv, "t1", None)
        assert q.empty()
    finally:
        bus.unsubscribe(conv, q)


def test_emit_thinking_no_subscriber_no_raise():

    _emit_thinking(f"think-nosub-{uuid4()}", "t1", "discarded thought")


def test_emit_thinking_uuid_task_id_serialized():

    conv = f"think-uuid-{uuid4()}"
    tid = uuid4()
    q = bus.subscribe(conv)
    try:
        _emit_thinking(conv, tid, "think")
        ev = q.get_nowait()
        assert ev["data"]["task_id"] == str(tid)
        assert isinstance(ev["data"]["task_id"], str)
    finally:
        bus.unsubscribe(conv, q)
