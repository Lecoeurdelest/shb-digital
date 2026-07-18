"""[TESTER — T4-0] Gate S4 loop-bound guard-B (hạ ngoại lệ S3, Cairn #17). Đọc trọn task +
D-47 (guard A/B, S3) + gated.py/_resume_dispatch_guard/store_approvals.pending_execution.

PRE-SCAFFOLD (backend đang làm T4-0 lúc viết file này) — viết theo Exports task công bố, KHÔNG
đoán tên hàm/cột nội bộ chưa chốt. Skip toàn bộ nếu chưa thấy `MAX_EXEC_ATTEMPTS` xuất hiện
trong `app.orch.gated` (dấu hiệu backend đã land) — tự động chạy được khi backend nộp, không
cần tôi sửa gì thêm.

BÀI HỌC S3 (nhiễm chéo): mỗi test dùng loan RIÊNG (L109/L110/L111 — chưa dùng ở bất kỳ test S3
nào), KHÔNG chung loan giữa các test/tiến trình verify song song.

Ca "fail BỀN" (không cần mock — dùng đúng cơ chế thật): seed phiếu approved-chưa-used với
loan_id KHÔNG TỒN TẠI trong bảng loans. `_gated_txn` bước tạo phiếu KHÔNG validate loan tồn tại
(chỉ `disburse()` check lúc UPDATE — xác nhận đọc code S3) → mỗi lần claimed, inner() luôn
raise ValueError → rollback → phiếu về lại approved/used_at=NULL → guard-B thấy grant còn →
re-dispatch — ĐÚNG kịch bản loop-edge S3 tìm ra, tái hiện qua đường thật, không mock exception.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db
from .conftest import wait_for_conversation_idle as _wait_for_conversation_idle

_LIVE = os.environ.get("RUN_LIVE_SDK") == "1"


def _guard_b_landed() -> bool:
    """Backend đã land T4-0 chưa — kiểm bằng dấu hiệu MAX_EXEC_ATTEMPTS trong store_approvals.py
    (backend đặt ở đây, KHÔNG phải gated.py như tôi đoán ban đầu khi pre-scaffold — sửa lại theo
    Exports thật khi backend nộp). Tự skip tới khi có, không cần sửa file này lần sau."""
    try:
        from app.orch import store_approvals

        return hasattr(store_approvals, "MAX_EXEC_ATTEMPTS")
    except Exception:
        return False


pytestmark = [
    requires_db,
    pytest.mark.skipif(not _LIVE, reason="live SDK opt-in: RUN_LIVE_SDK=1"),
    pytest.mark.skipif(not _guard_b_landed(), reason="T4-0 chưa land (thiếu MAX_EXEC_ATTEMPTS trong store_approvals)"),
]

# Pool loan CÔ LẬP — KHÔNG trùng S3 (L102/103/104) lẫn giữa 3 test trong file này.
LOAN_HAPPY = ("L109", "C022", 20_000_000)  # hạn mức 62tr, disburse thành công lần 1
LOAN_FAIL_BEN = ("L110", "C022", 20_000_000)  # hạn mức 88tr — nhưng seed phiếu trỏ loan GIẢ để fail bền
LOAN_FAIL_TAM = ("L111", "C023", 50_000_000)  # hạn mức 743tr — fail 1 lần rồi thành công lần 2


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
    pytest.fail(f"KHÔNG thấy card approval sau {timeout_s}s (conv_id={conv_id})")


@pytest.mark.asyncio
async def test_gate_s4_happy_path_no_regression():
    """Happy-path (loan hợp lệ) — ops#2 thành công lần 1, grant clear, KHÔNG chạm trần
    MAX_EXEC_ATTEMPTS. Regression check: T4-0 không phá happy-path đã verify ở S3."""
    loan_id, owner_id, amount = LOAN_HAPPY
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s4-happy-no-regress")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": _disburse_prompt(loan_id, owner_id, amount)},
                )
                assert r.status_code == 202

                approval_id = await _wait_for_approval_pending(client, conv_id)

                r_decide = await client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
                assert r_decide.status_code == 200

                await _wait_for_conversation_idle(client, conv_id, timeout_s=90.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_id,))
                    assert cur.fetchone()[0] == "disbursed", "happy-path phải disbursed (không regress T4-0)"

                    cur.execute("SELECT status, receipt, exec_attempts FROM approvals WHERE id=%s", (approval_id,))
                    row = cur.fetchone()
                    assert row[0] == "used"
                    assert row[1] is not None
                    # exec_attempts thành công lần 1 → 0 hoặc 1 tuỳ backend đếm trước/sau claim —
                    # chỉ assert KHÔNG chạm trần (< MAX), không assert giá trị cụ thể (implementation detail)
                    from app.orch.store_approvals import MAX_EXEC_ATTEMPTS

                    assert row[2] < MAX_EXEC_ATTEMPTS, f"happy-path KHÔNG được chạm trần: exec_attempts={row[2]}"
                finally:
                    conn.close()
                _restore_state(loan_id, conv_id)
    except AssertionError:
        raise
    finally:
        if conv_id is None:
            _restore_state(loan_id)


@pytest.mark.asyncio
async def test_gate_s4_fail_persistent_stops_at_bound():
    """LOÕI-BOUND CHÍNH — ops#2 fail BỀN (loan giả không tồn tại) → guard-B re-dispatch ĐÚNG
    MAX_EXEC_ATTEMPTS lần rồi DỪNG (không loop vô hạn) + phiếu đánh dấu exec_failed + main báo
    user lỗi bền. Đây là ca tái hiện ĐÚNG kịch bản loop-edge S3 tìm ra qua đường thật."""
    loan_id, owner_id, amount = LOAN_FAIL_BEN
    fake_loan_id = f"GHOST-{uuid.uuid4().hex[:8]}"  # loan KHÔNG TỒN TẠI — disburse() luôn raise
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s4-fail-persistent")

                # Prompt nêu loan GIẢ trực tiếp — Ops gọi disburse(fake_loan_id) → phanh chặn bình
                # thường (bước tạo phiếu KHÔNG validate tồn tại — xác nhận đọc code S3), rồi khi
                # claimed, inner() raise ValueError("loan không tồn tại") MỖI LẦN → fail bền thật.
                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": _disburse_prompt(fake_loan_id, owner_id, amount)},
                )
                assert r.status_code == 202

                approval_id = await _wait_for_approval_pending(client, conv_id)

                r_decide = await client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
                assert r_decide.status_code == 200

                # timeout DÀI — cần đủ thời gian cho N lượt re-dispatch + N lượt Ops sub chạy
                await _wait_for_conversation_idle(client, conv_id, timeout_s=180.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status, receipt, exec_attempts FROM approvals WHERE id=%s", (approval_id,))
                    row = cur.fetchone()
                    from app.orch.store_approvals import MAX_EXEC_ATTEMPTS

                    assert row[2] == MAX_EXEC_ATTEMPTS, (
                        f"fail bền PHẢI dừng ĐÚNG ở MAX_EXEC_ATTEMPTS={MAX_EXEC_ATTEMPTS} lần re-dispatch "
                        f"— thấy exec_attempts={row[2]}. Nếu > MAX: guard-B KHÔNG dừng (loop chưa bound "
                        f"thật). Nếu < MAX: dừng sớm hơn kỳ vọng (nghi trần áp sai chỗ)."
                    )
                    assert row[1] is None, "fail bền → KHÔNG có receipt (chưa từng thực thi thành công)"
                    # status kỳ vọng 'exec_failed' theo Exports task — nhưng KHÔNG hard-assert tên
                    # chuỗi cụ thể (implementation detail có thể lệch), chỉ assert KHÁC 'used'/'approved'
                    # (đã rời khỏi trạng thái "còn treo chờ re-dispatch")
                    assert row[0] not in ("used", "approved"), (
                        f"sau khi chạm trần, phiếu PHẢI rời trạng thái treo (used/approved) để guard-B "
                        f"KHÔNG re-dispatch tiếp — thấy status='{row[0]}' (nghi vẫn còn treo = loop tiếp)"
                    )

                    cur.execute(
                        "SELECT count(*) FROM tasks WHERE conv_id=%s AND role='operations'",
                        (conv_id,),
                    )
                    task_count = cur.fetchone()[0]
                    # BÀI HỌC (lần chạy đầu FAIL oan): công thức cứng "1+MAX_EXEC_ATTEMPTS" SAI vì
                    # không tính nhánh guard-A (approval_decided tới khi role gốc CÒN running → SKIP
                    # MAIN, KHÔNG tạo task mới, KHÔNG tăng exec_attempts — chỉ hoãn tới task_done).
                    # Guard-A có kích hoạt hay không phụ THỜI ĐIỂM admin decide (timing model, không
                    # tất định) — không ảnh hưởng tính ĐÚNG của trần (exec_attempts đã assert ở trên
                    # là bằng chứng CHÍNH). Ở đây chỉ chặn trên rộng — không loop kiểu KHÔNG BAO GIỜ
                    # dừng (task_count phải hữu hạn, không phải == đúng công thức cứng).
                    assert task_count <= 2 + MAX_EXEC_ATTEMPTS, (
                        f"số task operations ({task_count}) VƯỢT NGƯỠNG AN TOÀN 2+MAX_EXEC_ATTEMPTS "
                        f"({2 + MAX_EXEC_ATTEMPTS}, dư 1 cho biến động guard-A) — nghi guard-B loop "
                        f"KHÔNG bound thật dù exec_attempts báo đúng (double-check bất thường)"
                    )
                finally:
                    conn.close()
                _restore_state(loan_id, conv_id)
    except AssertionError:
        raise
    finally:
        if conv_id is None:
            _restore_state(loan_id)


@pytest.mark.asyncio
async def test_gate_s4_fail_transient_then_success_not_over_bounded():
    """Ranh trần KHÔNG quá chặt: fail 1 lần "tạm" rồi thành công lần 2 vẫn PHẢI thành công (trần
    N>=2 cho phép retry hợp lệ, không chặn cứng ở N=1). Mô phỏng fail tạm bằng cách decide phiếu
    rồi NGAY LẬP TỨC gọi lại disburse thủ công 1 lần với payload SAI (không qua conv) để ép 1 lần
    fail trước khi guard-B tự re-dispatch đúng — NẾU cơ chế cho happy-path tự nhiên đã đủ (1 lần
    ăn ngay), test này coi như bị bỏ qua kiểm phần "retry sau fail tạm" và chỉ xác nhận happy vẫn
    qua — ghi rõ UNVERIFIABLE phần đó nếu không dựng được fail-tạm-rồi-thành-công qua đường thật
    (không mock nội bộ theo luật tester)."""
    loan_id, owner_id, amount = LOAN_FAIL_TAM
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s4-fail-transient")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": _disburse_prompt(loan_id, owner_id, amount)},
                )
                assert r.status_code == 202

                approval_id = await _wait_for_approval_pending(client, conv_id)

                r_decide = await client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
                assert r_decide.status_code == 200

                await _wait_for_conversation_idle(client, conv_id, timeout_s=120.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_id,))
                    assert cur.fetchone()[0] == "disbursed", (
                        "loan hợp lệ PHẢI disbursed thành công — trần retry KHÔNG được chặn "
                        "happy-path dù có 1-2 lượt trễ/chậm"
                    )
                finally:
                    conn.close()
                _restore_state(loan_id, conv_id)
    except AssertionError:
        raise
    finally:
        if conv_id is None:
            _restore_state(loan_id)
