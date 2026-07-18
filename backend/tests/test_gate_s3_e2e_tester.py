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
không gọi disburse → nghi ngay SKILL lệch trước khi nghi cơ chế (§6b thứ tự nghi vấn).

BÀI HỌC NHIỄM CHÉO (18/7, sau race-fix commit cd1bd24): 3 người (tester/architect/backend) từng
CÙNG chạy live-SDK trên CHUNG loan L007 gần như đồng thời → `_restore_state` cũ reset
`loans.status` theo loan_id TOÀN CỤC (không theo conv_id) → cleanup của 1 tiến trình ghi đè MẤT
kết quả ĐÚNG của tiến trình khác đang chạy song song → trông giống "fail ngẫu nhiên" dù cơ chế
resume/guard hoàn toàn đúng (xác nhận qua transcript: receipt lưu đúng, task Ops gọi disburse
thật thành công, nhưng loans bị set lại 'active' SAU ĐÓ bởi lệnh reset khác). **Fix: mỗi test
dùng loan RIÊNG** (không chung TEST_LOAN_ID cho cả 3 test, không chung với loan người khác có
thể đang verify song song) — loại bỏ hẳn khả năng nhiễm chéo thay vì trông chờ "đừng chạy cùng
lúc" (kỷ luật quy trình dễ quên, cô lập bằng code mới bền)."""

from __future__ import annotations

import asyncio
import os

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db
from .conftest import wait_for_conversation_idle as _wait_for_conversation_idle

_LIVE = os.environ.get("RUN_LIVE_SDK") == "1"

pytestmark = [
    requires_db,
    pytest.mark.skipif(not _LIVE, reason="live SDK opt-in: RUN_LIVE_SDK=1 (resume cần MAIN thật quyết dispatch)"),
]

# Pool loan CÔ LẬP per-test (bài học nhiễm chéo 18/7) — mỗi test 1 loan RIÊNG, KHÔNG chung
# TEST_LOAN_ID nữa. amount luôn DƯỚI hạn mức (test cơ chế PHANH, không phải giới hạn tín dụng —
# việc của credit, ngoài scope T3-4). owner_id LUÔN nêu rõ trong prompt (N2 — bài học lần chạy
# đầu: thiếu owner_id → sub từ chối tự bịa, ĐÚNG hành vi, không phải bug).
LOAN_HAPPY = ("L102", "C002", 50_000_000)  # hạn mức 108tr
LOAN_REJECT = ("L103", "C009", 50_000_000)  # hạn mức 113tr
LOAN_DECIDE_TWICE = ("L104", "C010", 300_000_000)  # hạn mức 700tr


def _disburse_prompt(loan_id: str, owner_id: str, amount: int) -> str:
    return (
        f"Khách hàng {owner_id} (khoản vay {loan_id}) đã được duyệt hạn mức — giao Vận hành thực "
        f"hiện giải ngân {amount} đồng ngay cho khoản vay {loan_id}, KHÔNG cần thẩm định lại credit/legal"
    )


def _restore_state(loan_id: str, conv_id: str | None = None) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE loans SET status='active' WHERE loan_id=%s", (loan_id,))
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


@pytest.mark.asyncio
async def test_gate_s3_happy_path_approve_resume_disburse_real():
    """GATE S3 CHÍNH — chứng minh resume THẬT: agent gọi disburse → chặn → admin decide approved
    THẬT (HTTP POST) → main (LLM thật) resume → tự dispatch Ops → Ops gọi lại disburse → wrapper
    claim → loans.status='disbursed'. Đây là ca live SDK, có thể mất 60-120s (2 lượt SDK: lượt
    đầu Ops gọi disburse bị chặn, lượt resume Ops gọi lại disburse thành công)."""
    loan_id, owner_id, amount = LOAN_HAPPY
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s3-happy-path")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": _disburse_prompt(loan_id, owner_id, amount)},
                )
                assert r.status_code == 202

                # BƯỚC 1: agent gọi disburse lần đầu → phanh CHẶN → card approval xuất hiện
                approval_id = await _wait_for_approval_pending(client, conv_id)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_id,))
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
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_id,))
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
                _restore_state(loan_id, conv_id)
    except AssertionError:
        raise  # giữ nguyên conv_id trong DB — KHÔNG cleanup khi fail (bằng chứng điều tra)
    finally:
        if conv_id is None:
            _restore_state(loan_id)


@pytest.mark.asyncio
async def test_gate_s3_reject_path_no_disburse():
    """Nhánh reject: decide rejected → main được đánh thức, báo user từ chối — loans.status
    KHÔNG đổi (KHÔNG có double-check nào cho phép Ops gọi lại disburse sau reject)."""
    loan_id, owner_id, amount = LOAN_REJECT
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s3-reject-path")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": _disburse_prompt(loan_id, owner_id, amount)},
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
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_id,))
                    assert cur.fetchone()[0] == "active", "reject → loans.status KHÔNG được đổi"

                    cur.execute("SELECT status, receipt FROM approvals WHERE id=%s", (approval_id,))
                    row = cur.fetchone()
                    assert row[0] == "rejected"
                    assert row[1] is None, "reject → KHÔNG có receipt (chưa từng thực thi)"
                finally:
                    conn.close()
                # Chỉ dọn khi TỚI ĐƯỢC ĐÂY (mọi assert trên đã pass) — bài học từ happy-path
                # (evidence-preserving cleanup): FAIL ở trên nhảy thẳng ra except, KHÔNG xoá conv.
                _restore_state(loan_id, conv_id)
    except AssertionError:
        raise  # giữ nguyên conv_id trong DB — KHÔNG cleanup khi fail (bằng chứng điều tra)
    finally:
        if conv_id is None:
            _restore_state(loan_id)


@pytest.mark.asyncio
async def test_gate_s3_decide_twice_returns_409_no_double_wake():
    """Defensive (đã T3-2 unit test mock, verify lại qua đường thật + kèm resume thật lần 1
    không bị đánh thức đôi): decide approved 2 lần liên tiếp → lần 2 = 409, chỉ 1 lần resume."""
    loan_id, owner_id, amount = LOAN_DECIDE_TWICE
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s3-decide-twice")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": _disburse_prompt(loan_id, owner_id, amount)},
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
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_id,))
                    assert cur.fetchone()[0] == "disbursed"
                    cur.execute(
                        "SELECT count(*) FROM approvals WHERE conv_id=%s AND status='used'",
                        (conv_id,),
                    )
                    assert cur.fetchone()[0] == 1, "chỉ đúng 1 phiếu used dù decide 2 lần"
                finally:
                    conn.close()
                # Chỉ dọn khi TỚI ĐƯỢC ĐÂY (mọi assert trên đã pass) — evidence-preserving cleanup.
                _restore_state(loan_id, conv_id)
    except AssertionError:
        raise  # giữ nguyên conv_id trong DB — KHÔNG cleanup khi fail (bằng chứng điều tra)
    finally:
        if conv_id is None:
            _restore_state(loan_id)
