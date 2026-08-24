"""Prompt-building cho MAIN turn (S8 — tách khỏi main_session.py để <400 LOC). Chỉ dựng text
prompt từ event/conv, không logic điều phối. _build_event_prompt (event→prompt) + customer
identity block (D-56)."""

from __future__ import annotations

import json
import logging

from app.orch.main_skill import CREDIT_MEMO_MIN_DISTINCT_DONE_ROLES, CREDIT_MEMO_SECTIONS, CREDIT_MEMO_TITLE
from app.prompting import get_prompt_service
from app.storage import connect_core

log = logging.getLogger("orch.prompts")


def _prompt(key: str, **values: object) -> str:
    return get_prompt_service().render(key, values).rstrip("\n")


def _completed_specialist_roles(board: object) -> tuple[str, ...]:
    """Role động trên board: chỉ `done` có kết quả; task trùng role không làm đủ cổng giả."""
    if not isinstance(board, list):
        return ()
    roles = {
        role.strip()
        for task in board
        if isinstance(task, dict)
        and task.get("status") == "done"
        and isinstance((role := task.get("role")), str)
        and role.strip()
    }
    return tuple(sorted(roles))


def _credit_memo_board_instruction(board: object) -> str:
    """Cổng prompt xác định từ board, không cược MAIN tự đếm task/role khi resume."""
    roles = _completed_specialist_roles(board)
    role_text = ", ".join(roles) if roles else "chưa có"
    if len(roles) < CREDIT_MEMO_MIN_DISTINCT_DONE_ROLES:
        return _prompt(
            "event.credit_memo.blocked",
            minimum_roles=CREDIT_MEMO_MIN_DISTINCT_DONE_ROLES,
            role_text=role_text,
        )

    sections = "; ".join(f"`{section}`" for section in CREDIT_MEMO_SECTIONS)
    return _prompt(
        "event.credit_memo.ready",
        role_count=len(roles),
        role_text=role_text,
        title=CREDIT_MEMO_TITLE,
        sections=sections,
    )


def _customer_prompt_block(conv_id: str) -> str:
    """D-56: nếu ca creator = KHÁCH (users.role='customer'), trả block identity khách để prepend MAIN
    prompt. creator = ngân hàng (admin/user) HOẶC ca cũ → trả "" (không inject). owner_id của
    CREATOR (JOIN users by conversations.user_id — KHÁC /api/me lấy requester). Tên từ customers/
    businesses; không tìm thấy → fallback chỉ owner_id + log (không crash MAIN). Best-effort (lỗi DB → "")."""
    import psycopg2

    try:
        conn = connect_core()
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
                    # T9-1 (D-57): KHÁCH role=customer CHƯA có hồ sơ (owner_id NULL) → block đổi ý:
                    # thu hồ sơ bằng present_form, KHÔNG hỏi vặt từng câu. KHÁC 'set-but-missing'
                    # (owner_id có nhưng không trong customers → fallback block dưới) — 3 trạng thái riêng.
                    return _prompt("customer.new")
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
                return _prompt("customer.existing", who=who)
        finally:
            conn.close()
    except psycopg2.Error as e:
        log.warning("MAIN inject customer block lỗi (bỏ qua): %s", e)
        return ""


def _build_event_prompt(event: str, data: dict) -> str:
    if event == "user_message":
        return _prompt("event.user_message", content=data["content"])
    if event == "task_done":
        # T4-0: guard-B đã đánh dấu grant exec_failed sau khi vượt trần re-dispatch → prompt RÕ cho
        # MAIN báo user lỗi bền (DETERMINISTIC — không cược model đọc error trong result_summary).
        ef = data.get("exec_failed")
        if ef:
            return _prompt(
                "event.task_done.exec_failed",
                action=ef["action"],
                payload_summary=ef["payload_summary"],
                attempts=ef["attempts"],
            )
        # T4-5 dọn 2-card-trùng: sau resume giải ngân, Ops sub ĐÃ present biên nhận lên canvas. Nếu
        # MAIN present LẠI khi tổng hợp → 2 card "Biên nhận" trùng (tester S3 bắt). Predicate HẸP:
        # role=operations + done + result có receipt (disbursed) = ops#2 execution-done → dặn MAIN
        # KHÔNG present lại (chỉ text ngắn). CHỈ path này — KHÔNG đụng #1 (main pre-approval summary).
        role = data.get("role")
        summary = data.get("result_summary") or ""
        if role == "operations" and data.get("outcome") == "done" and "disbursed" in summary:
            return _prompt("event.task_done.operations_disbursed", result_summary=summary)
        prompt = _prompt(
            "event.task_done.generic",
            role=data["role"],
            outcome=data["outcome"],
            result_summary=data["result_summary"],
            board_json=json.dumps(data.get("board") or [], ensure_ascii=False),
        )
        return prompt + _credit_memo_board_instruction(data.get("board"))
    if event == "approval_decided":
        # T3-2 resume (§4.4/§8): mặt model nói THEO HÀNH ĐỘNG + tham số, KHÔNG phiếu-id (§15).
        # main giao lại Ops đúng payload để wrapper bước 2 claim. approved → thực thi; rejected → báo user.
        action = data["action"]
        payload_summary = ", ".join(f"{k}={v}" for k, v in (data.get("payload") or {}).items())
        if data["decision"] == "approved":
            return _prompt("event.approval.approved", action=action, payload_summary=payload_summary)
        # DF-B-07: reason nay ĐI KÈM wake payload (approvals._emit_and_wake) → nếu có, chèn NGUYÊN
        # VĂN vào prompt + lệnh MAIN truyền đạt đúng lời người duyệt (không diễn dịch/bịa lý do).
        reason = (data.get("reason") or "").strip()
        if reason:
            return _prompt(
                "event.approval.rejected_reason",
                action=action,
                payload_summary=payload_summary,
                reason=reason,
            )
        return _prompt("event.approval.rejected", action=action, payload_summary=payload_summary)
    return json.dumps(data, ensure_ascii=False)
