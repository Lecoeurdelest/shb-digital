"""READ-scope guard tầng mount (FIX E — CHẶN S9) — ca KHÁCH chỉ tra được hồ sơ CỦA MÌNH.

Lỗ hổng (tester PROD): khách A route Credit → credit_assess(owner_id khác) → DSCR/nợ khách B hiện
màn khách A. VÁ: choke point DUY NHẤT ở VỎ (_make_handler, TRƯỚC gọi fn LAB — N1 giữ nguyên).

RULE MAP (arg-name → cách kiểm) — tool mới tự ăn theo key. Kiểm MỌI key định danh có trong args
(không first-match — 1 tool nhiều arg như legal_check_docs(owner_id, collateral_id) → kiểm cả 2).
Ca creator KHÁCH (role=customer) owner O:
  owner_id     → phải == O
  id (cust_*)  → phải == O (cust_get)
  loan_id      → loans.owner_id == O
  collateral_id→ collaterals.owner_id == O
  cust_search  → REFUSE thẳng (search = liệt kê người khác)
Ca bank / creator không-customer → PASS (0 đổi). Fail-closed: resolve/DB lỗi → refuse.
owner_id=NULL (khách chưa hồ sơ) → refuse mọi tool định danh (đúng — MAIN inject bảo present_form).

Raw pg_conn + %s (VỎ code, KHÔNG adapter LAB `?`). Lookup MỖI call (KHÔNG cache — owner_id đổi
trong phiên: NULL → C901 sau form-submit; cache = mis-guard).
"""

from __future__ import annotations

import logging
from typing import Any

import psycopg2

log = logging.getLogger("mount.read_scope")

_NOT_YOUR_DATA = {
    "code": "not_your_data",
    "message": "Thông tin không thuộc hồ sơ của quý khách",
    "hint": "Quý khách chỉ tra cứu được hồ sơ của chính mình.",
    "retryable": False,
}

# tool CHỈ dành ca bank (khách gọi = liệt kê người khác) → refuse thẳng cho ca khách.
_SEARCH_TOOLS = {"cust_search"}
# tool có arg `id` là ĐỊNH DANH OWNER (cust_get) — phân biệt với id khác (không có hiện tại).
_ID_IS_OWNER_TOOLS = {"cust_get"}


def _creator_customer_owner(pg_conn: Any, conv_id: str) -> tuple[bool, str | None]:
    """(is_customer, owner_id) của creator ca. is_customer=False → ca bank/không-resolve → PASS.
    Best-effort: DB lỗi → (False, None) KHÔNG được — leak-gate phải fail-closed. Nhưng lookup creator
    lỗi = không biết ai → coi NHƯ KHÔNG customer (pass) CHỈ khi conv không resolve; lỗi DB thực sự
    → raise để caller refuse. Ở đây: row None → (False,None) pass (FIX-A choice: attacker conv luôn
    resolve). psycopg2.Error → raise (caller bắt → refuse fail-closed)."""
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT u.role, u.owner_id FROM conversations c JOIN users u ON c.user_id=u.username WHERE c.id::text=%s",
            (conv_id,),
        )
        row = cur.fetchone()
    if not row or row[0] != "customer":
        return (False, None)  # bank / ca cũ không resolve → không áp guard (pass)
    return (True, row[1])


def _owner_of(pg_conn: Any, table: str, key_col: str, key_val: str) -> str | None:
    """owner_id của 1 bản ghi (loans/collaterals) — raw %s. None = không tồn tại."""
    with pg_conn.cursor() as cur:
        cur.execute(f"SELECT owner_id FROM {table} WHERE {key_col}=%s", (key_val,))  # noqa: S608 — table/col hằng nội bộ
        r = cur.fetchone()
    return r[0] if r else None


def read_scope_refusal(pg_conn: Any, conv_id: str, tool: str, args: dict[str, Any]) -> dict[str, Any] | None:
    """None = cho phép; dict 4-field = REFUSE. Kiểm MỌI arg định danh vs owner creator-khách.

    pg_conn = raw psycopg2 (VỎ cấp, cùng conn adapter dùng). Gọi TRƯỚC fn LAB trong _make_handler."""
    try:
        is_customer, owner = _creator_customer_owner(pg_conn, conv_id)
        if not is_customer:
            return None  # ca bank / không resolve → tool chạy như cũ (N1)

        # khách CHƯA có hồ sơ (owner NULL) mà gọi tool định danh → refuse (MAIN inject bảo present_form)
        if not owner:
            if tool in _SEARCH_TOOLS or any(k in args for k in ("owner_id", "id", "loan_id", "collateral_id")):
                return dict(_NOT_YOUR_DATA)
            return None  # tool không định danh (calc/present) → qua

        # cust_search: liệt kê người khác → refuse thẳng cho ca khách
        if tool in _SEARCH_TOOLS:
            return {**_NOT_YOUR_DATA, "hint": f"Hồ sơ của quý khách: {owner}. Không tra cứu danh sách người khác."}

        # kiểm MỌI arg định danh CÓ trong args (không first-match — 1 tool nhiều arg)
        if args.get("owner_id") is not None and args["owner_id"] != owner:
            return dict(_NOT_YOUR_DATA)
        if tool in _ID_IS_OWNER_TOOLS and args.get("id") is not None and args["id"] != owner:
            return dict(_NOT_YOUR_DATA)
        if args.get("loan_id") is not None and _owner_of(pg_conn, "loans", "loan_id", args["loan_id"]) != owner:
            return dict(_NOT_YOUR_DATA)
        if (
            args.get("collateral_id") is not None
            and _owner_of(pg_conn, "collaterals", "id", args["collateral_id"]) != owner
        ):
            return dict(_NOT_YOUR_DATA)
        return None  # mọi arg định danh khớp owner → cho qua
    except psycopg2.Error as e:
        log.warning("read-scope guard lỗi conv=%s tool=%s → refuse fail-closed: %s", conv_id, tool, e)
        return dict(_NOT_YOUR_DATA)
