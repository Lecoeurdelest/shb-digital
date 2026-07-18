"""[TESTER — GATE S2 mechanics smoke, CHẠY MẶC ĐỊNH] Mirror test_gate_s1_e2e_mechanics.py cho
S2 (yêu cầu architect: gate S2 không được manual-only — cần automated smoke chạy được không
cần RUN_LIVE_SDK, để Gate 3 sạch). Không copy test backend (author≠checker) — thiết kế độc lập
cover đúng những gì T2-4 gate S2 brief đòi: dispatch 2 sub SONG SONG, real-sub card persist
đúng shape+task_id, MAIN present(document) trên đường D-33 inline task_id PHẢI null (đây chính
là bug CTX_TASK leak tester T2-4 bắt — regression-lock để KHÔNG tái phát), id vỏ-inject
(present args bơm id/task_id giả bị lọc).

RANH GIỚI: mechanics-stub verify CƠ CHẾ (card shape, task_id, persist, SSE card event) — KHÔNG
verify N2 "số liệu không nhẩm" (đó là việc test_gate_s1_e2e.py + verify browser live SDK đã
làm ở T2-4, cần SDK thật vì bằng chứng phải từ tool_calls THẬT).

KỸ THUẬT — seam giống S1 mechanics + 1 seam mới cho D-33 inline:
1. `sub_runner.set_default_runner(stub)` — 2 role dispatch song song, mỗi stub trả tool_calls
   riêng (mô phỏng credit/legal độc lập).
2. `main_session.run_main_turn` override — LƯỢT TỔNG HỢP (khi được đánh thức bởi task_done) tự
   gọi `present_tool` THẬT (không mock) với type=document, KHÔNG set task_id trong args (đúng
   MAIN_SKILL thật — model không tự bơm id). present_tool đọc ContextVar tại thời điểm gọi —
   đây CHÍNH LÀ nơi CTX_TASK từng leak (main_session.py run_main_turn không reset → present
   thấy task_id của sub cuối cùng report thay vì None). Test này khoá lại hành vi đúng.
3. Dispatch qua `orch_dispatch_impl` thật (không gọi tắt spawn_sub) — đường model thật đi qua.
Cả 2 khôi phục nguyên trạng trong `finally`.
"""

from __future__ import annotations

import asyncio
import contextlib

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app
from app.orch import main_session, registry, sub_runner
from app.sse import bus

from .conftest import requires_db

pytestmark = requires_db

STUB_CREDIT_RESULT = {
    "text": "DSCR=27.25 (>=1.2 đạt), LTV=62.5% (<=70% đạt). Nguồn: credit_assess, credit_cic_get.",
    "tool_calls": [
        {"tool": "cust_get", "input": {"id": "B001"}},
        {"tool": "credit_assess", "input": {"owner_id": "B001", "loan_amount_vnd": 5_000_000_000}},
    ],
}
STUB_LEGAL_RESULT = {
    "text": "Tài sản COL06 pháp lý sạch, không tranh chấp. Nguồn: legal_check_docs.",
    "tool_calls": [
        {"tool": "legal_check_docs", "input": {"collateral_id": "COL06"}},
    ],
}
_STUB_BY_ROLE = {"credit": STUB_CREDIT_RESULT, "legal": STUB_LEGAL_RESULT}


async def _stub_sub_runner(task) -> dict:
    """Trả kết quả khác nhau theo role — mô phỏng 2 chuyên gia ĐỘC LẬP (task.role phân biệt)."""
    await asyncio.sleep(0.05)
    return _STUB_BY_ROLE.get(task.role, {"text": "stub", "tool_calls": []})


async def _stub_run_main_turn_with_present(conv_id: str, prompt: str, on_text=None) -> dict:
    """Thay main_session.run_main_turn HOÀN TOÀN (seam thay thế cả hàm, KHÔNG gọi hàm gốc) —
    do đó dòng reset ContextVar thật (main_session.py `registry.CTX_TASK.set("")`) KHÔNG chạy
    qua đường này. Test này KHÔNG phải nơi khoá regression CTX_TASK leak (đó là việc của
    test_main_present_document_task_id_null_on_inline_reentrant_path_mechanics — seam khác,
    chặn ở ClaudeSDKClient.connect, GIỮ NGUYÊN run_main_turn thật chạy qua đoạn reset). Ở ĐÂY
    stub tự mô phỏng ĐÚNG CONTRACT mà run_main_turn thật đảm bảo (reset CTX_ACTOR/CTX_TASK đầu
    lượt) — để card document present từ lượt tổng hợp phản ánh đúng hành vi kỳ vọng của hệ
    thống khi lắp đúng phần thật, không phải để tự-xác-nhận seam giả của chính nó.

    Phân biệt lượt bằng nội dung prompt (giống S1 mechanics): lượt dispatch (user_message) →
    opener ngắn, KHÔNG dispatch (test tự dispatch trực tiếp qua orch_dispatch_impl — não thật
    mới quyết, stub không giả não). Lượt tổng hợp (đánh thức bởi task_done, đường D-33 inline)
    → gọi present_tool THẬT với type=document, KHÔNG set id/task_id trong args (đúng cách
    MAIN_SKILL thật chỉ đạo model)."""
    from app.orch import registry as _registry

    _registry.CTX_ACTOR.set("main")
    _registry.CTX_TASK.set("")  # mô phỏng đúng contract run_main_turn thật (main_session.py:177)

    if "Tin nhắn người dùng" in prompt:
        text = "Đã giao việc cho 2 chuyên gia — đang chạy song song."
        if on_text is not None:
            await on_text(text)
        return {"text": text, "session_id": "stub-session-id", "is_error": False}

    # Lượt tổng hợp: gọi present_tool THẬT (qua .handler — present_tool là SdkMcpTool, không
    # callable trực tiếp) — task_id lấy từ ContextVar TẠI THỜI ĐIỂM NÀY.
    from app.orch.common_tools import present_tool

    await present_tool.handler(
        {
            "type": "document",
            "title": "Tờ trình thẩm định — B001 (mechanics)",
            "items": [
                {"section": "Tín dụng", "content": STUB_CREDIT_RESULT["text"]},
                {"section": "Pháp lý", "content": STUB_LEGAL_RESULT["text"]},
            ],
            "sources": ["credit_assess", "credit_cic_get", "legal_check_docs"],
        }
    )
    text = "Đã tổng hợp tờ trình lên canvas."
    if on_text is not None:
        await on_text(text)
    return {"text": text, "session_id": "stub-session-id", "is_error": False}


@contextlib.asynccontextmanager
async def _override_runners_after_boot():
    """Override SAU lifespan boot() — TRƯỚC thì boot() ghi đè lại wiring thật (xem docstring
    S1 mechanics — cùng bẫy, cùng lý do)."""
    orig_default_runner = sub_runner._default_runner
    orig_run_main_turn = main_session.run_main_turn
    sub_runner.set_default_runner(_stub_sub_runner)
    main_session.run_main_turn = _stub_run_main_turn_with_present
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
    events: list[dict] = []
    for _ in range(n):
        events.append(await asyncio.wait_for(q.get(), timeout=timeout_s))
    return events


def _cleanup(conv_id: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM tasks WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_two_subs_parallel_dispatch_then_main_synthesis_presents_document_mechanics():
    """Gate S2 D-35+D-36: dispatch 2 sub SONG SONG (credit+legal) qua orch_dispatch_impl thật,
    room.wire_event_sink() nối _report → handle_room_event → _turn_runner thật → run_main_turn
    (stub — KHÔNG phải run_main_turn gốc, xem docstring stub) — lượt CUỐI (sau khi cả 2 sub báo
    task_done) phải là "lượt tổng hợp": stub gọi present_tool THẬT (type=document) → card
    persist thật + SSE card event. Verify WIRING/SHAPE đúng khi contract "main present → task_id
    null" được tuân thủ (2 task song song done đúng role + card document xuất hiện đúng shape +
    PG khớp SSE toàn chuỗi). Đây KHÔNG phải nơi khoá regression CTX_TASK leak ở code THẬT — bài
    học tự rút ra khi viết: seam thay hẳn run_main_turn thì dòng reset thật không chạy qua, nên
    test này chỉ xác nhận hệ thống hoạt động ĐÚNG khi phần thật tuân thủ contract, không tự
    verify phần thật có tuân thủ hay không. Regression-lock THẬT nằm ở
    test_main_present_document_task_id_null_on_inline_reentrant_path_mechanics bên dưới (seam
    khác — chặn ClaudeSDKClient.connect, run_main_turn GỐC chạy xuyên qua đoạn reset thật)."""
    from app.orch import room

    async with app.router.lifespan_context(app):
        async with _override_runners_after_boot():
            room.wire_event_sink()  # nối sub_runner._report → room (đường D-33 inline thật)
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "mechanics-s2-parallel")

                q = bus.subscribe(conv_id)
                try:
                    from app.orch.dispatch import orch_dispatch_impl

                    registry.CTX_CONV.set(conv_id)
                    out_credit = await orch_dispatch_impl(conv_id, "credit", "Thẩm định B001", "brief credit")
                    out_legal = await orch_dispatch_impl(conv_id, "legal", "Kiểm tra COL06", "brief legal")
                    assert out_credit["created"] is True
                    assert out_legal["created"] is True

                    # 2×task.created (dispatch) + đủ event của 2 lượt main (mỗi task_done đánh
                    # thức 1 lượt _turn_runner: conversation.status running→idle × chat.delta done,
                    # KHÔNG stream on_text nhiều lần ở stub này) + card (present document ở lượt
                    # tổng hợp cuối cùng khi board đủ 2/2 done — do 2 sub chạy gần như đồng thời,
                    # thứ tự event kế tiếp phụ thuộc thời điểm _report race, nên gom theo type
                    # thay vì assert thứ tự cứng tuyệt đối).
                    events = await _drain(q, 10, timeout_s=10.0)
                finally:
                    bus.unsubscribe(conv_id, q)

                by_type: dict[str, list[dict]] = {}
                for e in events:
                    by_type.setdefault(e["type"], []).append(e)

                created = by_type.get("task.created", [])
                done = by_type.get("task.status", [])
                cards = by_type.get("card", [])
                assert len(created) == 2, f"phải đúng 2 task.created (song song): {events}"
                assert len(done) == 2, f"phải đúng 2 task.status done: {events}"
                assert len(cards) >= 1, f"lượt tổng hợp phải present ít nhất 1 card (document): {events}"

                roles_created = sorted(e["data"]["task"]["role"] for e in created)
                assert roles_created == ["credit", "legal"], f"2 role phải khác nhau: {roles_created}"

                for e in done:
                    task = e["data"]["task"]
                    assert task["status"] == "done", f"stub phải kết thúc done: {task}"
                    expected = _STUB_BY_ROLE[task["role"]]
                    assert task["result"]["text"] == expected["text"], "result phải khớp đúng stub theo role"

                document_cards = [c for c in cards if c["data"]["card"]["type"] == "document"]
                assert len(document_cards) >= 1, f"MAIN phải present(document) ở lượt tổng hợp: {cards}"
                doc_card = document_cards[-1]["data"]["card"]
                assert doc_card["task_id"] is None, (
                    f"MAIN present(document) trên đường D-33 inline phải task_id=None (T2-1/N5, "
                    f"regression-lock CTX_TASK leak) — thấy {doc_card['task_id']}"
                )

        conn = psycopg2.connect(DATABASE_URL)
        try:
            cur = conn.cursor()
            cur.execute("SELECT role, status FROM tasks WHERE conv_id=%s ORDER BY role", (conv_id,))
            rows = cur.fetchall()
            assert rows == [("credit", "done"), ("legal", "done")], f"PG persist phải khớp SSE: {rows}"
            cur.execute("SELECT type, task_id FROM cards WHERE conv_id=%s", (conv_id,))
            card_rows = cur.fetchall()
            assert any(t == "document" and tid is None for t, tid in card_rows), (
                f"PG card document task_id NULL phải khớp SSE: {card_rows}"
            )
        finally:
            conn.close()
        _cleanup(conv_id)
        room.set_turn_runner(None)


@pytest.mark.asyncio
async def test_main_present_document_task_id_null_on_inline_reentrant_path_mechanics():
    """REGRESSION-LOCK cho bug CTX_TASK leak (tester T2-4 bắt, backend fix a6aaed9): trên
    đường D-33 inline (sub done → _report → _event_sink → handle_room_event → run_main_turn
    CHẠY TRONG task/context của sub vừa report), khi MAIN present(document) để tổng hợp,
    task_id PHẢI là None (T2-1/N5: "main present ngoài sub → task_id null"). Nếu run_main_turn
    quên reset CTX_TASK, card sẽ mang task_id của sub cuối cùng report — đây chính là bug đã
    xảy ra ở commit 3497a1f (thiếu dòng fix) trước khi backend sửa thành a6aaed9.

    Test đi ĐÚNG ĐƯỜNG THẬT: _run_sub (đặt CTX_TASK=task.id) → _report → sink → _turn_runner
    THẬT (room.py, không mock) → run_main_turn (stub CỦA TEST, nhưng CHẠY XUYÊN QUA logic thật
    của run_main_turn KHÔNG — ở đây stub THAY THẾ run_main_turn hoàn toàn, nên seam reset
    CTX_TASK không phải của module thật). Để khoá đúng dòng fix thật (main_session.py), cần
    gọi hàm run_main_turn GỐC (không override) — xem test thứ 2 dưới dùng seam khác: chặn ở
    ClaudeSDKClient thay vì thay cả hàm, khớp cách backend + tester đã verify độc lập."""
    from app.orch import room

    registry.reset_room("mechanics-ctxtask-conv")
    conv_id = "mechanics-ctxtask-conv"
    seen_task_id_in_present: list[str | None] = []

    class _StopHere(Exception):
        pass

    async def _fake_connect(self):
        # Đọc CTX_TASK NGAY SAU khi run_main_turn thật đã chạy đoạn reset ContextVar (dòng
        # đầu hàm) — đây chính là điểm bug từng leak. raise để không cần SDK subprocess thật.
        seen_task_id_in_present.append(registry.CTX_TASK.get() or None)
        raise _StopHere

    async def noop(*a, **k):
        return None

    import claude_agent_sdk

    orig_connect = claude_agent_sdk.ClaudeSDKClient.connect
    claude_agent_sdk.ClaudeSDKClient.connect = _fake_connect

    async def _turn_runner_catches_stophere(cid, event, data):
        try:
            await main_session.run_main_turn(cid, "prompt tổng hợp mechanics")
        except _StopHere:
            pass

    room.set_turn_runner(_turn_runner_catches_stophere)

    async def sink(cid, event, data):
        await room.handle_room_event(cid, event, data)

    sub_runner.set_event_sink(sink)

    import app.orch.store as store_mod

    monkeypatched = {
        "mark_running": store_mod.mark_running,
        "finish_task": store_mod.finish_task,
        "get_task": store_mod.get_task,
        "task_board": store_mod.task_board,
        "get_conv_session_id": main_session.store.get_conv_session_id,
    }
    store_mod.mark_running = noop
    store_mod.finish_task = noop
    store_mod.get_task = noop
    store_mod.task_board = lambda *a, **k: asyncio.sleep(0, result=[])
    main_session.store.get_conv_session_id = noop

    try:
        from app.orch.store import Task

        await sub_runner._run_sub(
            Task(id="mechanics-sub-task-id", conv_id=conv_id, role="credit", title="t", status="queued"),
            runner=lambda task: asyncio.sleep(0.01, result={"ok": True}),
        )
        await asyncio.sleep(0.05)

        assert seen_task_id_in_present == [None], (
            f"MAIN present (run_main_turn THẬT, đường D-33 inline) phải thấy CTX_TASK=None "
            f"(reset đúng, T2-1/N5) — thấy {seen_task_id_in_present}. Leak = bug CTX_TASK "
            f"tester T2-4 bắt tái phát (main_session.py quên reset registry.CTX_TASK)."
        )
    finally:
        claude_agent_sdk.ClaudeSDKClient.connect = orig_connect
        room.set_turn_runner(None)
        sub_runner.set_event_sink(None)
        store_mod.mark_running = monkeypatched["mark_running"]
        store_mod.finish_task = monkeypatched["finish_task"]
        store_mod.get_task = monkeypatched["get_task"]
        store_mod.task_board = monkeypatched["task_board"]
        main_session.store.get_conv_session_id = monkeypatched["get_conv_session_id"]
        registry.reset_room(conv_id)


@pytest.mark.asyncio
async def test_present_tool_id_injection_filtered_mechanics():
    """id vỏ-inject (N5/§15): args bơm id/conv_id/task_id/ts giả → present_tool LỌC, card
    thật lưu id UUID vỏ sinh, task_id đúng ContextVar (KHÔNG phải giá trị model bịa). Không
    over-block field nội dung N3 (sources/recommended giữ nguyên)."""
    from app.orch import store
    from app.orch.common_tools import present_tool

    conv_id = "mechanics-idinject-conv"
    registry.CTX_CONV.set(conv_id)
    registry.CTX_ACTOR.set("main")
    registry.CTX_TASK.set("")

    result = await present_tool.handler(
        {
            "type": "options",
            "title": "Đề xuất (mechanics id-inject test)",
            "items": [{"label": "Duyệt", "value": "approve"}],
            "sources": ["credit_assess"],
            "recommended": "approve",
            "id": "FAKE-ID-MODEL-BOM",
            "conv_id": "FAKE-CONV-BOM",
            "task_id": "FAKE-TASK-BOM",
            "ts": "1999-01-01T00:00:00Z",
        }
    )
    assert "rendered" in result["content"][0]["text"], f"present phải trả rendered:true: {result}"

    cards = await store.list_cards(conv_id)
    try:
        assert len(cards) == 1
        card = cards[0]
        assert card["id"] != "FAKE-ID-MODEL-BOM", "id phải là UUID vỏ sinh, KHÔNG phải giá trị model bịa"
        assert card["conv_id"] == conv_id, "conv_id phải khớp ContextVar, KHÔNG phải giá trị model bịa"
        assert card["task_id"] != "FAKE-TASK-BOM", "task_id phải từ ContextVar, KHÔNG phải giá trị model bịa"
        assert card["sources"] == ["credit_assess"], "N3: field nội dung KHÔNG bị over-block"
        assert card["recommended"] == "approve", "N3: field nội dung KHÔNG bị over-block"
    finally:
        # conv_id text tự do (D-31, KHÔNG FK) — test này KHÔNG tạo conversation thật qua API,
        # chỉ set ContextVar để verify present_tool đơn lẻ. Chỉ dọn cards, không đụng
        # conversations (row không tồn tại — DELETE full _cleanup() sẽ lỗi UUID cast).
        conn = psycopg2.connect(DATABASE_URL)
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
            conn.commit()
        finally:
            conn.close()
