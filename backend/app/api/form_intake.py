"""Form intake (T9-1 D-57) — POST /api/conversations/{id}/form-submit: khách MỚI nộp hồ sơ →
tạo customers C9xx + link users.owner_id + đánh thức MAIN. Tách khỏi conversations.py (PROD modular).

VÒNG ĐỜI: register (owner_id=NULL) → MAIN present_form → khách điền → form-submit ĐÂY:
  (a) mint C9xx (advisory-lock serialize) → INSERT customers → UPDATE users.owner_id  [1 tx, COMMIT]
  (b) card status 'pending'→'submitted' atomic (double-submit → 409)
  (c) bơm message '[HỒ SƠ ĐÃ NỘP]' + wake MAIN qua handle_room_event (CÙNG đường approval — §4.4)

Ordering (advisor): COMMIT owner_id TRƯỚC wake — wake trước thì turn đọc owner_id=NULL → re-present form.
loan_purpose KHÔNG vào customers (không có cột) → vào message wake (loan intent, không master data).
"""

from __future__ import annotations

import logging
from typing import Any

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.deps import can_access_conv, require_user
from app.db.config import DATABASE_URL
from app.errors import ApiError
from app.orch.common_tools import FORM_REQUIRED
from app.orch.store import get_conversation

log = logging.getLogger("api.form_intake")

router = APIRouter(prefix="/api/conversations", tags=["form-intake"])

# advisory-lock key CỐ ĐỊNH serialize mint C9xx (2 submit đồng thời → cùng max+1 → PK collision).
# Deterministic int (không hash() Python — PYTHONHASHSEED đổi giữa process). Mirror gated.py pattern.
_MINT_LOCK_KEY = 0x0900000000000001

# cột customers form ghi (5 — KHỚP schema; age/region để NULL; loan_purpose KHÔNG có cột → vào wake msg).
_CUSTOMER_COLS = ("full_name", "id_number", "address", "occupation", "monthly_income")


class FormSubmitBody(BaseModel):
    card_id: str
    values: dict[str, Any]


@router.post("/{conv_id}/form-submit")
async def form_submit(conv_id: str, body: FormSubmitBody, claims: dict = Depends(require_user)) -> dict[str, Any]:
    """Khách nộp hồ sơ → tạo customers C9xx + link + wake MAIN. 404-hide ca người khác · card sai
    ca/không tồn tại 404 · thiếu field bắt buộc 400 · income không phải số 400 · đã submit 409."""
    conv = await get_conversation(conv_id)
    if conv is None or not can_access_conv(conv, claims):
        raise ApiError(404, "not_found", "Không tìm thấy hội thoại.", "Kiểm lại id.", retryable=False)

    values = body.values or {}
    missing = [f for f in FORM_REQUIRED if not str(values.get(f, "")).strip()]
    if missing:
        raise ApiError(
            400, "missing_fields", f"Thiếu thông tin bắt buộc: {missing}", "Điền đủ rồi nộp lại.", retryable=True
        )
    try:
        income = int(float(values["monthly_income"]))
    except (TypeError, ValueError) as e:
        raise ApiError(400, "bad_income", "Thu nhập phải là số.", "Nhập số VND (vd 15000000).", retryable=True) from e

    # tx-sync trong to_thread (D-22 — psycopg2 sync không block loop 1-worker).
    import asyncio

    result = await asyncio.to_thread(_submit_txn, conv_id, claims.get("sub"), body.card_id, values, income)
    if result == "already_submitted":
        raise ApiError(409, "form_already_submitted", "Hồ sơ đã được nộp.", "Không nộp lại.", retryable=False)
    if result == "card_not_found":
        raise ApiError(404, "not_found", "Không tìm thấy form hồ sơ.", "Tải lại trang.", retryable=False)

    # (c) wake MAIN SAU khi owner_id đã COMMIT (advisor: wake trước → turn đọc owner_id=NULL → re-present)
    await _wake_main(conv_id, result, values)
    return {"owner_id": result["owner_id"], "customer_created": True}


def _submit_txn(conv_id: str, user_id: str | None, card_id: str, values: dict, income: int) -> Any:
    """1 tx: mint C9xx (advisory-lock) → INSERT customers → UPDATE users.owner_id → flip card atomic.
    Trả dict{owner_id, full_name} khi ok; 'already_submitted' / 'card_not_found' khi chặn."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # (b-guard) card flip ATOMIC TRƯỚC (idempotent double-submit): pending→submitted, cùng ca.
            # jsonb_set data.status; WHERE status != submitted → rowcount 0 = đã nộp (409) hoặc card sai ca.
            cur.execute(
                "UPDATE cards SET data = jsonb_set(data, '{status}', '\"submitted\"') "
                "WHERE id=%s AND conv_id=%s AND type='form' AND data->>'status' IS DISTINCT FROM 'submitted' "
                "RETURNING id",
                (card_id, conv_id),
            )
            if cur.fetchone() is None:
                # phân biệt: card tồn tại (đã submitted) vs không tồn tại/sai ca
                cur.execute("SELECT data->>'status' AS s FROM cards WHERE id=%s AND conv_id=%s", (card_id, conv_id))
                row = cur.fetchone()
                conn.rollback()
                return "already_submitted" if row else "card_not_found"

            # (a) mint C9xx serialize (advisory-xact-lock — tự release ở commit/rollback)
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (_MINT_LOCK_KEY,))
            owner_id = _next_c9xx(cur)
            cur.execute(
                f"INSERT INTO customers (id, {', '.join(_CUSTOMER_COLS)}) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    owner_id,
                    values["full_name"],
                    values["id_number"],
                    values["address"],
                    values["occupation"],
                    income,
                ),
            )
            # link account đang login → owner_id mới (JOIN by users.id = claims.sub)
            cur.execute("UPDATE users SET owner_id=%s WHERE id::text=%s", (owner_id, user_id))
            conn.commit()  # owner_id COMMIT TRƯỚC wake (advisor ordering)
            return {"owner_id": owner_id, "full_name": values["full_name"]}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _next_c9xx(cur: Any) -> str:
    """owner_id mới dạng C9NN zero-pad (C901, C902… — fixed-width để MAX lexical đúng, không đụng
    seed C001-C030). Gọi TRONG advisory-lock (serialize — 2 submit không cùng max)."""
    cur.execute("SELECT id FROM customers WHERE id LIKE 'C9%%' ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    n = (int(row["id"][2:]) + 1) if row else 1
    return f"C9{n:02d}"


async def _wake_main(conv_id: str, result: dict, values: dict) -> None:
    """Bơm message '[HỒ SƠ ĐÃ NỘP]' (kèm loan_purpose — loan intent) + wake MAIN qua handle_room_event
    (CÙNG đường approval.decided/user_message — §4.4, KHÔNG cơ chế mới). Lỗi wake surface log, không nuốt."""
    from app.orch.room import handle_room_event

    content = (
        f"[HỒ SƠ ĐÃ NỘP] Họ tên: {values.get('full_name')} · CMND: {values.get('id_number')} · "
        f"Nghề: {values.get('occupation')} · Thu nhập: {values.get('monthly_income')} VND · "
        f"Mục đích vay: {values.get('loan_purpose')}. Hồ sơ đã tạo (mã {result['owner_id']}) — "
        f"hãy tiếp tục thẩm định hoặc hỏi thêm nếu cần."
    )
    try:
        await handle_room_event(conv_id, "user_message", {"content": content})
    except Exception as e:  # noqa: BLE001
        log.error("wake MAIN sau form-submit lỗi conv=%s: %s", conv_id, e)
