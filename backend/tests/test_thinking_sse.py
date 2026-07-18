"""[BACKEND] Test T4-2: SSE thinking emit — {task_id, text} shape §9, LIVE-only.

_emit_thinking: sub (task_id) | main (None) → SSE thinking. text rỗng → không emit (không khối rỗng).
Fire-and-forget (lỗi SSE không raise). KHÔNG persist DB (trace tạm).
"""

from __future__ import annotations

from uuid import uuid4

from app.orch.main_session import _emit_thinking
from app.sse import bus


def test_emit_thinking_sub_shape():
    """sub think → SSE thinking {task_id (str), text} §9."""
    conv = f"think-sub-{uuid4()}"
    q = bus.subscribe(conv)
    try:
        _emit_thinking(conv, "task-abc", "Đang cân nhắc DSCR của khách...")
        assert not q.empty(), "SSE thinking KHÔNG phát"
        ev = q.get_nowait()
        assert ev["type"] == "thinking"
        d = ev["data"]
        assert set(d.keys()) == {"task_id", "text"}  # §9 shape đúng
        assert d["task_id"] == "task-abc"
        assert "DSCR" in d["text"]
    finally:
        bus.unsubscribe(conv, q)


def test_emit_thinking_main_task_id_null():
    """MAIN think → task_id=None (main gọi ngoài sub)."""
    conv = f"think-main-{uuid4()}"
    q = bus.subscribe(conv)
    try:
        _emit_thinking(conv, None, "Điều phối: cần giao credit + legal")
        ev = q.get_nowait()
        assert ev["data"]["task_id"] is None
        assert "điều phối" in ev["data"]["text"].lower()
    finally:
        bus.unsubscribe(conv, q)


def test_emit_thinking_empty_text_no_emit():
    """text rỗng → KHÔNG emit (không hiện khối trace rỗng — defensive task #19)."""
    conv = f"think-empty-{uuid4()}"
    q = bus.subscribe(conv)
    try:
        _emit_thinking(conv, "t1", "")
        assert q.empty(), "text rỗng KHÔNG được emit"
        _emit_thinking(conv, "t1", None)  # None cũng bỏ qua
        assert q.empty()
    finally:
        bus.unsubscribe(conv, q)


def test_emit_thinking_no_subscriber_no_raise():
    """không ai subscribe → fire-and-forget, KHÔNG raise (best-effort)."""
    # không subscribe conv này → publish vào rỗng, không nổ
    _emit_thinking(f"think-nosub-{uuid4()}", "t1", "suy nghĩ vào hư không")
    # không assert gì — chỉ cần KHÔNG raise


def test_emit_thinking_uuid_task_id_serialized():
    """task_id uuid object → str hoá (JSON-safe)."""
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
