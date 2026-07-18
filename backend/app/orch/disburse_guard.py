"""Cross-owner disburse guard (T9-4 finding, money-adjacent) — tách khỏi gated.py (PROD ≤400 LOC).

Ca creator = KHÁCH yêu cầu giải ngân loan của khách KHÁC → phiếu tạo bình thường, dưới ngưỡng
auto → khách A kích hoạt giải ngân loan khách B. VÁ: gated._gated_txn gọi cross_owner_refusal
TRƯỚC advisory-lock/4-step; refuse fail-closed nếu loan không thuộc hồ sơ creator-khách.
"""

from __future__ import annotations

import logging
from typing import Any

import psycopg2

log = logging.getLogger("orch.disburse_guard")

_NOT_YOUR_LOAN = {
    "code": "not_your_loan",
    "message": "Khoản vay không thuộc hồ sơ của quý khách",
    "hint": "Chỉ giải ngân khoản vay thuộc hồ sơ của chính mình. Kiểm lại mã khoản vay.",
    "retryable": False,
}


def cross_owner_refusal(cur: Any, conv_id: str, loan_id: str | None) -> dict[str, Any] | None:
    """None = cho phép (ca bank HOẶC khách giải ngân đúng loan mình); dict 4-field = REFUSE.

    Ca creator KHÁCH (users.role='customer') → loans.owner_id PHẢI == creator.owner_id. fail-closed:
    creator owner NULL / loan không tồn tại-hoặc-khác-owner / lookup lỗi → refuse (money-adjacent,
    T9-4). Ca creator BANK (admin/user/ca cũ không map user) → None (qua — bank thao tác hộ mọi
    khách). Dùng CÙNG cur gated (đọc TRƯỚC mọi write — refuse rollback sạch, không poison tx)."""
    try:
        cur.execute(
            "SELECT u.role, u.owner_id FROM conversations c JOIN users u ON c.user_id=u.username WHERE c.id::text=%s",
            (conv_id,),
        )
        row = cur.fetchone()
        # creator không phải khách (bank / ca cũ không resolve user) → không áp guard.
        # Note (architect): no-resolving-conv → coi như bank/pass — khớp _customer_prompt_block JOIN.
        if not row or row["role"] != "customer":
            return None
        creator_owner = row["owner_id"]
        if not creator_owner:  # khách CHƯA có hồ sơ mà đòi giải ngân → fail-closed
            return dict(_NOT_YOUR_LOAN)
        cur.execute("SELECT owner_id FROM loans WHERE loan_id=%s", (loan_id,))
        lrow = cur.fetchone()
        if not lrow or lrow["owner_id"] != creator_owner:  # loan không tồn tại / khác owner → refuse
            return dict(_NOT_YOUR_LOAN)
        return None  # khách giải ngân đúng loan của mình → cho qua
    except psycopg2.Error as e:
        log.warning("cross-owner guard lookup lỗi conv=%s loan=%s → refuse fail-closed: %s", conv_id, loan_id, e)
        return dict(_NOT_YOUR_LOAN)
