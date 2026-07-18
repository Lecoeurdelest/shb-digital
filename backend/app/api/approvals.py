"""Approvals router (T3-2) — ADMIN (ngân hàng) decide + list. CONTRACT: success=resource trần, error 4-field.

D-56 (người chốt, ĐẢO D-54): app = CỬA KHÁCH HÀNG — khách tự chat, agent auto-duyệt khoản nhỏ
(phanh phân tầng T5-2'); khoản LỚN bắn về NGÂN HÀNG duyệt. Duyệt phiếu = việc NGÂN HÀNG → require_admin.
Customer gọi decide → 403 forbidden 4-field.

GET /api/approvals?status=pending (admin) — hàng chờ duyệt (bank).
POST /api/approvals/{id}/decide (admin, {decision, reason?}) — atomic → SSE approval.decided →
ĐÁNH THỨC main qua handle_room_event (CÙNG đường sub-báo-xong §4.4 — KHÔNG chế cơ chế mới).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.auth.deps import require_admin
from app.errors import ApiError
from app.orch import store_approvals

log = logging.getLogger("api.approvals")

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class DecideBody(BaseModel):
    decision: str  # approved | rejected
    reason: str | None = None


@router.get("")
async def list_approvals(status: str = Query("pending"), claims: dict = Depends(require_admin)) -> list[dict[str, Any]]:
    """List pending approval tickets (admin only).

    Hàng chờ duyệt (admin). S3 chỉ status=pending (khác → 400)."""
    if status != "pending":
        raise ApiError(
            400, "bad_status", f"status '{status}' không hỗ trợ.", "Chỉ status=pending ở S3.", retryable=False
        )
    return await store_approvals.list_pending()


@router.post("/{approval_id}/decide")
async def decide(approval_id: str, body: DecideBody, claims: dict = Depends(require_admin)) -> dict[str, Any]:
    """Approve/reject an approval ticket (admin only) — atomic, wakes MAIN, emits SSE.

    ADMIN (ngân hàng — D-56) duyệt/từ chối phiếu → atomic → SSE + đánh thức main.

    decide atomic (UPDATE…WHERE status='pending') → None = 409 (đã quyết) hoặc 404 (không tồn tại).
    """
    if not store_approvals.valid_decision(body.decision):
        raise ApiError(
            400,
            "bad_decision",
            f"decision '{body.decision}' không hợp lệ.",
            "Dùng 'approved' | 'rejected'.",
            retryable=False,
        )

    decided = await store_approvals.decide(
        approval_id, body.decision, decided_by=claims.get("username", "admin"), reason=body.reason
    )
    if decided is None:
        # phân biệt 404 (không tồn tại) vs 409 (đã quyết) — chống double-wake
        if await store_approvals.approval_exists(approval_id):
            raise ApiError(
                409,
                "approval_already_decided",
                "Phiếu đã được quyết trước đó.",
                "Tải lại hàng chờ duyệt.",
                retryable=False,
            )
        raise ApiError(404, "not_found", f"Không có phiếu '{approval_id}'.", "Kiểm lại id.", retryable=False)

    # SSE approval.decided + card sync + đánh thức main — SAU khi decide commit (§5)
    _emit_and_wake(decided)
    # HOOK a (T9-2): mail báo khách khoản vay được duyệt/từ chối — best-effort async, KHÔNG chặn.
    # SAU _emit_and_wake (SSE/wake xong). Ca bank/không email → helper tự skip.
    _notify_decided(decided)
    decided.pop("_card_row", None)  # nội bộ (emit card SSE) — KHÔNG lên API response
    return decided


def _notify_decided(decided: dict[str, Any]) -> None:
    """Mail HOOK a (T9-2 + addendum HTML brand): khoản vay được {phê duyệt|từ chối}.
    status='used'/'approved'→phê duyệt, 'rejected'→từ chối. Plain fallback + HTML multipart."""
    from app.notify.email import render_email_html
    from app.notify.hooks import app_url, notify_conv_owner, owner_greeting

    approved = decided.get("status") in ("used", "approved")
    kind = "approved" if approved else "rejected"
    verb = "phê duyệt" if approved else "từ chối"
    payload = decided.get("payload") or {}
    amount = int(float(payload.get("amount"))) if payload.get("amount") else 0
    loan_id = payload.get("loan_id", "")
    amount_str = f" số tiền {amount:,} VND" if amount else ""
    body = (
        f"Kính gửi anh/chị,\n\nYêu cầu '{decided.get('action')}'{amount_str} của anh/chị đã được "
        f"{verb}.\n\nTrân trọng,\nBANK Digital."
    )
    d = {
        "greeting_name": owner_greeting(decided["conv_id"]),
        "loan_id": loan_id,
        "amount_vnd": amount,
        "decided_by": decided.get("decided_by"),
        "decided_at": decided.get("decided_at"),
        "ref": decided.get("id"),
        "app_url": app_url(),
    }
    html_body = render_email_html(kind, d)
    icon = "✅" if approved else "✖️"
    subject = f"{icon} Khoản vay {loan_id} đã được {verb} — BANK Digital"
    notify_conv_owner(decided["conv_id"], subject, body, html_body)


def _emit_and_wake(decided: dict[str, Any]) -> None:
    """SSE approval.decided (lazy import) + ĐÁNH THỨC main qua handle_room_event (§4.4 event-wake).

    KHÔNG chế cơ chế mới — CÙNG đường task_done sub dùng. approval_decided vào hàng đợi phòng của
    conv PHIẾU (không phải conv đang mở) → 1-lượt/phòng → run_main_turn xử nhánh mới.
    Cả approved LẪN rejected đánh thức (main biết + báo user — brief §B4). Event KHÔNG dedup (§4.2).
    """
    from app.orch.room import handle_room_event
    from app.sse.emit import emit

    conv_id = decided["conv_id"]
    # SSE cho FE (badge/queue cập nhật, panel decided)
    emit(
        conv_id,
        "approval.decided",
        {
            "phieu": {
                "id": decided["id"],
                "action": decided["action"],
                "status": decided["status"],
                "decided_by": decided["decided_by"],
                "reason": decided["reason"],
            }
        },
    )
    # card SSE (T3-2 gap FE+architect): card.data đã sync trong tx decide → emit card mới để FE
    # upsertCard cập nhật panel NGAY + reload-safe (DB đã đúng). _card_row None nếu card không tồn
    # tại (hiếm — phiếu không kèm card) → bỏ qua.
    card_row = decided.get("_card_row")
    if card_row is not None:
        from app.orch.store import _card_to_dict

        emit(conv_id, "card", {"card": _card_to_dict(card_row)})
    # ĐÁNH THỨC main — spawn (fire-and-forget, giống decide trong multi-agent §8; inline await sẽ
    # block HTTP response chờ main xong cả lượt). payload mặt-model nói theo HÀNH ĐỘNG + tham số
    # (KHÔNG phiếu-id §15) — payload để main giao lại đúng args.
    payload = {
        "approval_id": decided["id"],  # NỘI BỘ (không lên prompt)
        "action": decided["action"],
        "decision": decided["status"],  # approved | rejected
        "payload": decided.get("payload") or {},
    }

    async def _wake_guarded() -> None:
        # nhất quán kỷ luật _report (sub_runner "đường đỡ cuối — không nuốt im"): resume fail
        # surface app-log, KHÔNG rơi im vào asyncio default handler.
        try:
            await handle_room_event(conv_id, "approval_decided", payload)
        except Exception as e:  # noqa: BLE001
            log.error("resume approval_decided lỗi conv=%s: %s", conv_id, e)

    asyncio.ensure_future(_wake_guarded())
