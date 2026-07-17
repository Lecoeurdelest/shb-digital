"""[TESTER — GATE S1 mechanics smoke, CHẠY MẶC ĐỊNH] Bổ sung theo yêu cầu architect sau khi
commit T1-3 (ed2b302): `test_gate_s1_e2e.py` (2 test) là SDK-live opt-in (RUN_LIVE_SDK=1) —
default `uv run pytest` KHÔNG có test nào verify SSE-mechanics end-to-end (chat→SSE envelope
→task.created→task.status→chat.delta done→full-state shape). Chat/SSE là bề mặt dễ vỡ ở S2+
(đổi emit/room/stream wiring) — thiếu lớp này thì gate mechanics mục ruỗng cho tới khi có ai
chạy RUN_LIVE_SDK=1 (hiếm trong vòng lặp dev thường).

RANH GIỚI (chốt cùng architect): mechanics-stub verify VỎ (SSE envelope 1-shape/seq per-turn/
task lifecycle/CONTRACT §3 full-state) — KHÔNG verify N2 "không nhẩm" (đó là việc của
test_gate_s1_e2e.py, giữ nguyên, cần SDK thật vì bằng chứng phải tới từ tool_calls THẬT).

KỸ THUẬT — 2 seam public override được (KHÔNG sửa code sản phẩm, không patch private):
1. `app.orch.sub_runner.set_default_runner(stub)` — orch_dispatch_impl gọi `spawn_sub(task)`
   không truyền runner → dùng `_default_runner` global; override tạm bằng stub trả DSCR
   shape giống thật ({text, tool_calls}) KHÔNG cần SDK subprocess.
2. `app.orch.main_session.run_main_turn` — module-level function, Python resolve theo tên
   trong module namespace mỗi lần `_turn_runner` gọi → monkeypatch attribute này (không phải
   patch `_turn_runner`, giữ nguyên TOÀN BỘ logic wiring thật: persist message, emit SSE,
   Gap1/Gap2 error handling — đây CHÍNH LÀ mechanics cần verify) có hiệu lực ngay.
Cả 2 khôi phục nguyên trạng trong `finally` (tránh leak sang test khác/gate live-SDK trong
cùng process pytest).

Đọc SSE qua `app.sse.bus.subscribe(conv_id)` trực tiếp (KHÔNG qua HTTP streaming endpoint) —
tránh toàn bộ vấn đề TestClient/ASGITransport đã gặp ở test_gate_s1_e2e.py (đọc docstring
file đó): bus là nguồn sự thật duy nhất publish (SSE router chỉ forward), nên subscribe thẳng
xác nhận đúng những gì client THẬT sẽ nhận, không phụ thuộc transport HTTP.
"""

from __future__ import annotations

import asyncio
import contextlib

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app
from app.orch import main_session, sub_runner
from app.sse import bus

from .conftest import requires_db

pytestmark = requires_db  # cần PG (auth users seed + persist) — KHÔNG cần RUN_LIVE_SDK

STUB_DSCR_RESULT = {
    "text": "## Kết quả thẩm định DSCR — Khách hàng C001\n\nDSCR = 3.709 (thu nhập 30tr/nợ 8.088.576đ)."
    "\n\nNguồn: tool credit_assess.",
    "tool_calls": [
        {"tool": "cust_get", "input": {"id": "C001"}},
        {"tool": "credit_assess", "input": {"owner_id": "C001", "loan_amount_vnd": 0}},
    ],
}


async def _stub_sub_runner(task) -> dict:
    """Thay run_sub_turn thật — trả kết quả ĐÚNG SHAPE (text + tool_calls) không cần SDK."""
    await asyncio.sleep(0.05)  # nhường event loop, mô phỏng độ trễ I/O tối thiểu
    return STUB_DSCR_RESULT


async def _stub_run_main_turn(conv_id: str, prompt: str, on_text=None) -> dict:
    """Thay main_session.run_main_turn thật. 2 lượt phân biệt bằng nội dung prompt:
    - Lượt dispatch (user_message): trả opener ngắn — KHÔNG tự gọi orch_dispatch thật (đó là
      việc của MCP tool orch_dispatch mount vào main SDK, mechanics-stub không có tool-call
      loop) → mechanics test tự dispatch trực tiếp qua orch.dispatch.orch_dispatch_impl thay
      vì trông cậy stub main "quyết định" gọi tool (não thật mới quyết, stub không giả não).
    - Lượt tổng hợp (task_done event): trả text chứa DSCR (mô phỏng main đã tổng hợp)."""
    text = "Đã ghi nhận yêu cầu." if "Tin nhắn người dùng" in prompt else STUB_DSCR_RESULT["text"]
    if on_text is not None:
        await on_text(text)
    return {"text": text, "session_id": "stub-session-id", "is_error": False}


@contextlib.asynccontextmanager
async def _override_runners_after_boot():
    """Override 2 seam SAU KHI lifespan (main_session.boot()) đã chạy — TRƯỚC lifespan thì
    `boot()` ghi đè lại `_default_runner`/wiring bằng SDK thật, làm stub vô nghĩa và khiến
    `_run_sub` treo/nổ khi cố connect SDK thật không có auth trong môi trường test (triệu
    chứng THẬT gặp ở lần thử đầu: task.result.reason='user hủy' — SDK bị cancel khi pytest
    timeout dọn event loop, không phải bug mechanics). Khôi phục nguyên trạng ở finally."""
    orig_default_runner = sub_runner._default_runner
    orig_run_main_turn = main_session.run_main_turn
    sub_runner.set_default_runner(_stub_sub_runner)
    main_session.run_main_turn = _stub_run_main_turn
    try:
        yield
    finally:
        sub_runner.set_default_runner(orig_default_runner)
        main_session.run_main_turn = orig_run_main_turn


async def _login_and_create_conv(client: AsyncClient, title: str) -> str:
    r = await client.post("/api/auth/login", json={"username": "user", "password": "user"})
    assert r.status_code == 200, f"login thất bại: {r.status_code} {r.text}"
    r2 = await client.post("/api/conversations", json={"title": title})
    assert r2.status_code == 201, f"tạo ca thất bại: {r2.status_code} {r2.text}"
    return r2.json()["id"]


async def _drain(q: asyncio.Queue, n: int, timeout_s: float = 10.0) -> list[dict]:
    """Đọc đúng n event từ bus queue, timeout để không treo test khi mechanics thật vỡ."""
    events: list[dict] = []
    for _ in range(n):
        events.append(await asyncio.wait_for(q.get(), timeout=timeout_s))
    return events


@pytest.mark.asyncio
async def test_sse_envelope_shape_and_task_lifecycle_mechanics():
    """Mechanics KHÔNG cần SDK: dispatch task credit (stub runner) → verify:
    1. SSE envelope 1-shape (CONTRACT §4): mọi event có đủ {type, conversation_id, seq, ts, data}.
    2. task.created → task.status(done) đúng thứ tự, đúng role, kèm result (từ stub).
    3. task.status(done).data.task.result khớp STUB_DSCR_RESULT (shape tool_calls/text)."""
    async with app.router.lifespan_context(app):  # boot() chạy TRƯỚC — set wiring thật
        async with _override_runners_after_boot():  # rồi mới override thành stub — thứ tự bắt buộc
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "mechanics-dispatch")

                q = bus.subscribe(conv_id)
                try:
                    from app.orch.dispatch import orch_dispatch_impl

                    out = await orch_dispatch_impl(conv_id, "credit", "Thẩm định C001 (mechanics)", "brief mechanics")
                    assert out["created"] is True, f"dispatch phải tạo task mới: {out}"

                    events = await _drain(q, 2, timeout_s=10.0)
                finally:
                    bus.unsubscribe(conv_id, q)

                for ev in events:
                    assert set(ev.keys()) == {"type", "conversation_id", "seq", "ts", "data"}, (
                        f"SSE envelope lệch shape CONTRACT §4: {ev.keys()}"
                    )
                    assert ev["conversation_id"] == conv_id

                types = [ev["type"] for ev in events]
                assert types == ["task.created", "task.status"], f"thứ tự event sai: {types}"

                created_task = events[0]["data"]["task"]
                assert created_task["role"] == "credit"
                assert created_task["status"] == "queued"

                done_task = events[1]["data"]["task"]
                assert done_task["status"] == "done", f"stub runner phải kết thúc done: {done_task}"
                tool_names = [tc["tool"] for tc in done_task["result"]["tool_calls"]]
                assert "credit_assess" in tool_names, f"result phải giữ shape tool_calls từ stub: {done_task['result']}"
                assert "3.709" in done_task["result"]["text"]

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SELECT role, status FROM tasks WHERE conv_id=%s", (conv_id,))
        rows = cur.fetchall()
        assert len(rows) == 1 and rows[0] == ("credit", "done"), f"PG persist phải khớp SSE: {rows}"
        cur.execute("DELETE FROM tasks WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_chat_flow_emits_conversation_status_and_chat_delta_done_mechanics():
    """Mechanics KHÔNG cần SDK: POST /chat → handle_room_event (spine thật) → stub main_turn
    → verify conversation.status(running→idle) + chat.delta(done=True, full_text) đúng Gap1
    (CONTRACT §4b: MỌI kết lượt bắn done) + persist message assistant khớp full_text.

    4 event thật (không phải 3 — đã sửa sau lần chạy đầu FAIL): _turn_runner gọi on_text(chunk)
    → emit_chat_delta(done=False) 1 lần (stub chỉ gọi on_text 1 lần), RỒI emit_chat_done() bắn
    THÊM 1 event type='chat.delta' (done=True) riêng — không phải cùng 1 event chỉnh sửa tại
    chỗ. Tổng: running → chat.delta(false) → chat.delta(true) → idle."""
    async with app.router.lifespan_context(app):
        async with _override_runners_after_boot():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "mechanics-chat")

                q = bus.subscribe(conv_id)
                try:
                    r = await client.post(f"/api/conversations/{conv_id}/chat", json={"content": "Câu hỏi mechanics"})
                    assert r.status_code == 202
                    assert r.json().get("queued") is True

                    events = await _drain(q, 4, timeout_s=10.0)
                finally:
                    bus.unsubscribe(conv_id, q)

                for ev in events:
                    assert set(ev.keys()) == {"type", "conversation_id", "seq", "ts", "data"}

                types = [ev["type"] for ev in events]
                assert types == ["conversation.status", "chat.delta", "chat.delta", "conversation.status"], (
                    f"thứ tự sai: {types}"
                )
                assert events[0]["data"]["status"] == "running"
                assert events[1]["data"]["done"] is False, "chat.delta đầu (streaming chunk) done=False"
                assert events[2]["data"]["done"] is True, "Gap1: chat.delta cuối lượt PHẢI done=True"
                assert events[2]["data"]["full_text"] == "Đã ghi nhận yêu cầu."
                assert events[3]["data"]["status"] == "idle"

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SELECT sender, content FROM messages WHERE conv_id=%s ORDER BY ts", (conv_id,))
        rows = cur.fetchall()
        senders = [r[0] for r in rows]
        assert senders == ["user", "assistant"], f"PG messages phải khớp Gap1 persist: {senders}"
        assert rows[1][1] == "Đã ghi nhận yêu cầu.", "message assistant phải khớp full_text SSE"
        cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_get_full_state_shape_matches_contract_after_mechanics_flow():
    """CONTRACT §3 ConversationFullState = {conversation, messages[], tasks[]} — verify shape
    đúng SAU 1 vòng chat+dispatch mechanics (không cần SDK), field-level.

    Đợi ĐỦ 4 event (xem test trên) trước khi GET — thiếu 1 event cuối (conversation.status=
    idle) thì lượt CHƯA thật sự kết thúc, GET sẽ đọc status='running' (lỗi quan sát ở lần
    chạy đầu, không phải bug thật)."""
    async with app.router.lifespan_context(app):
        async with _override_runners_after_boot():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "mechanics-fullstate")

                q = bus.subscribe(conv_id)
                try:
                    r = await client.post(f"/api/conversations/{conv_id}/chat", json={"content": "test"})
                    assert r.status_code == 202
                    await _drain(q, 4, timeout_s=10.0)
                finally:
                    bus.unsubscribe(conv_id, q)

                state = (await client.get(f"/api/conversations/{conv_id}")).json()
                assert set(state.keys()) == {"conversation", "messages", "tasks"}
                assert state["conversation"]["id"] == conv_id
                assert state["conversation"]["status"] == "idle"
                assert isinstance(state["messages"], list) and len(state["messages"]) == 2
                for m in state["messages"]:
                    assert set(m.keys()) >= {"id", "conv_id", "ts", "sender", "content"}
                assert state["tasks"] == []  # câu "test" không dispatch — mechanics đúng route thật

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()
