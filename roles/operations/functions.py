"""roles/operations — STUB (vỏ viết — D-18/D-35; LAB đè khi đẻ thật).

Tool giả ĐÚNG contract (envelope {found,item,asOf,hint} + isMock:true MỌI return). SQL portable.
1 tool đủ demo. disburse (tool gated, phanh) = S4 — KHÔNG ở stub này. LAB drop thật → xoá stub.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ops_plan(conn: sqlite3.Connection, owner_id: str, loan_type: str | None = None) -> dict[str, Any]:
    """[STUB] Lộ trình xử lý hồ sơ vay (các bước + người phụ trách + ETA). Số fake, shape thật."""
    row = conn.execute("SELECT id FROM customers WHERE id=?", (owner_id,)).fetchone()
    exists = row is not None
    return {
        "found": True, "isMock": True, "asOf": _now(),
        "item": {
            "ownerId": owner_id, "ownerExists": exists,
            "steps": [
                {"step": "Tiếp nhận hồ sơ", "owner": "RM", "eta": "1 ngày"},
                {"step": "Thẩm định tín dụng", "owner": "Credit", "eta": "2 ngày"},
                {"step": "Kiểm pháp lý", "owner": "Legal", "eta": "2 ngày"},
                {"step": "Phê duyệt + giải ngân", "owner": "Operations", "eta": "1 ngày"},
            ],
            "totalDays": 6,
            "computedBy": "STUB",
        },
        "hint": "[STUB] Vận hành thật chưa nuôi — shape đúng, số FAKE, KHÔNG dùng để quyết. "
                "Giải ngân thật (disburse, có phanh) = sprint sau.",
    }


def disburse(conn: sqlite3.Connection, loan_id: str, amount: float = 0) -> dict[str, Any]:
    """[GATED — vỏ, T3-1] Giải ngân khoản vay. CÓ PHANH: gọi đầu → chờ người duyệt → duyệt →
    chạy (ghi loans.status='disbursed'). Logic thật ở app/orch/gated.disburse (wrapper thread-conn
    tự chạy — REGISTRY entry này chỉ để mount thấy tên+schema; gated wrapper KHÔNG gọi fn này).
    D-18: phanh là của VỎ. GATED_WHITELIST={disburse}."""
    # KHÔNG chạy trực tiếp — gated wrapper (mount) chặn + tự chạy GATED_TOOLS['disburse'].
    raise RuntimeError("disburse phải qua gated wrapper (T3-1) — không gọi trực tiếp")


# ops_plan read-only; disburse GATED (whitelist app/orch/gated.GATED_WHITELIST).
REGISTRY = {"ops_plan": ops_plan, "disburse": disburse}
ANNOTATIONS = {
    "ops_plan": {"readOnlyHint": True},
    "disburse": {"destructiveHint": True},  # gated (§4.4) — harness policy máy-đọc
}
SCHEMAS: dict[str, Any] = {
    "ops_plan": {
        "mô tả": ("[STUB] Lộ trình xử lý hồ sơ vay: các bước + người phụ trách + ETA + tổng ngày."
                  " Read-only. (Vận hành thật chưa nuôi; giải ngân có phanh = sprint sau.)"),
        "params": {
            "owner_id": {"type": "str", "required": True, "desc": "id khách/DN"},
            "loan_type": {"type": "str", "values": ["consumer", "secured"], "default": None,
                          "desc": "loại vay"},
        }},
    "disburse": {
        "mô tả": ("GIẢI NGÂN khoản vay (CÓ PHANH — cần người duyệt). Gọi lần đầu → hệ thống CHẶN, "
                  "tạo phiếu chờ duyệt; báo main kết thúc lượt. Sau khi được DUYỆT, gọi lại đúng "
                  "tham số → giải ngân chạy thật. KHÔNG tự nhẩm/bỏ qua phanh."),
        "params": {
            "loan_id": {"type": "str", "required": True, "desc": "id khoản vay, vd 'L001'"},
            "amount": {"type": "float", "default": 0, "desc": "số tiền giải ngân (VND)"},
        }},
}
