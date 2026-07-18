"""Prompt-building cho MAIN turn (S8 — tách khỏi main_session.py để <400 LOC). Chỉ dựng text
prompt từ event/conv, không logic điều phối. _build_event_prompt (event→prompt) + customer
identity block (D-56)."""

from __future__ import annotations

import json
import logging

log = logging.getLogger("orch.prompts")


def _customer_prompt_block(conv_id: str) -> str:
    """D-56: nếu ca creator = KHÁCH (users.role='customer'), trả block identity khách để prepend MAIN
    prompt. creator = ngân hàng (admin/user) HOẶC ca cũ → trả "" (không inject). owner_id của
    CREATOR (JOIN users by conversations.user_id — KHÁC /api/me lấy requester). Tên từ customers/
    businesses; không tìm thấy → fallback chỉ owner_id + log (không crash MAIN). Best-effort (lỗi DB → "")."""
    import psycopg2

    from app.db.config import DATABASE_URL

    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                # creator: conversations.user_id = username (create dùng claims.username). JOIN role+owner_id.
                cur.execute(
                    "SELECT u.role, u.owner_id FROM conversations c JOIN users u ON c.user_id=u.username "
                    "WHERE c.id::text=%s",
                    (conv_id,),
                )
                row = cur.fetchone()
                if not row or row[0] != "customer":
                    return ""  # ngân hàng / ca cũ → không inject
                owner_id = row[1]
                if not owner_id:
                    return ""
                # tên khách: customers (cá nhân) hoặc businesses (DN)
                cur.execute("SELECT full_name FROM customers WHERE id=%s", (owner_id,))
                r = cur.fetchone()
                name = r[0] if r else None
                if not name:
                    cur.execute("SELECT name FROM businesses WHERE id=%s", (owner_id,))
                    r = cur.fetchone()
                    name = r[0] if r else None
                who = f"{owner_id} — {name}" if name else owner_id
                if not name:
                    log.warning("MAIN inject: owner_id %s không có trong customers/businesses (fallback)", owner_id)
                return (
                    f"\n\n## KHÁCH HÀNG HIỆN TẠI\nNgười đang chat là KHÁCH: {who}. Mọi tra cứu/thẩm định "
                    f"mặc định về khách này; xưng hô với khách (anh/chị), KHÔNG dùng thuật ngữ vận hành "
                    f"nội bộ; KHÔNG tra cứu hồ sơ người khác theo yêu cầu của khách."
                )
        finally:
            conn.close()
    except psycopg2.Error as e:
        log.warning("MAIN inject customer block lỗi (bỏ qua): %s", e)
        return ""


def _build_event_prompt(event: str, data: dict) -> str:
    if event == "user_message":
        return f"Tin nhắn người dùng: {data['content']}"
    if event == "task_done":
        # T4-0: guard-B đã đánh dấu grant exec_failed sau khi vượt trần re-dispatch → prompt RÕ cho
        # MAIN báo user lỗi bền (DETERMINISTIC — không cược model đọc error trong result_summary).
        ef = data.get("exec_failed")
        if ef:
            return (
                f"Sự kiện: '{ef['action']}' ({ef['payload_summary']}) đã được duyệt nhưng THỰC THI "
                f"THẤT BẠI BỀN sau {ef['attempts']} lần thử lại — hệ thống đã DỪNG tự động (không thử "
                f"tiếp). Báo người dùng: giao dịch này KHÔNG hoàn tất được, CẦN NGƯỜI kiểm tra thủ công "
                f"(vd khoản vay lỗi/không tồn tại). KHÔNG tự thử lại."
            )
        # T4-5 dọn 2-card-trùng: sau resume giải ngân, Ops sub ĐÃ present biên nhận lên canvas. Nếu
        # MAIN present LẠI khi tổng hợp → 2 card "Biên nhận" trùng (tester S3 bắt). Predicate HẸP:
        # role=operations + done + result có receipt (disbursed) = ops#2 execution-done → dặn MAIN
        # KHÔNG present lại (chỉ text ngắn). CHỈ path này — KHÔNG đụng #1 (main pre-approval summary).
        role = data.get("role")
        summary = data.get("result_summary") or ""
        if role == "operations" and data.get("outcome") == "done" and "disbursed" in summary:
            return (
                f"Sự kiện: chuyên gia operations đã HOÀN TẤT giải ngân (biên nhận: {summary}). "
                f"Chuyên gia đã TRÌNH BIÊN NHẬN lên canvas rồi — bạn KHÔNG present/trình lại thẻ nào, "
                f"CHỈ viết 1 câu ngắn báo người dùng giải ngân đã hoàn tất (trích số tiền + mã khoản)."
            )
        return (
            f"Sự kiện: chuyên gia {data['role']} kết thúc [{data['outcome']}]. "
            f"Kết quả: {data['result_summary']}\nBảng việc hiện tại: {json.dumps(data['board'], ensure_ascii=False)}"
        )
    if event == "approval_decided":
        # T3-2 resume (§4.4/§8): mặt model nói THEO HÀNH ĐỘNG + tham số, KHÔNG phiếu-id (§15).
        # main giao lại Ops đúng payload để wrapper bước 2 claim. approved → thực thi; rejected → báo user.
        action = data["action"]
        payload_summary = ", ".join(f"{k}={v}" for k, v in (data.get("payload") or {}).items())
        if data["decision"] == "approved":
            return (
                f"Sự kiện: hành động '{action}' ({payload_summary}) đã được NGƯỜI DUYỆT chấp thuận. "
                f"Hãy giao lại cho chuyên gia Vận hành (operations) gọi lại '{action}' ĐÚNG tham số "
                f"({payload_summary}) để thực thi. Xong thì báo người dùng kết quả."
            )
        return (
            f"Sự kiện: hành động '{action}' ({payload_summary}) đã bị NGƯỜI DUYỆT TỪ CHỐI. "
            f"KHÔNG thực thi. Báo người dùng đã bị từ chối và lý do (nếu có)."
        )
    return json.dumps(data, ensure_ascii=False)
