"""[TESTER — T3-4] GATE S3 end-to-end — CHỖ CHỨNG MINH resume THẬT (architect nhấn mạnh: 15
test T3-2 của backend mock handle_room_event → chỉ chứng minh wake DISPATCHED đúng args, KHÔNG
chứng minh main RESUME + Ops re-execute THẬT. Đây là câu user hỏi trực tiếp "ai kích hoạt sự
kiện thực thi → resume → disburse thật" — chỉ live SDK mới trả lời được, vì phụ thuộc MAIN (LLM
thật) có follow đúng prompt "giao lại cho Vận hành gọi lại disburse" hay không.

D-40 happy-path (SPEC + brief #14): ca "giải ngân 5 tỷ cho DN X" (loan L007) → Ops gọi disburse
→ phanh CHẶN (approval_required + phiếu pending + card approval + waiting_approval) → admin
POST /api/approvals/{id}/decide {decision:approved} THẬT → SSE approval.decided + đánh thức
main → main (LLM thật) đọc prompt → PHẢI tự dispatch role operations → Ops gọi lại disburse →
wrapper bước 2 claim → loans.status='disbursed' + receipt. Query PG đối chiếu toàn chuỗi.

Nhánh reject: decide rejected → main báo user từ chối, loans.status KHÔNG đổi.

PRE-SCAFFOLD — viết trong lúc chờ FE T3-3 (approval panel UI, chưa xong tại thời điểm viết file
này — xem Cairn #13). Phần PG/API test (không cần browser) viết trước, chạy live SDK ngay khi
seed data sẵn. Phần browser (bấm Duyệt trên UI thật) sẽ bổ sung khi FE T3-3 báo Exports/UI sẵn
sàng — Chrome MCP workaround đã biết từ S2 (form_input + javascript_tool .click(), computer
click có thể flaky tuỳ phiên).

Finding SỚM đã báo architect trước khi chạy (đọc code trước khi tốn live SDK call): đọc
`roles/operations/SKILL.md` thấy dòng "Giải ngân THẬT ... CHƯA có ở stub này" — NGƯỢC với thực
tế `functions.py` đã mount `disburse` từ T3-1. Nếu ca live dưới đây main không tự dispatch/Ops
không gọi disburse → nghi ngay SKILL lệch trước khi nghi cơ chế (§6b thứ tự nghi vấn)."""

from __future__ import annotations

import asyncio
import os

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db

_LIVE = os.environ.get("RUN_LIVE_SDK") == "1"

pytestmark = [
    requires_db,
    pytest.mark.skipif(not _LIVE, reason="live SDK opt-in: RUN_LIVE_SDK=1 (resume cần MAIN thật quyết dispatch)"),
]

TEST_LOAN_ID = "L007"  # seed thật: owner B001, principal 3 tỷ, status active
TEST_OWNER_ID = "B001"  # BÀI HỌC (lần chạy đầu FAIL vì thiếu): sub credit/legal/operations
# ĐÚNG khi từ chối tự bịa owner_id (N2) — câu prompt PHẢI nêu rõ owner_id, không chỉ loan_id,
# nếu không MAIN dispatch cả 3 role rồi TẤT CẢ hỏi lại → không bao giờ tới bước gọi disburse.
TEST_AMOUNT = 1_000_000_000  # BÀI HỌC (lần chạy 2 FAIL): 5 tỷ VƯỢT hạn mức L007 (3 tỷ) → MAIN
# ĐÚNG khi tự chặn (N2 kiểm soát rủi ro, không phải bug) — dùng số DƯỚI hạn mức để test đúng
# cơ chế PHANH duyệt, không phải test giới hạn tín dụng (đó là việc của credit, ngoài scope T3-4).
DISBURSE_PROMPT = (
    f"Khách hàng {TEST_OWNER_ID} (khoản vay {TEST_LOAN_ID}) đã được duyệt hạn mức — giao Vận "
    f"hành thực hiện giải ngân {TEST_AMOUNT} đồng ngay cho khoản vay {TEST_LOAN_ID}, KHÔNG cần "
    f"thẩm định lại credit/legal"
)


def _restore_state(conv_id: str | None = None) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE loans SET status='active' WHERE loan_id=%s", (TEST_LOAN_ID,))
        if conv_id:
            cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
            cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv_id,))
            cur.execute("DELETE FROM tasks WHERE conv_id=%s", (conv_id,))
            cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
            cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()


async def _login_and_create_conv(client: AsyncClient, title: str) -> str:
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, f"login thất bại: {r.status_code} {r.text}"
    r2 = await client.post("/api/conversations", json={"title": title})
    assert r2.status_code == 201, f"tạo ca thất bại: {r2.status_code} {r2.text}"
    return r2.json()["id"]


async def _wait_for_approval_pending(client: AsyncClient, conv_id: str, timeout_s: float = 90.0) -> str:
    """Poll GET full-state tới khi thấy card approval xuất hiện (agent đã gọi disburse, bị
    chặn). Trả approval_id (card.approval_id — T3-1 export). timeout dài vì cần MAIN thật +
    Ops sub thật chạy tới lúc gọi tool gated (~30-60s theo kinh nghiệm gate S1/S2)."""
    elapsed = 0.0
    interval = 3.0
    while elapsed < timeout_s:
        r = await client.get(f"/api/conversations/{conv_id}")
        assert r.status_code == 200
        state = r.json()
        for c in state.get("cards", []):
            if c.get("type") == "approval":
                return c["approval_id"]
        await asyncio.sleep(interval)
        elapsed += interval
    pytest.fail(
        f"KHÔNG thấy card approval sau {timeout_s}s — nghi: (1) SKILL operations lệch (đã báo "
        f"architect trước khi chạy), (2) MAIN không dispatch Ops, (3) Ops không gọi disburse. "
        f"Kiểm tra state cuối: {state if 'state' in dir() else 'chưa lấy được'}"
    )


async def _wait_for_conversation_idle(client: AsyncClient, conv_id: str, timeout_s: float = 90.0) -> None:
    """Poll tới khi conversation.status='idle' — main đã kết thúc lượt resume."""
    elapsed = 0.0
    interval = 3.0
    while elapsed < timeout_s:
        r = await client.get(f"/api/conversations/{conv_id}")
        state = r.json()
        if state["conversation"]["status"] == "idle":
            return
        await asyncio.sleep(interval)
        elapsed += interval
    pytest.fail(f"conversation KHÔNG về idle sau {timeout_s}s resume — main có thể đang kẹt/lỗi")


@pytest.mark.asyncio
async def test_gate_s3_happy_path_approve_resume_disburse_real():
    """GATE S3 CHÍNH — chứng minh resume THẬT: agent gọi disburse → chặn → admin decide approved
    THẬT (HTTP POST) → main (LLM thật) resume → tự dispatch Ops → Ops gọi lại disburse → wrapper
    claim → loans.status='disbursed'. Đây là ca live SDK, có thể mất 60-120s (2 lượt SDK: lượt
    đầu Ops gọi disburse bị chặn, lượt resume Ops gọi lại disburse thành công)."""
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s3-happy-path")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": DISBURSE_PROMPT},
                )
                assert r.status_code == 202

                # BƯỚC 1: agent gọi disburse lần đầu → phanh CHẶN → card approval xuất hiện
                approval_id = await _wait_for_approval_pending(client, conv_id)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (TEST_LOAN_ID,))
                    loan_status_before = cur.fetchone()[0]
                finally:
                    conn.close()
                assert loan_status_before == "active", (
                    f"TRƯỚC duyệt, loans.status PHẢI nguyên (chưa disburse) — thấy {loan_status_before}"
                )

                # BƯỚC 2: admin decide approved THẬT qua API (không mock)
                r_decide = await client.post(
                    f"/api/approvals/{approval_id}/decide",
                    json={"decision": "approved"},
                )
                assert r_decide.status_code == 200, f"decide phải 200: {r_decide.status_code} {r_decide.text}"
                assert r_decide.json()["status"] == "approved"

                # BƯỚC 3: chờ RESUME THẬT — main tự dispatch Ops, Ops gọi lại disburse
                await _wait_for_conversation_idle(client, conv_id, timeout_s=90.0)

                # Lấy TOÀN BỘ messages+tasks TRƯỚC khi assert — nếu FAIL, in ra để điều tra
                # (bài học lần trước: cleanup vô điều kiện trong finally đã xoá mất bằng chứng
                # ngay khi assert raise, không kịp đọc transcript main resume làm gì).
                r_state = await client.get(f"/api/conversations/{conv_id}")
                full_state = r_state.json()

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (TEST_LOAN_ID,))
                    loan_status_after = cur.fetchone()[0]
                    assert loan_status_after == "disbursed", (
                        f"SAU duyệt + resume, loans.status PHẢI 'disbursed' — thấy '{loan_status_after}'. "
                        f"Đây là điểm CHƯA AI CHỨNG MINH (T3-2 test mock resume) — FAIL ở đây nghĩa là "
                        f"main không tự dispatch Ops HOẶC Ops không gọi lại disburse đúng cách. "
                        f"conv_id={conv_id} (GIỮ LẠI, không xoá — tra tay: SELECT sender,content FROM "
                        f"messages WHERE conv_id='{conv_id}' ORDER BY ts). "
                        f"Messages cuối: {[m['content'][:300] for m in full_state.get('messages', [])[-3:]]}"
                    )

                    cur.execute(
                        "SELECT status, receipt FROM approvals WHERE id=%s",
                        (approval_id,),
                    )
                    approval_row = cur.fetchone()
                    assert approval_row[0] == "used", f"phiếu phải 'used' sau resume+claim: {approval_row[0]}"
                    assert approval_row[1] is not None, "receipt phải lưu sau khi disburse thật chạy"
                finally:
                    conn.close()
                # Chỉ dọn conv khi TỚI ĐƯỢC ĐÂY (mọi assert trên đã pass) — FAIL ở trên thì
                # except/raise nhảy thẳng ra ngoài, conv_id KHÔNG bị xoá, giữ cho điều tra tay.
                _restore_state(conv_id)
    except AssertionError:
        raise  # giữ nguyên conv_id trong DB — KHÔNG cleanup khi fail (bằng chứng điều tra)
    finally:
        if conv_id is None:
            _restore_state()


@pytest.mark.asyncio
async def test_gate_s3_reject_path_no_disburse():
    """Nhánh reject: decide rejected → main được đánh thức, báo user từ chối — loans.status
    KHÔNG đổi (KHÔNG có double-check nào cho phép Ops gọi lại disburse sau reject)."""
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s3-reject-path")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": DISBURSE_PROMPT},
                )
                assert r.status_code == 202

                approval_id = await _wait_for_approval_pending(client, conv_id)

                r_decide = await client.post(
                    f"/api/approvals/{approval_id}/decide",
                    json={"decision": "rejected", "reason": "test reject — không đủ điều kiện"},
                )
                assert r_decide.status_code == 200
                assert r_decide.json()["status"] == "rejected"

                await _wait_for_conversation_idle(client, conv_id, timeout_s=90.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (TEST_LOAN_ID,))
                    assert cur.fetchone()[0] == "active", "reject → loans.status KHÔNG được đổi"

                    cur.execute("SELECT status, receipt FROM approvals WHERE id=%s", (approval_id,))
                    row = cur.fetchone()
                    assert row[0] == "rejected"
                    assert row[1] is None, "reject → KHÔNG có receipt (chưa từng thực thi)"
                finally:
                    conn.close()
                # Chỉ dọn khi TỚI ĐƯỢC ĐÂY (mọi assert trên đã pass) — bài học từ happy-path
                # (evidence-preserving cleanup): FAIL ở trên nhảy thẳng ra except, KHÔNG xoá conv.
                _restore_state(conv_id)
    except AssertionError:
        raise  # giữ nguyên conv_id trong DB — KHÔNG cleanup khi fail (bằng chứng điều tra)
    finally:
        if conv_id is None:
            _restore_state()


@pytest.mark.asyncio
async def test_gate_s3_decide_twice_returns_409_no_double_wake():
    """Defensive (đã T3-2 unit test mock, verify lại qua đường thật + kèm resume thật lần 1
    không bị đánh thức đôi): decide approved 2 lần liên tiếp → lần 2 = 409, chỉ 1 lần resume."""
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s3-decide-twice")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": DISBURSE_PROMPT},
                )
                assert r.status_code == 202
                approval_id = await _wait_for_approval_pending(client, conv_id)

                r1 = await client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
                assert r1.status_code == 200

                r2 = await client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
                assert r2.status_code == 409
                body = r2.json()
                assert body["code"] == "approval_already_decided"

                await _wait_for_conversation_idle(client, conv_id, timeout_s=90.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (TEST_LOAN_ID,))
                    assert cur.fetchone()[0] == "disbursed"
                    cur.execute(
                        "SELECT count(*) FROM approvals WHERE conv_id=%s AND status='used'",
                        (conv_id,),
                    )
                    assert cur.fetchone()[0] == 1, "chỉ đúng 1 phiếu used dù decide 2 lần"
                finally:
                    conn.close()
                # Chỉ dọn khi TỚI ĐƯỢC ĐÂY (mọi assert trên đã pass) — evidence-preserving cleanup.
                _restore_state(conv_id)
    except AssertionError:
        raise  # giữ nguyên conv_id trong DB — KHÔNG cleanup khi fail (bằng chứng điều tra)
    finally:
        if conv_id is None:
            _restore_state()
