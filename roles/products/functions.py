"""roles/products — STUB (vỏ viết — D-18/D-35; LAB đè khi đẻ thật).

Tool giả ĐÚNG contract (signature + envelope {found,item,asOf,hint} + isMock:true MỌI return).
Agent tiêu thụ stub y hệt tool thật → swap vô hình. SQL portable (chạy qua PGConnAdapter D-27).
1-2 tool đủ demo phối hợp. LAB drop functions thật + SCHEMAS → xoá stub (mount_role không đổi).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def product_suggest(conn: sqlite3.Connection, owner_id: str, loan_amount_vnd: float = 0,
                    loan_type: str | None = None) -> dict[str, Any]:
    """[STUB] Gợi ý gói vay theo hồ sơ. Số fake, shape thật. LAB đè khi đẻ thật."""
    # query customers thật để stub bám data có thật (test đường conn — lab-joint §4)
    row = conn.execute("SELECT id, full_name FROM customers WHERE id=?", (owner_id,)).fetchone()
    name = row["full_name"] if row else owner_id
    return {
        "found": True, "isMock": True, "asOf": _now(),
        "item": {
            "ownerId": owner_id, "ownerName": name,
            "options": [
                {"name": "Gói Chuẩn", "rate": "10.5%/năm", "tenor": "60 tháng", "fee": "0.5%", "fit": "phù hợp"},
                {"name": "Gói Ưu Đãi", "rate": "9.0%/năm", "tenor": "36 tháng", "fee": "1.0%", "fit": "nếu trả nhanh"},
            ],
            "recommended": "Gói Chuẩn",
            "computedBy": "STUB",
        },
        "hint": "[STUB] Sản phẩm thật chưa nuôi — shape đúng, số FAKE, KHÔNG dùng để quyết.",
    }


REGISTRY = {"product_suggest": product_suggest}
ANNOTATIONS = {"product_suggest": {"readOnlyHint": True}}
SCHEMAS: dict[str, Any] = {
    "product_suggest": {
        "mô tả": ("[STUB] Gợi ý gói vay phù hợp theo hồ sơ khách + số tiền + loại vay. Trả danh sách"
                  " gói (rate/tenor/fee/fit) + gói khuyến nghị. Read-only. (Sản phẩm thật chưa nuôi.)"),
        "params": {
            "owner_id": {"type": "str", "required": True, "desc": "id khách/DN"},
            "loan_amount_vnd": {"type": "float", "default": 0, "desc": "số tiền vay (VND)"},
            "loan_type": {"type": "str", "values": ["consumer", "secured"], "default": None,
                          "desc": "loại vay"},
        }},
}
