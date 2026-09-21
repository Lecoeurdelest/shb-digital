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

    roles = _completed_specialist_roles(board)
    role_text = ", ".join(roles) if roles else "none"
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

    import psycopg2

    try:
        conn = connect_core()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT u.role, u.owner_id FROM conversations c JOIN users u ON c.user_id=u.username "
                    "WHERE c.id::text=%s",
                    (conv_id,),
                )
                row = cur.fetchone()
                if not row or row[0] != "customer":
                    return ""
                owner_id = row[1]
                if not owner_id:
                    return _prompt("customer.new")

                cur.execute("SELECT full_name FROM customers WHERE id=%s", (owner_id,))
                r = cur.fetchone()
                name = r[0] if r else None
                if not name:
                    cur.execute("SELECT name FROM businesses WHERE id=%s", (owner_id,))
                    r = cur.fetchone()
                    name = r[0] if r else None
                who = f"{owner_id} — {name}" if name else owner_id
                if not name:
                    log.warning("MAIN injection: owner_id %s is absent from customers/businesses (fallback)", owner_id)
                return _prompt("customer.existing", who=who)
        finally:
            conn.close()
    except psycopg2.Error as e:
        log.warning("failed to inject MAIN customer block (ignored): %s", e)
        return ""


def _build_event_prompt(event: str, data: dict) -> str:
    if event == "user_message":
        return _prompt("event.user_message", content=data["content"])
    if event == "task_done":
        ef = data.get("exec_failed")
        if ef:
            return _prompt(
                "event.task_done.exec_failed",
                action=ef["action"],
                payload_summary=ef["payload_summary"],
                attempts=ef["attempts"],
            )

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
        action = data["action"]
        payload_summary = ", ".join(f"{k}={v}" for k, v in (data.get("payload") or {}).items())
        if data["decision"] == "approved":
            return _prompt("event.approval.approved", action=action, payload_summary=payload_summary)

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
