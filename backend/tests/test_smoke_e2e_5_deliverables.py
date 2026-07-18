"""[TESTER] Smoke e2e 5-deliverable LIỀN MẠCH — regression demo vĩnh viễn (architect dispatch
sau S6, 18/7). 1 test live-SDK opt-in (RUN_LIVE_SDK=1), chạy trên DB sạch (reset_demo trước),
đi qua CẢ 5 deliverable của đề #132 THEO ĐÚNG THỨ TỰ MỘT LƯỢT, PASS 1 lần = bằng chứng liền-mạch
tất định, chạy lại được trước mỗi lần demo thật (Đà Nẵng 17-19/7).

Ghép từ pattern đã có (author≠checker vẫn giữ — file này KHÔNG gọi tắt nội bộ, luôn qua HTTP
thật/DB thật, không mock):
  - conftest.wait_for_conversation_idle (bài học idle-lượt-đầu, S3/S4)
  - test_gate_s3_e2e_tester.py: _login_and_create_conv, _wait_for_approval_pending, decide thật
  - test_gate_s3_gated_disburse_tester.py: cleanup approvals+cards (không chỉ approvals)
  - test_gate_s4_audit_tester.py: GET /api/audit thật
  - test_compare.py: POST /api/compare live, partial-ok khi multi timeout

5 deliverable theo dispatch:
  (1) ca khảo sát fan-out (B001/COL06, đủ mục đích+tài sản theo N2 — Legal không dừng hỏi) →
      settled + cards>0
  (2a) disburse <500tr → auto-approve, decided_by='auto-rule', status='used' NGAY (không phiếu
       chờ)
  (2b) disburse ≥500tr → phiếu pending → admin decide approved THẬT → resume → disbursed
  (3) audit: GET /api/audit?conv_id=... trả rows thật của (1), actor/tool hợp lệ
  (4) compare: POST /api/compare 200, single có text, multi có nguồn HOẶC partial (không 500,
      không treo — đây chính là ca finding /api/compare đã fix S5, verify lại luôn ở đây)

Loan CÔ LẬP (bài học nhiễm chéo 18/7 — mỗi file/mỗi test 1 loan riêng, KHÔNG trùng loan đang
dùng ở test khác đã biết: L001-L007, L102-L104 đã có chủ). Dùng L109 (auto-approve, principal
62tr < 500tr ngưỡng) + L111 (cần duyệt, principal 743tr ≥ 500tr ngưỡng) — 2 loan RÀNH RIÊNG cho
smoke này, chưa thấy conflict khi grep toàn bộ tests/ tại thời điểm viết.

Timeout RỘNG RÃI theo yêu cầu dispatch (mỗi bước có thể mất 30-120s do LLM thật + fan-out 3 sub).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db

_LIVE = os.environ.get("RUN_LIVE_SDK") == "1"

pytestmark = [
    requires_db,
    pytest.mark.skipif(not _LIVE, reason="live SDK opt-in: RUN_LIVE_SDK=1 (5 deliverable cần MAIN+sub thật)"),
]

# Loan CÔ LẬP riêng cho smoke này — KHÔNG trùng L001-L007 (gate S2/S3 khác), L102-L104 (gate S3
# tester). Seed thật (app/db/seed_from_lab hoặc lab_config): L109/C022 62tr, L111/C023 743tr.
LOAN_AUTO = ("L109", "C022", 300_000_000)  # < 500tr ngưỡng D-52 → auto-rule
LOAN_MANUAL = ("L111", "C023", 700_000_000)  # >= 500tr ngưỡng → phiếu chờ người

# Câu khảo sát fan-out — ĐỦ mục đích + tài sản ngay (N2 luật #6 "đủ thông tin → check NGAY,
# đừng hỏi thừa") để Legal KHÔNG dừng hỏi lại, giữ smoke chạy 1 lượt không cần trả lời tiếp.
_SURVEY_PROMPT = (
    "Công ty TNHH Cơ khí Xưởng X (mã B001) muốn vay 5 tỷ MỞ RỘNG SẢN XUẤT, thế chấp nhà xưởng "
    "(COL06) — khảo sát tổng quan nhanh: sức khoẻ tín dụng, pháp lý hồ sơ thế chấp, gói vay phù "
    "hợp. Chưa phải hồ sơ chính thức."
)


def _disburse_prompt(loan_id: str, owner_id: str, amount: int) -> str:
    return (
        f"Khách hàng {owner_id} (khoản vay {loan_id}) đã được duyệt hạn mức — giao Vận hành thực "
        f"hiện giải ngân {amount} đồng ngay cho khoản vay {loan_id}, KHÔNG cần thẩm định lại credit/legal"
    )


def _reset_demo() -> None:
    """DB sạch trước smoke — dùng chính script demo dùng (app.db.reset_demo), KHÔNG tự viết lại
    logic reset (single source of truth, tránh lệch với demo thật)."""
    result = subprocess.run(
        [sys.executable, "-m", "app.db.reset_demo"],
        cwd=str(__file__).rsplit("/tests/", 1)[0],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"reset_demo thất bại: {result.stdout}\n{result.stderr}"


def _restore_loans(loan_ids: list[str]) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        for loan_id in loan_ids:
            cur.execute("UPDATE loans SET status='active' WHERE loan_id=%s", (loan_id,))
        conn.commit()
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


async def _login_and_create_conv(client: AsyncClient, title: str) -> str:
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, f"login thất bại: {r.status_code} {r.text}"
    r2 = await client.post("/api/conversations", json={"title": title})
    assert r2.status_code == 201, f"tạo ca thất bại: {r2.status_code} {r2.text}"
    return r2.json()["id"]


_TERMINAL_TASK_STATUS = {"done", "failed", "timeout"}


async def _wait_for_settled(client: AsyncClient, conv_id: str, timeout_s: float = 180.0) -> dict:
    """Chờ MẠNH HƠN `conftest.wait_for_conversation_idle` cho ca FAN-OUT nhiều sub — bài học
    smoke lần chạy đầu (FAIL oan): MAIN dispatch xong 3 sub → conv có thể THOÁNG QUA 'idle' giữa
    lượt dispatch và lượt sub thực sự chạy (message "Đã giao việc cho 3 chuyên gia..." tại thời
    điểm conv.status vừa kịp 'idle' 1 nhịp) — `wait_for_conversation_idle` chỉ cần thấy 'running'
    1 LẦN rồi coi 'idle' kế tiếp là xong, không đủ mạnh khi có nhiều nhịp running/idle xen kẽ.
    Hệ quả quan sát được: test thoát context sớm → asyncio executor shutdown → 3 sub đang chạy
    ngầm bị đánh 'failed' reason='user hủy' (không phải bug nghiệp vụ, là do wait sai).

    Điều kiện SETTLED thật (khớp cách tôi tự poll tay trong rehearsal T5-4): conv.status=='idle'
    VÀ có ≥1 task VÀ TẤT CẢ task đều ở trạng thái CHUNG CUỘC (done/failed/timeout) — không còn
    task nào queued/running. Đọc `tasks` field từ chính GET /api/conversations/{id} (qua HTTP
    thật, không gọi tắt store.task_board nội bộ — giữ nguyên tắc author≠checker)."""
    elapsed = 0.0
    interval = 3.0
    state: dict | None = None
    while elapsed < timeout_s:
        r = await client.get(f"/api/conversations/{conv_id}")
        assert r.status_code == 200
        state = r.json()
        conv_status = state.get("conversation", {}).get("status")
        tasks = state.get("tasks", [])
        if conv_status == "idle" and tasks and all(t.get("status") in _TERMINAL_TASK_STATUS for t in tasks):
            return state
        await asyncio.sleep(interval)
        elapsed += interval
    pytest.fail(
        f"conversation KHÔNG settled (idle + mọi task chung-cuộc) sau {timeout_s}s — conv_id={conv_id}. "
        f"state cuối: conv_status={state.get('conversation', {}).get('status') if state else '?'}, "
        f"tasks={[(t.get('role'), t.get('status')) for t in (state.get('tasks', []) if state else [])]}"
    )


async def _wait_for_approval_pending(client: AsyncClient, conv_id: str, timeout_s: float = 90.0) -> str:
    elapsed = 0.0
    interval = 3.0
    state: dict | None = None
    while elapsed < timeout_s:
        r = await client.get(f"/api/conversations/{conv_id}")
        assert r.status_code == 200
        state = r.json()
        for c in state.get("cards", []):
            if c.get("type") == "approval":
                return c["approval_id"]
        await asyncio.sleep(interval)
        elapsed += interval
    pytest.fail(f"KHÔNG thấy card approval sau {timeout_s}s — conv_id={conv_id}, state cuối: {state}")


@pytest.mark.asyncio
async def test_smoke_5_deliverables_liền_mạch():
    """Smoke e2e liền mạch — 5 deliverable 1 lượt, DB sạch, không mock, không gọi tắt nội bộ.
    FAIL ở deliverable nào → message rõ deliverable đó, conv_id liên quan GIỮ LẠI để điều tra
    (evidence-preserving, bài học S3)."""
    loan_auto_id, owner_auto, amount_auto = LOAN_AUTO
    loan_manual_id, owner_manual, amount_manual = LOAN_MANUAL

    _reset_demo()  # DB sạch — nguồn sự thật duy nhất, không tự viết lại logic reset

    conv_survey: str | None = None
    conv_auto: str | None = None
    conv_manual: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=180.0) as client:
                # ═══ DELIVERABLE (1): ca khảo sát fan-out — settled + cards>0 ═══
                conv_survey = await _login_and_create_conv(client, "smoke-d1-survey")
                r = await client.post(f"/api/conversations/{conv_survey}/chat", json={"content": _SURVEY_PROMPT})
                assert r.status_code == 202, f"[D1] gửi câu khảo sát phải 202: {r.status_code} {r.text}"

                state1 = await _wait_for_settled(client, conv_survey, timeout_s=180.0)
                cards1 = state1.get("cards", [])
                assert len(cards1) > 0, (
                    f"[D1] ca khảo sát fan-out PHẢI sinh ≥1 card (present từ credit/legal/products) — "
                    f"thấy 0 card. conv_id={conv_survey} (GIỮ LẠI điều tra). "
                    f"messages cuối: {[m['content'][:200] for m in state1.get('messages', [])[-3:]]}"
                )

                # ═══ DELIVERABLE (2a): disburse <500tr → auto-approve NGAY ═══
                conv_auto = await _login_and_create_conv(client, "smoke-d2a-auto-approve")
                r = await client.post(
                    f"/api/conversations/{conv_auto}/chat",
                    json={"content": _disburse_prompt(loan_auto_id, owner_auto, amount_auto)},
                )
                assert r.status_code == 202, f"[D2a] gửi disburse auto phải 202: {r.status_code} {r.text}"

                await _wait_for_settled(client, conv_auto, timeout_s=90.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_auto_id,))
                    row = cur.fetchone()
                    assert row is not None, f"[D2a] loan {loan_auto_id} không tồn tại trong seed"
                    assert row[0] == "disbursed", (
                        f"[D2a] disburse dưới ngưỡng PHẢI auto-approve → disbursed NGAY — thấy "
                        f"'{row[0]}'. conv_id={conv_auto} (GIỮ LẠI điều tra)."
                    )
                    cur.execute(
                        "SELECT status, decided_by FROM approvals WHERE conv_id=%s ORDER BY decided_at DESC LIMIT 1",
                        (conv_auto,),
                    )
                    appr_row = cur.fetchone()
                    assert appr_row is not None, f"[D2a] phải có approval row (dù auto) — conv_id={conv_auto}"
                    assert appr_row[0] == "used", f"[D2a] approval status phải 'used': {appr_row[0]}"
                    assert appr_row[1] == "auto-rule", (
                        f"[D2a] decided_by PHẢI 'auto-rule' (D-52 phanh phân tầng) — thấy '{appr_row[1]}'"
                    )
                finally:
                    conn.close()

                # ═══ DELIVERABLE (2b): disburse ≥500tr → phiếu chờ → decide → resume → disbursed ═══
                conv_manual = await _login_and_create_conv(client, "smoke-d2b-manual-approve")
                r = await client.post(
                    f"/api/conversations/{conv_manual}/chat",
                    json={"content": _disburse_prompt(loan_manual_id, owner_manual, amount_manual)},
                )
                assert r.status_code == 202, f"[D2b] gửi disburse manual phải 202: {r.status_code} {r.text}"

                approval_id = await _wait_for_approval_pending(client, conv_manual, timeout_s=90.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_manual_id,))
                    assert cur.fetchone()[0] == "active", (
                        f"[D2b] TRƯỚC duyệt, loans.status PHẢI nguyên — conv_id={conv_manual}"
                    )
                finally:
                    conn.close()

                r_decide = await client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
                assert r_decide.status_code == 200, f"[D2b] decide phải 200: {r_decide.status_code} {r_decide.text}"

                await _wait_for_settled(client, conv_manual, timeout_s=90.0)

                conn = psycopg2.connect(DATABASE_URL)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM loans WHERE loan_id=%s", (loan_manual_id,))
                    row = cur.fetchone()
                    assert row[0] == "disbursed", (
                        f"[D2b] SAU duyệt + resume, loans.status PHẢI 'disbursed' — thấy '{row[0]}'. "
                        f"conv_id={conv_manual} (GIỮ LẠI điều tra)."
                    )
                    cur.execute("SELECT status, receipt FROM approvals WHERE id=%s", (approval_id,))
                    appr_row = cur.fetchone()
                    assert appr_row[0] == "used", f"[D2b] phiếu phải 'used' sau resume: {appr_row[0]}"
                    assert appr_row[1] is not None, "[D2b] receipt phải lưu sau disburse thật"
                finally:
                    conn.close()

                # ═══ DELIVERABLE (3): audit — GET /api/audit trả rows thật của ca khảo sát (D1) ═══
                r_audit = await client.get(f"/api/audit?conv_id={conv_survey}")
                assert r_audit.status_code == 200, f"[D3] GET /api/audit phải 200: {r_audit.text}"
                audit_rows = r_audit.json()
                assert len(audit_rows) >= 1, (
                    f"[D3] ca khảo sát fan-out PHẢI sinh ≥1 audit row qua đường thật — thấy "
                    f"{len(audit_rows)}. conv_id={conv_survey}"
                )
                for row in audit_rows:
                    assert row["tool"], f"[D3] audit row thiếu tool name: {row}"
                    assert row["actor"] in ("main", "credit", "legal", "operations", "products"), (
                        f"[D3] actor lạ không thuộc role hệ thống: {row['actor']}"
                    )

                # ═══ DELIVERABLE (4): compare — POST /api/compare 200, không treo, partial-ok ═══
                r_compare = await client.post(
                    "/api/compare",
                    json={"question": "Khách C001 vay 500 triệu được không?"},
                )
                assert r_compare.status_code == 200, (
                    f"[D4] POST /api/compare PHẢI 200 (không treo, fix S5 _SINGLE_TIMEOUT_S) — "
                    f"thấy {r_compare.status_code}: {r_compare.text}"
                )
                compare_body = r_compare.json()
                assert compare_body.get("single", {}).get("text"), (
                    "[D4] single phải có text (dù timeout cũng có text báo)"
                )
                multi = compare_body.get("multi", {})
                assert multi.get("timeout") or multi.get("tool_calls", 0) > 0, (
                    f"[D4] multi PHẢI có nguồn (tool_calls>0) HOẶC partial-timeout rõ ràng — thấy: {multi}"
                )

                # Tới được đây = CẢ 5 deliverable PASS liền mạch → dọn sạch (evidence không cần giữ)
                _restore_loans([loan_auto_id, loan_manual_id])
                for cid in (conv_survey, conv_auto, conv_manual):
                    if cid:
                        _cleanup_conv(cid)
    except AssertionError:
        raise  # giữ nguyên mọi conv_id trong DB — KHÔNG cleanup khi fail (bằng chứng điều tra, §5)
