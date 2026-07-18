"""Verdict-aware disburse decision (T7-3, D-52/D-56) — ĐỌC sổ assessments → MA TRẬN 3 TẦNG.

Tách khỏi gated.py (chuẩn PROD ≤400 LOC + "query verdict = helper riêng"). gated._gated_txn gọi
`disburse_decision(conn, args)` ở nhánh 4a thay điều kiện auto cũ — cấu trúc phanh (4-step tx +
advisory lock) KHÔNG đổi, CHỈ điều kiện auto thành verdict-aware.

BACKWARD KEY: assessments RỖNG/không-verdict → hành vi Y HỆT T5-2' cũ (tầng-1 auto, tầng-2/3 người).
"""

from __future__ import annotations

import logging
from typing import Any

import psycopg2
import psycopg2.extras

from app.db.config import DATABASE_URL

log = logging.getLogger("orch.verdict")

# Ngưỡng dưới (T5-2' D-52): amount < mức này → tầng 1 (auto có kiểm soát). Đảo được (đổi số).
AUTO_APPROVE_THRESHOLD = 500_000_000  # VND
_AUTO_MAX_FALLBACK = 2_000_000_000.0  # assumptions.auto_approve_max_vnd thiếu → fallback 2e9


def auto_approve_max(conn: Any) -> float:
    """Ngưỡng trên tầng-2 = assumptions.auto_approve_max_vnd (2e9). Thiếu/lỗi → fallback 2e9
    (KHÔNG nới auto ngoài ý định). conn = gated conn (SELECT read-only, cùng tx an toàn)."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM assumptions WHERE key='auto_approve_max_vnd'")
            row = cur.fetchone()
            if row and row[0] is not None:
                return float(row[0])
    except (psycopg2.Error, TypeError, ValueError) as e:
        log.warning("đọc auto_approve_max_vnd lỗi (fallback 2e9): %s", e)
    return _AUTO_MAX_FALLBACK


def latest_verdict(loan_id: str) -> dict[str, Any] | None:
    """Assessment MỚI NHẤT theo owner (loans.loan_id → owner_id → assessments) → {id, lane}
    hoặc None (không loan/owner/assessment/DB lỗi).

    D-59 (T7-3): assessments GHI 'lane' KHÔNG ghi 'decision' (LAB legal.py:337 chỉ INSERT lane —
    T7-2 byte-identical, KHÔNG được thêm cột decision = phá N1). decision suy từ lane + tầng số
    tiền disburse (xem disburse_decision). SELECT chỉ id, lane.

    CONN RIÊNG ngắn (advisor T7-3): đọc verdict trên conn TÁCH khỏi gated tx — đọc lỗi trên conn
    gated thì tx bị abort → INSERT phiếu-người sau đó nổ InFailedSqlTransaction, phá đúng nhánh
    'DB lỗi → về người'. assessments = data commit độc lập, không thuộc write-set disburse. Match
    theo owner mới-nhất (known-limitation demo-grade: KHÔNG đối chiếu số tiền ca — D-52 note)."""
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT owner_id FROM loans WHERE loan_id=%s", (loan_id,))
            lrow = cur.fetchone()
            if not lrow or not lrow["owner_id"]:
                return None
            cur.execute(
                "SELECT id, lane FROM assessments WHERE owner_id=%s ORDER BY created_at DESC, id DESC LIMIT 1",
                (lrow["owner_id"],),
            )
            arow = cur.fetchone()
            return dict(arow) if arow else None
    except psycopg2.Error as e:
        log.warning("đọc verdict assessment lỗi loan=%s (coi như không verdict): %s", loan_id, e)
        return None
    finally:
        if conn is not None:
            conn.close()


def disburse_decision(conn: Any, args: dict[str, Any]) -> tuple[str, str | None]:
    """MA TRẬN 3 TẦNG (D-52/D-56) — trả ('auto', reason) hoặc ('human', None).

    - Tầng 1 (amount < AUTO_APPROVE_THRESHOLD): auto NHƯ CŨ, TRỪ KHI verdict xấu (lane=red HOẶC
      decision=reject_recommended) → thắt về người (có bằng chứng xấu).
    - Tầng 2 (THRESHOLD ≤ amount ≤ auto_max): auto CHỈ KHI verdict lane=green VÀ
      decision=auto_approve_eligible; else người (pain D-52 — hồ sơ XANH agent tự duyệt).
    - Tầng 3 (amount > auto_max): LUÔN người.
    assessments RỖNG/không-verdict → Y HỆT T5-2' cũ. amount thiếu/không parse → ('human', None)."""
    try:
        amount = float(args.get("amount"))
    except (TypeError, ValueError):
        return ("human", None)

    loan_id = args.get("loan_id")
    verdict = latest_verdict(loan_id) if loan_id else None
    lane = verdict.get("lane") if verdict else None
    # D-59: decision suy từ lane (LAB mapping xác định, không lưu cột decision — xem latest_verdict).
    # bad ⟺ lane=red: decision=reject_recommended ⟺ lane=red trong LAB (amount-independent).
    # green (trong nhánh tầng-2) ⟺ lane=green: decision=auto_approve_eligible ⟺ lane=green ∧
    # amount≤auto_max — mà tầng-2 ĐÃ gate amount≤auto_max → recompute decision theo số tiền DISBURSE
    # (không phải số tiền classify lưu — nhất quán known-limitation 'match owner, amount-mismatch').
    bad = lane == "red"

    if amount < AUTO_APPROVE_THRESHOLD:
        if bad:
            return ("human", None)  # thắt chặt: verdict xấu (red) chặn auto tầng-1
        return ("auto", f"Tự động duyệt theo rule: số tiền dưới ngưỡng {AUTO_APPROVE_THRESHOLD:,} VND")

    if amount <= auto_approve_max(conn):
        if lane == "green":  # tầng-2 ĐÃ gate amount≤auto_max → lane=green ⟺ auto_approve_eligible
            return ("auto", f"Hồ sơ XANH — assessment #{verdict['id']} (lane green, auto_approve_eligible)")
        return ("human", None)

    return ("human", None)  # tầng 3 — trên ngưỡng trên, luôn người
