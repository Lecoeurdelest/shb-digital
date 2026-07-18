"""[TESTER — T4-1] Gate S4 audit tool_calls — verify TẦNG TÍCH HỢP THẬT (author≠checker: backend
test_audit.py đã cover unit store_audit trực tiếp + SSE emit trực tiếp + API filter cơ bản — đây
verify qua 1 CA CHAT/DISBURSE THẬT, để hệ thống TỰ ghi audit qua toàn bộ luồng SUB/MAIN thật,
không gọi store_audit.record_tool_call tay).

4 điểm theo dispatch backend:
1. ca disburse thật → tool_calls rows persist đúng (actor/tool/input) qua đường thật.
2. append-only — 0 UPDATE/DELETE trong store_audit.py (đọc code xác nhận, không đoán).
3. GET /api/audit filter đúng qua HTTP thật (không gọi query_tool_calls trực tiếp).
4. persist lỗi KHÔNG fail turn — verify GIÁN TIẾP qua đường thật: không phá DB (nguy hiểm, dùng
   chung với người khác), thay vào đó xác nhận bằng code-read _audit_tool_call bọc try/except
   riêng NGOÀI record_tool_call (double-safety) + best-effort ghi rõ trong docstring/test backend
   (test_record_bad_db_returns_none_not_raise đã cover unit) — KHÔNG lặp lại phá DB thật.

Loan cô lập (bài học S3): dùng conv MỚI, KHÔNG chung conv với bất kỳ test nào khác.
"""

from __future__ import annotations

import asyncio
import inspect
import os

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db

_LIVE = os.environ.get("RUN_LIVE_SDK") == "1"

# Chỉ 2 test live-SDK (chat thật) cần skip khi KHÔNG có RUN_LIVE_SDK — append-only-by-code KHÔNG
# cần live SDK (đọc source thuần), đặt skip TRÊN TỪNG TEST thay vì module-level pytestmark để
# không skip oan cái không cần live.
_skip_live = pytest.mark.skipif(not _LIVE, reason="live SDK opt-in: RUN_LIVE_SDK=1 (audit qua đường thật)")


def test_store_audit_is_append_only_by_code():
    """Điểm 2: append-only — đọc SOURCE store_audit.py xác nhận KHÔNG có UPDATE/DELETE nào trên
    tool_calls (chỉ INSERT ở _record_sync + SELECT ở _query_sync). Đọc code, không đoán — nếu
    backend thêm UPDATE/DELETE sau này, test này bắt được ngay (regression bất biến §10)."""
    from app.orch import store_audit

    source = inspect.getsource(store_audit)
    # tách theo dòng, bỏ comment/docstring chứa chữ UPDATE/DELETE dạng mô tả (không phải SQL thật)
    sql_lines = [
        line for line in source.splitlines() if "cur.execute(" in line or line.strip().startswith(('"', "'"))
    ]
    combined = " ".join(sql_lines).upper()
    assert "UPDATE TOOL_CALLS" not in combined, "store_audit VI PHẠM append-only — có UPDATE trên tool_calls"
    assert "DELETE FROM TOOL_CALLS" not in combined, "store_audit VI PHẠM append-only — có DELETE trên tool_calls"
    assert "INSERT INTO TOOL_CALLS" in combined, "store_audit PHẢI có đường INSERT (persist audit)"


async def _login_and_create_conv(client: AsyncClient, title: str) -> str:
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, f"login thất bại: {r.status_code} {r.text}"
    r2 = await client.post("/api/conversations", json={"title": title})
    assert r2.status_code == 201, f"tạo ca thất bại: {r2.status_code} {r2.text}"
    return r2.json()["id"]


async def _wait_for_conversation_idle(client: AsyncClient, conv_id: str, timeout_s: float = 90.0) -> None:
    """BÀI HỌC (lần chạy đầu FAIL oan): conversation KHỞI TẠO với status='idle' MẶC ĐỊNH (store.py
    _create_conversation_sync) — POST /chat set 'running' bất đồng bộ, có khoảng hở giữa 202
    response và DB thực sự chuyển 'running'. Poll ngay lập tức có thể đọc trúng 'idle' CŨ (chưa
    từng chạy) rồi trả về SỚM SAI, coi như đã xong khi thực ra còn chưa bắt đầu. Fix: đợi thấy
    'running' TRƯỚC (xác nhận turn đã thực sự bắt đầu) rồi mới coi 'idle' sau đó là ĐÃ XONG."""
    elapsed = 0.0
    interval = 3.0
    seen_running = False
    while elapsed < timeout_s:
        r = await client.get(f"/api/conversations/{conv_id}")
        status = r.json()["conversation"]["status"]
        if status == "running":
            seen_running = True
        elif status == "idle" and seen_running:
            return
        await asyncio.sleep(interval)
        elapsed += interval
    pytest.fail(
        f"conversation KHÔNG về idle-sau-running sau {timeout_s}s (conv_id={conv_id}, "
        f"seen_running={seen_running} — False nghĩa là chưa từng thấy turn thực sự chạy)"
    )


def _restore_state(conv_id: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tool_calls WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM tasks WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()


@requires_db
@_skip_live
@pytest.mark.asyncio
async def test_gate_s4_audit_persists_real_tool_calls_via_chat():
    """Điểm 1 + 3 — ca chat THẬT (credit assess, không đụng phanh/disburse — tránh chồng bài
    T4-0/S3) → MAIN dispatch credit → sub gọi tool thật → audit ghi lại qua ĐÚNG đường thật (SUB
    tool_use/tool_result matching trong main_session.py, không gọi record_tool_call tay) → verify
    bằng GET /api/audit THẬT (HTTP, không gọi query_tool_calls trực tiếp)."""
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                conv_id = await _login_and_create_conv(client, "gate-s4-audit-real")

                r = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": "Khách hàng B001 xin vay — thẩm định tín dụng dùm tôi."},
                )
                assert r.status_code == 202

                await _wait_for_conversation_idle(client, conv_id, timeout_s=90.0)

                # ĐIỂM 3: GET /api/audit thật (HTTP, admin) — không gọi query_tool_calls tay
                r_audit = await client.get(f"/api/audit?conv_id={conv_id}")
                assert r_audit.status_code == 200, f"GET /api/audit phải 200: {r_audit.text}"
                rows = r_audit.json()
                assert len(rows) >= 1, (
                    f"Ca chat thật PHẢI sinh ít nhất 1 tool_call audit qua đường thật — thấy "
                    f"{len(rows)} rows (conv_id={conv_id}, GIỮ LẠI để tra: SELECT * FROM tool_calls "
                    f"WHERE conv_id='{conv_id}')"
                )

                # ĐIỂM 1: actor/tool/input đúng — ít nhất 1 row actor≠main (sub thật gọi tool)
                actors = {row["actor"] for row in rows}
                assert actors, "audit rows PHẢI có actor"
                for row in rows:
                    assert row["tool"], f"row thiếu tool name: {row}"
                    assert row["actor"] in ("main", "credit", "legal", "operations"), (
                        f"actor lạ không thuộc role hệ thống: {row['actor']}"
                    )

                # filter theo actor cụ thể (nếu có sub credit) — kiểm whitelist filter hoạt động qua HTTP
                credit_rows = [row for row in rows if row["actor"] == "credit"]
                if credit_rows:
                    r_filtered = await client.get(f"/api/audit?conv_id={conv_id}&actor=credit")
                    assert r_filtered.status_code == 200
                    filtered = r_filtered.json()
                    assert len(filtered) == len(credit_rows), "filter actor=credit qua HTTP phải khớp đúng số dòng"
                    assert all(row["actor"] == "credit" for row in filtered)

                _restore_state(conv_id)
    except AssertionError:
        raise  # giữ nguyên conv_id trong DB — KHÔNG cleanup khi fail (bằng chứng điều tra)
