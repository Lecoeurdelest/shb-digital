"""[BACKEND] Test SSE bus fanout + emit envelope + redact + endpoints shape. Mechanics (no SDK)."""

from __future__ import annotations

import pytest

from app.sse import bus, emit
from app.sse.redact import redact_deep

from .conftest import requires_db


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
    assert q1.empty()


def test_unsubscribe_removes():
    q = bus.subscribe("c3")
    assert bus.conn_count("c3") == 1
    bus.unsubscribe("c3", q)
    assert bus.conn_count("c3") == 0


def test_publish_full_queue_drops_not_raises():
    q = bus.subscribe("c4")

    for i in range(600):
        bus.publish("c4", {"n": i})
    assert q.qsize() <= 500


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
    emit.emit_chat_delta("c6", "turn-1", " hello")
    emit.emit_chat_done("c6", "turn-1", "Hello")
    e1 = q.get_nowait()
    e2 = q.get_nowait()
    e3 = q.get_nowait()
    assert e1["seq"] == 1 and e1["data"]["chunk"] == "Xin" and e1["data"]["done"] is False
    assert e2["seq"] == 2
    assert e3["seq"] == 3 and e3["data"]["done"] is True and e3["data"]["full_text"] == "Hello"


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


@pytest.mark.asyncio
async def test_sse_endpoint_headers_present():

    from app.api.sse import _SSE_HEADERS

    assert _SSE_HEADERS["X-Accel-Buffering"] == "no"
    assert _SSE_HEADERS["Cache-Control"] == "no-cache"


def test_sse_heartbeat_interval_15s():

    from app.api.sse import _HEARTBEAT

    assert _HEARTBEAT == 15.0


@requires_db
@pytest.mark.asyncio
async def test_sse_stream_emits_ping_event_when_idle(monkeypatch):

    import json as _json

    import psycopg2

    import app.api.sse as sse_mod
    from app.db.config import DATABASE_URL

    monkeypatch.setattr(sse_mod, "_HEARTBEAT", 0.05)  # nhanh

    cn = psycopg2.connect(DATABASE_URL)
    cn.autocommit = True
    with cn.cursor() as cur:
        cur.execute(
            "INSERT INTO conversations (user_id, title, status, created_at) VALUES "
            "('admin','t','running',now()) RETURNING id::text"
        )
        conv = cur.fetchone()[0]
    cn.close()

    class _FakeReq:
        async def is_disconnected(self):
            return False

    resp = await sse_mod.sse(
        conv,
        _FakeReq(),
        claims={
            "role": "admin",
            "username": "admin",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
        },
    )
    frames = []
    it = resp.body_iterator
    for _ in range(3):
        frames.append(await it.__anext__())
    joined = "".join(frames)
    assert ": connected" in joined

    ping_frames = [f for f in frames if f.startswith("data:")]
    assert ping_frames, "Expected invariant was not satisfied at source line 165."
    payload = _json.loads(ping_frames[0][len("data: ") :].strip())
    assert payload["type"] == "ping"
    assert payload["conversation_id"] == conv
    assert payload["data"] == {}
    assert set(payload) == {"type", "conversation_id", "seq", "ts", "data"}


def test_bus_publish_no_subscriber_noop():

    emit.emit("nobody", "task.status", {"task": {"id": "t"}})
    assert bus.conn_count("nobody") == 0
