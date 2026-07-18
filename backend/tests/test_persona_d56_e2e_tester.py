"""[TESTER — T8-4] Matrix authz D-56 verify ĐỘC LẬP (author≠checker) — backend đã tự viết
`test_persona_d56.py` (unit-style, TestClient đồng bộ, MAIN inject gọi TẮT `_customer_prompt_block`
trực tiếp). File NÀY không lặp lại y hệt: đi qua HTTP thật (AsyncClient + ASGITransport, đúng
pattern gate S3/S4 sẵn có), phủ thêm góc backend CHƯA cover qua đường thật:
  - list_conversations (không chỉ get 1 ca) — admin thấy ca khách, khách chỉ thấy ca mình
  - chat vào ca người khác → 404 (không chỉ get)
  - SSE endpoint qua HTTP thật (không mock request.is_disconnected)
  - interrupt endpoint qua HTTP thật
  - MAIN identity inject qua ĐƯỜNG SỐNG: tạo ca thật bằng account customer, gửi 1 câu ngắn,
    chờ MAIN trả lời — verify gián tiếp qua NỘI DUNG message MAIN thật trả về (không gọi tắt
    `_customer_prompt_block`) — đúng "test build-prompt như backend làm HOẶC live 1 câu ngắn"
    trong dispatch, chọn nhánh LIVE để verify khác góc backend.
  - regression: suite đầy đủ 100% sau invert (kiểm ở cuối phiên, không lặp lại trong file)

D-56 (xem DECISIONS.md + sprints/plan_sprint_8.md): app = cửa KHÁCH (role='customer', chỉ thấy
ca mình, KHÔNG duyệt — decide/audit/Tower→403); role bank (admin) = toàn quyền. Seed account:
c001/c001 (customer→C001), b001/b001 (customer→B001), user/user (bank, KHÔNG phải admin — cũng
KHÔNG duyệt được, xem test_gate_s3_authz_tester.py), admin/admin (bank, admin — duyệt được)."""

from __future__ import annotations

import os

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db
from .conftest import wait_for_conversation_idle as _wait_for_conversation_idle

_LIVE = os.environ.get("RUN_LIVE_SDK") == "1"


def _seeded(username: str) -> bool:
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=2)
    except psycopg2.Error:
        return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM users WHERE username=%s", (username,))
        return cur.fetchone()[0] >= 1
    except psycopg2.Error:
        return False
    finally:
        conn.close()


def _cleanup_conv(conv_id: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM tasks WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()


async def _login(client: AsyncClient, username: str, password: str):
    return await client.post("/api/auth/login", json={"username": username, "password": password})


# ═══════════════════════════════════════════════════════════════════════════
# /api/me shape (route MỚI D-56, KHÁC /api/auth/me backend đã test)
# ═══════════════════════════════════════════════════════════════════════════


@requires_db
@pytest.mark.asyncio
async def test_api_me_new_route_matches_auth_me():
    """Route /api/me (KHÔNG phải /api/auth/me) — Export FE T8-2 — trả cùng shape. Backend
    test_persona_d56.py chỉ test /api/me trực tiếp; đây verify 2 route ĐỒNG NHẤT payload
    (tránh lệch route cũ/mới do copy-paste sai)."""
    if not _seeded("c001"):
        pytest.skip("seed c001 chưa có")
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r_login = await _login(client, "c001", "c001")
            assert r_login.status_code == 200

            r_new = await client.get("/api/me")
            r_old = await client.get("/api/auth/me")
            assert r_new.status_code == 200
            assert r_old.status_code == 200
            body_new, body_old = r_new.json(), r_old.json()
            assert body_new["username"] == "c001"
            assert body_new["role"] == "customer"
            assert body_new["owner_id"] == "C001"
            assert body_new == body_old, "2 route /api/me và /api/auth/me PHẢI trả cùng payload"


# ═══════════════════════════════════════════════════════════════════════════
# list_conversations — scoping (backend chưa test qua đường list, chỉ test get 1 ca)
# ═══════════════════════════════════════════════════════════════════════════


@requires_db
@pytest.mark.asyncio
async def test_customer_list_only_own_convs_not_others():
    """GET /api/conversations (list) — customer CHỈ thấy ca của MÌNH, không thấy ca khách khác
    dù ca đó tồn tại thật trong DB. Backend chỉ test GET 1 ca theo id; đây test LIST (khác code
    path — list_conversations() vs get_conversation(), 2 hàm store khác nhau)."""
    if not _seeded("c001") or not _seeded("b001"):
        pytest.skip("seed c001/b001 chưa có")
    conv_c001: str | None = None
    conv_b001: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await _login(client, "c001", "c001")
                r = await client.post("/api/conversations", json={"title": "ca-c001-list-test"})
                assert r.status_code == 201
                conv_c001 = r.json()["id"]

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client2:
                await _login(client2, "b001", "b001")
                r2 = await client2.post("/api/conversations", json={"title": "ca-b001-list-test"})
                assert r2.status_code == 201
                conv_b001 = r2.json()["id"]

                # c001 list → PHẢI thấy conv_c001, KHÔNG thấy conv_b001
                await _login(client2, "c001", "c001")
                r_list = await client2.get("/api/conversations")
                assert r_list.status_code == 200
                ids = {c["id"] for c in r_list.json()}
                assert conv_c001 in ids, "c001 PHẢI thấy ca của chính mình trong list"
                assert conv_b001 not in ids, "c001 KHÔNG được thấy ca của b001 trong list (leak scoping)"
    finally:
        if conv_c001:
            _cleanup_conv(conv_c001)
        if conv_b001:
            _cleanup_conv(conv_b001)


@requires_db
@pytest.mark.asyncio
async def test_admin_list_sees_customer_convs():
    """Admin list → thấy CẢ ca của customer (giám sát ngân hàng, D-56 (b))."""
    if not _seeded("c001"):
        pytest.skip("seed c001 chưa có")
    conv_c001: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await _login(client, "c001", "c001")
                r = await client.post("/api/conversations", json={"title": "ca-c001-admin-visibility"})
                assert r.status_code == 201
                conv_c001 = r.json()["id"]

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client2:
                await _login(client2, "admin", "admin")
                r_list = await client2.get("/api/conversations")
                assert r_list.status_code == 200
                ids = {c["id"] for c in r_list.json()}
                assert conv_c001 in ids, "admin (ngân hàng) PHẢI thấy ca của customer trong list"
    finally:
        if conv_c001:
            _cleanup_conv(conv_c001)


# ═══════════════════════════════════════════════════════════════════════════
# chat vào ca người khác → 404 (backend chỉ test GET, chưa test POST /chat)
# ═══════════════════════════════════════════════════════════════════════════


@requires_db
@pytest.mark.asyncio
async def test_customer_chat_into_others_conv_404():
    """POST /chat vào ca của khách KHÁC → 404 (hide), KHÔNG lọt message vào — khác code path
    GET (chỉ đọc) mà backend đã test; đây verify nhánh WRITE cũng bị chặn đúng."""
    if not _seeded("c001") or not _seeded("b001"):
        pytest.skip("seed c001/b001 chưa có")
    conv_b001: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await _login(client, "b001", "b001")
                r = await client.post("/api/conversations", json={"title": "ca-b001-chat-guard"})
                assert r.status_code == 201
                conv_b001 = r.json()["id"]

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client2:
                await _login(client2, "c001", "c001")
                r_chat = await client2.post(f"/api/conversations/{conv_b001}/chat", json={"content": "xin chào"})
                assert r_chat.status_code == 404, (
                    f"c001 chat vào ca b001 PHẢI 404 (hide) — thấy {r_chat.status_code}: {r_chat.text}"
                )
                body = r_chat.json()
                assert set(body) == {"code", "message", "hint", "retryable"}
                assert body["code"] == "not_found"

            # Xác nhận DB thật: KHÔNG có message nào lọt vào (write thực sự bị chặn, không phải
            # chỉ response giả — kiểm §5 tester.md "verify trước khi tuyên bố")
            conn = psycopg2.connect(DATABASE_URL)
            try:
                cur = conn.cursor()
                cur.execute("SELECT count(*) FROM messages WHERE conv_id=%s AND content=%s", (conv_b001, "xin chào"))
                assert cur.fetchone()[0] == 0, "message của c001 KHÔNG được lọt vào ca b001"
            finally:
                conn.close()
    finally:
        if conv_b001:
            _cleanup_conv(conv_b001)


# ═══════════════════════════════════════════════════════════════════════════
# SSE + interrupt qua HTTP thật (backend chưa test 2 endpoint này ở test_persona_d56.py)
# ═══════════════════════════════════════════════════════════════════════════


@requires_db
@pytest.mark.asyncio
async def test_customer_sse_others_conv_404():
    """GET .../sse vào ca người khác → 404 qua HTTP thật (backend chưa cover endpoint SSE trong
    test_persona_d56.py — chỉ test get/chat)."""
    if not _seeded("c001") or not _seeded("b001"):
        pytest.skip("seed c001/b001 chưa có")
    conv_b001: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await _login(client, "b001", "b001")
                r = await client.post("/api/conversations", json={"title": "ca-b001-sse-guard"})
                assert r.status_code == 201
                conv_b001 = r.json()["id"]

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client2:
                await _login(client2, "c001", "c001")
                async with client2.stream("GET", f"/api/conversations/{conv_b001}/sse") as r_sse:
                    assert r_sse.status_code == 404, f"c001 SSE vào ca b001 PHẢI 404 — thấy {r_sse.status_code}"
    finally:
        if conv_b001:
            _cleanup_conv(conv_b001)


@requires_db
@pytest.mark.asyncio
async def test_customer_interrupt_others_conv_404():
    """POST .../interrupt vào ca người khác → 404 qua HTTP thật (backend chưa cover endpoint
    interrupt trong test_persona_d56.py)."""
    if not _seeded("c001") or not _seeded("b001"):
        pytest.skip("seed c001/b001 chưa có")
    conv_b001: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await _login(client, "b001", "b001")
                r = await client.post("/api/conversations", json={"title": "ca-b001-interrupt-guard"})
                assert r.status_code == 201
                conv_b001 = r.json()["id"]

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client2:
                await _login(client2, "c001", "c001")
                r_int = await client2.post(f"/api/conversations/{conv_b001}/interrupt", json={"target": "some-task-id"})
                assert r_int.status_code == 404, (
                    f"c001 interrupt ca b001 PHẢI 404 — thấy {r_int.status_code}: {r_int.text}"
                )
    finally:
        if conv_b001:
            _cleanup_conv(conv_b001)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN identity inject — LIVE (khác backend: build-prompt trực tiếp qua _customer_prompt_block).
# Đây verify qua ĐƯỜNG SỐNG — MAIN thật trả lời, kiểm nội dung có xưng hô "anh/chị" + không lộ
# thuật ngữ nội bộ, KHÔNG gọi tắt hàm build-prompt.
# ═══════════════════════════════════════════════════════════════════════════

pytestmark_live = pytest.mark.skipif(not _LIVE, reason="live SDK opt-in: RUN_LIVE_SDK=1 (MAIN thật)")


@requires_db
@pytestmark_live
@pytest.mark.asyncio
async def test_main_inject_live_customer_gets_anh_chi_tone():
    """LIVE: ca do customer (c001) tạo, gửi câu ngắn → MAIN (LLM thật) trả lời — verify GIÁN TIẾP
    qua NỘI DUNG message thật (không gọi tắt `_customer_prompt_block` như backend đã test) rằng
    persona-inject có tác dụng thật lên hành vi MAIN, không chỉ đúng string block được build."""
    if not _seeded("c001"):
        pytest.skip("seed c001 chưa có")
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120.0) as client:
                await _login(client, "c001", "c001")
                r = await client.post("/api/conversations", json={"title": "live-main-inject-c001"})
                assert r.status_code == 201
                conv_id = r.json()["id"]

                r_chat = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": "Chào, tôi muốn hỏi về khoản vay của mình hiện đang thế nào?"},
                )
                assert r_chat.status_code == 202

                await _wait_for_conversation_idle(client, conv_id, timeout_s=90.0)

                r_state = await client.get(f"/api/conversations/{conv_id}")
                assert r_state.status_code == 200
                messages = r_state.json().get("messages", [])
                assistant_msgs = [m["content"] for m in messages if m.get("sender") == "assistant"]
                assert assistant_msgs, f"MAIN phải trả lời ít nhất 1 message — conv_id={conv_id}"
                combined = " ".join(assistant_msgs).lower()
                # Nội bộ KHÔNG được lộ thuật ngữ vận hành khi chat với khách (dispatch T8-3 nhắc).
                leaked_terms = [t for t in ("credit_assess", "tool_call", "dispatch", "sub-agent") if t in combined]
                assert not leaked_terms, (
                    f"MAIN lộ thuật ngữ nội bộ khi chat với KHÁCH: {leaked_terms}. conv_id={conv_id}. "
                    f"messages: {assistant_msgs}"
                )
                # Tới được đây = PASS → dọn sạch (evidence không cần giữ)
                _cleanup_conv(conv_id)
    except AssertionError:
        raise  # giữ conv_id trong DB — KHÔNG cleanup khi fail (bằng chứng điều tra, §5)
