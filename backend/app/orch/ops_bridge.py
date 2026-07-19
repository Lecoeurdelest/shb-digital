"""ops_bridge (T12-3b) — proxy conn cho `ops_disburse` LAB chạy dưới gated (1-tx).

VẤN ĐỀ: LAB `ops_disburse` viết cho sqlite3 — `conn.execute("...?...")` (raw psycopg2 KHÔNG có
`.execute()`), `conn.execute("BEGIN IMMEDIATE")` + `conn.commit()`/`conn.rollback()` NỘI BỘ, bắt
`sqlite3.IntegrityError/OperationalError`. Chạy verbatim trên conn gated (psycopg2, gated sở hữu
1 tx duy nhất) → (1) AttributeError `.execute`; (2) commit nội bộ vỡ invariant `status='used' ⟺
receipt`; (3) exception không map → nhánh chống-đôi/khoá-sổ của LAB chết.

GIẢI (ít-xâm-lấn nhất — 0 sửa fn LAB byte-identical, 0 sửa cấu trúc gated): proxy CHỈ cho tool này:
- `.execute(sql, params)` sqlite-style → `?`→`%s`, chạy trên cursor của conn gated (SAME tx).
- `BEGIN IMMEDIATE` → NO-OP (gated đã BEGIN + advisory-lock serialize).
- `.commit()`/`.rollback()` → NO-OP (gated sở hữu commit/rollback DUY NHẤT — _branch_claim/auto).
- psycopg2.Error ở execute → re-raise `sqlite3.IntegrityError/OperationalError` tương đương (giữ
  nhánh already_disbursed/ledger_busy của LAB).
KHÔNG dùng PGConnAdapter chung (nó phục vụ read-path + assessments-write; thêm mode = rủi ro 43
money-test + mọi read tool). Proxy này SỐNG riêng cho ops_disburse.

MONEY-INVARIANT (blocked-return → RAISE): LAB `ops_disburse` TRẢ DICT cho block (disburse_blocked/
invalid_param/found:False) thay vì raise. Gated `_branch_claim` set `status='used'` ATOMIC TRƯỚC khi
chạy inner → coi mọi return là success → phiếu 'used' + dict-blocked làm receipt = giải ngân BỊ
CHẶN nhưng phiếu consumed (không retry được). `disburse` stub cũ RAISE khi lỗi (contract gated:
fail=raise→rollback→phiếu về approved). Bridge KHỚP contract đó: block/not-found → RAISE →
gated rollback → phiếu retryable. CHỈ disbursement THẬT (found:True + disbursementId) mới để commit.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

import psycopg2
import psycopg2.extras

# code trả từ ops_disburse = KHÔNG-giải-ngân (raise để gated rollback, phiếu về approved)
_BLOCKED_CODES = {"disburse_blocked", "invalid_param"}


class OpsDisburseBlocked(Exception):
    """Bridge raise khi ops_disburse trả block/not-found — gated rollback (phiếu về approved, retryable).

    CARRY payload 4-field NGUYÊN VĂN của LAB (`.payload`) → gated wrapper trả THẲNG payload này (không
    generic gated_error) → agent + MAIN nhận đúng code/message/hint/blockers "vì sao chặn", biết đường
    xử (reject tay / bổ sung thủ tục). LƯU Ý (D-68/T12-3b): dưới rollback, approvals row về 'approved'
    KHÔNG ghi được reason vào phiếu — reason tới AGENT (tool return) + MAIN (result), KHÔNG tới row phiếu."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__(str(payload.get("message") or "ops_disburse bị chặn"))


_Q = re.compile(r"\?")


class _OpsCursor:
    """Cursor sqlite-like trên 1 psycopg2 cursor — `.fetchone()/.fetchall()` trả sqlite3.Row-like
    (dict(r) hoạt động qua RealDictCursor của conn gated). LAB dùng `dict(r)` nên cần mapping row."""

    def __init__(self, pg_cursor: Any) -> None:
        self._cur = pg_cursor

    def fetchone(self) -> Any:
        return self._cur.fetchone()

    def fetchall(self) -> list:
        return self._cur.fetchall()


class OpsConnProxy:
    """Proxy conn cho ops_disburse — sqlite3.Connection-like TRÊN conn gated (SAME tx)."""

    def __init__(self, pg_conn: Any) -> None:
        self._conn = pg_conn

    def execute(self, sql: str, params: tuple = ()) -> _OpsCursor:
        stripped = sql.strip().upper()
        if stripped.startswith("BEGIN"):  # BEGIN IMMEDIATE → no-op (gated đã mở tx + advisory-lock)
            return _OpsCursor(_NullCursor())
        pg_sql = _Q.sub("%s", sql)
        # RealDictCursor → row là mapping → LAB `dict(r)` + `r["col"]` hoạt động như sqlite3.Row
        # (KHÔNG phụ thuộc cursor_factory của conn gated — proxy tự đảm bảo mapping row).
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(pg_sql, params)
        except psycopg2.IntegrityError as e:  # UNIQUE/PK → LAB bắt sqlite3.IntegrityError (already_disbursed)
            cur.close()
            raise sqlite3.IntegrityError(str(e)) from e
        except psycopg2.Error as e:  # lock/khác → sqlite3.OperationalError (ledger_busy)
            cur.close()
            raise sqlite3.OperationalError(str(e)) from e
        return _OpsCursor(cur)

    def commit(self) -> None:  # gated sở hữu commit DUY NHẤT — no-op
        pass

    def rollback(self) -> None:  # gated sở hữu rollback DUY NHẤT — no-op
        pass


class _NullCursor:
    """Cursor rỗng cho câu no-op (BEGIN) — fetchone/all trả None/[] (LAB không fetch sau BEGIN)."""

    def fetchone(self) -> Any:
        return None

    def fetchall(self) -> list:
        return []


def run_ops_disburse(pg_conn: Any, **args: Any) -> dict[str, Any]:
    """Chạy LAB ops_disburse qua OpsConnProxy (SAME tx gated). Block/not-found → RAISE
    OpsDisburseBlocked (gated rollback → phiếu retryable). Success (found:True) → trả receipt."""
    from roles.operations.functions import ops_disburse

    proxy = OpsConnProxy(pg_conn)
    out = ops_disburse(proxy, **args)
    # KHÔNG giải ngân thật → RAISE (carry payload 4-field) để gated undo claim.
    # (1) block/param-sai: LAB đã trả 4-field {code,message,hint,retryable} → carry nguyên văn.
    if out.get("code") in _BLOCKED_CODES:
        raise OpsDisburseBlocked(out)
    # (2) app không tồn tại: LAB trả {found:False, hint} (KHÔNG có code/message/retryable) → CHUẨN HOÁ
    #     thành 4-field disburse_blocked để giữ hợp đồng envelope (agent luôn nhận đủ 4-field).
    if out.get("found") is False:
        raise OpsDisburseBlocked(
            {
                "code": "disburse_blocked",
                "message": "Không tìm thấy hồ sơ để giải ngân.",
                "hint": out.get("hint") or "Kiểm application_id.",
                "retryable": False,
                "blockers": ["application_not_found"],
            }
        )
    return out  # found:True + item.disbursementId — disbursement THẬT, để gated commit + save receipt
