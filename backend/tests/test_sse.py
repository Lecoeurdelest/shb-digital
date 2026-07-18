"""[BACKEND] Test SSE bus fanout + emit envelope + redact + endpoints shape. Mechanics (no SDK)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.sse import bus, emit
from app.sse.redact import redact_deep


@pytest.fixture(autouse=True)
def _reset_sse():
    bus.reset()
    emit.reset()
    yield
    bus.reset()
    emit.reset()


# ── bus fanout ──────────────────────────────────────────────────────────────


def test_subscribe_publish_fanout():
    q1 = bus.subscribe("c1")
    q2 = bus.subscribe("c1")
    bus.publish("c1", {"type": "x"})
    assert q1.get_nowait() == {"type": "x"}
    assert q2.get_nowait() == {"type": "x"}


def test_publish_other_conv_isolated():
    q1 = bus.subscribe("c1")
    bus.subscribe("c2")
    bus.publish("c2", {"type": "y"})
    assert q1.empty()  # c1 không nhận event của c2


def test_unsubscribe_removes():
    q = bus.subscribe("c3")
    assert bus.conn_count("c3") == 1
    bus.unsubscribe("c3", q)
    assert bus.conn_count("c3") == 0


def test_publish_full_queue_drops_not_raises():
    q = bus.subscribe("c4")
    # nhồi đầy queue (maxsize 500) — publish không raise, chỉ drop
    for i in range(600):
        bus.publish("c4", {"n": i})
    assert q.qsize() <= 500  # đầy thì drop, không nổ


# ── emit envelope shape ─────────────────────────────────────────────────────


def test_emit_envelope_shape():
    q = bus.subscribe("c5")
    emit.emit("c5", "conversation.status", {"status": "running"})
    ev = q.get_nowait()
    assert set(ev) == {"type", "conversation_id", "seq", "ts", "data"}
    assert ev["type"] == "conversation.status"
    assert ev["conversation_id"] == "c5"
    assert ev["data"] == {"status": "running"}


def test_chat_delta_seq_increments_then_done_highest():
    q = bus.subscribe("c6")
    emit.emit_chat_delta("c6", "turn-1", "Xin")
    emit.emit_chat_delta("c6", "turn-1", " chào")
    emit.emit_chat_done("c6", "turn-1", "Xin chào")
    e1 = q.get_nowait()
    e2 = q.get_nowait()
    e3 = q.get_nowait()
    assert e1["seq"] == 1 and e1["data"]["chunk"] == "Xin" and e1["data"]["done"] is False
    assert e2["seq"] == 2
    assert e3["seq"] == 3 and e3["data"]["done"] is True and e3["data"]["full_text"] == "Xin chào"


def test_emit_task_full_row():
    q = bus.subscribe("c7")
    emit.emit_task("c7", "task.created", {"id": "t1", "role": "credit", "status": "queued"})
    ev = q.get_nowait()
    assert ev["type"] == "task.created"
    assert ev["data"]["task"]["role"] == "credit"


# ── redact ──────────────────────────────────────────────────────────────────


def test_redact_api_key_in_emit():
    q = bus.subscribe("c8")
    emit.emit("c8", "chat.delta", {"chunk": "key sk-abcdefghijklmnopqrstuvwxyz123 leaked"})
    ev = q.get_nowait()
    assert "sk-abcdefghij" not in ev["data"]["chunk"]
    assert "[REDACTED:api-key]" in ev["data"]["chunk"]


def test_redact_deep_nested():
    out = redact_deep({"a": {"b": ["sk-abcdefghijklmnopqrstuvwxyz123"]}})
    assert "[REDACTED:api-key]" in out["a"]["b"][0]


# ── endpoint 404 (mechanics, không cần SDK) ─────────────────────────────────


@pytest.mark.asyncio
async def test_sse_endpoint_headers_present():
    """4 header sống-còn phải có trong response."""
    from app.api.sse import _SSE_HEADERS

    assert _SSE_HEADERS["X-Accel-Buffering"] == "no"
    assert _SSE_HEADERS["Cache-Control"] == "no-cache"


def test_sse_heartbeat_interval_15s():
    """S6: heartbeat 15s (SPEC §9) — client có traffic phát hiện đứt (SIGKILL onerror không fire)."""
    from app.api.sse import _HEARTBEAT

    assert _HEARTBEAT == 15.0


@pytest.mark.asyncio
async def test_sse_stream_emits_ping_event_when_idle(monkeypatch):
    """S6: queue RỖNG > _HEARTBEAT → stream yield EVENT ping (data:) KHÔNG comment (: ...) — native
    EventSource nuốt comment → FE onmessage không thấy. type='ping' cùng shape envelope → FE reset
    watchdog. Hạ _HEARTBEAT nhỏ để test nhanh."""
    import json as _json

    import app.api.sse as sse_mod

    monkeypatch.setattr(sse_mod, "_HEARTBEAT", 0.05)  # nhanh
    conv = f"hb-{uuid4()}"

    class _FakeReq:
        async def is_disconnected(self):
            return False

    resp = await sse_mod.sse(conv, _FakeReq(), _claims={"username": "u"})
    frames = []
    it = resp.body_iterator
    for _ in range(3):  # connected + ≥1 ping (queue rỗng → timeout → ping event)
        frames.append(await it.__anext__())
    joined = "".join(frames)
    assert ": connected" in joined  # frame đầu (comment — onopen fire, không cần onmessage)
    # heartbeat = EVENT THẬT data: (KHÔNG comment ': heartbeat') → FE onmessage bắt được
    ping_frames = [f for f in frames if f.startswith("data:")]
    assert ping_frames, "phải có ít nhất 1 ping EVENT (data:) khi idle"
    payload = _json.loads(ping_frames[0][len("data: ") :].strip())
    assert payload["type"] == "ping"  # FE parse type='ping' → bỏ qua render + reset watchdog
    assert payload["conversation_id"] == conv
    assert payload["data"] == {}
    assert set(payload) == {"type", "conversation_id", "seq", "ts", "data"}  # cùng shape SSEEnvelope


def test_bus_publish_no_subscriber_noop():
    # emit khi không ai nghe → không nổ (orch _report/dispatch emit an toàn khi chưa có SSE client)
    emit.emit("nobody", "task.status", {"task": {"id": "t"}})
    assert bus.conn_count("nobody") == 0
