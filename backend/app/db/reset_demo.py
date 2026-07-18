"""Seed-reset 1 lệnh (demo-critical) — DB sạch để demo, giữ schema + seed nghiệp vụ gốc.

Chạy: `uv run python -m app.db.reset_demo`

XOÁ sạch VẬN HÀNH (BE ghi lúc chạy — tích tụ qua demo: phiếu pending, ca cũ, trace):
  conversations · messages · tasks · cards · approvals · tool_calls · assessments
  (assessments = sổ GHI của legal_classify_profile — runtime ledger như approvals, wipe khi reset)
GIỮ + RE-SEED NGHIỆP VỤ gốc (customers/loans/legal như đầu) qua load_seed() — loans.status về seed
(active) nên demo giải ngân lại được. GIỮ users (không xoá account demo).

Idempotent — chạy lại nhiều lần vẫn ra DB-demo-sạch. KHÔNG đụng migration (schema giữ nguyên).
KHÔNG đụng seed nghiệp vụ nguồn (load_seed đọc LAB read-only D-08).
"""

from __future__ import annotations

import logging
import shutil

import psycopg2

from app.db.config import DATABASE_URL
from app.db.seed_from_lab import load_seed

log = logging.getLogger("db.reset_demo")

# Bảng VẬN HÀNH — xoá sạch (tích tụ qua demo). Thứ tự không quan trọng (conv_id text mềm, không FK cứng
# D-31) nhưng để rõ: con trước cha. TRUNCATE CASCADE gọn + reset nhanh.
_RUNTIME_TABLES = ["assessments", "tool_calls", "cards", "approvals", "tasks", "messages", "conversations"]


def _wipe_conversation_dirs() -> int:
    """Xoá mọi dir con trong CONV_ROOT (data/conversations/<id>/), GIỮ CONV_ROOT. Trả số dir đã xoá.

    Best-effort: CONV_ROOT chưa tồn tại → 0 (không lỗi). Từng dir lỗi (đang mở/quyền) → log warning +
    bỏ qua, KHÔNG raise (reset không được crash vì 1 folder — DB đã sạch là chính)."""
    from app.orch.main_session import CONV_ROOT

    if not CONV_ROOT.exists():
        return 0
    removed = 0
    for child in CONV_ROOT.iterdir():
        if not child.is_dir():
            continue
        try:
            shutil.rmtree(child)
            removed += 1
        except OSError as e:  # đang mở/quyền/lock → bỏ qua, không crash reset
            log.warning("wipe conversation dir %s lỗi (bỏ qua): %s", child.name, e)
    return removed


def reset_demo(database_url: str = DATABASE_URL) -> dict[str, int]:
    """Xoá vận hành + re-seed nghiệp vụ. Trả {bảng: số row sau reset} để verify."""
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for table in _RUNTIME_TABLES:
                cur.execute(f"TRUNCATE TABLE {table} CASCADE")
    finally:
        conn.close()

    # RIDER T7-3: wipe folder neo cwd mồ côi (data/conversations/<id>/ — resume neo transcript ở đây;
    # conversations table đã wipe → neo mồ côi, user thấy folder rỗng tích tụ). rmtree từng dir con,
    # GIỮ CONV_ROOT. Lỗi 1 folder (đang mở/quyền) KHÔNG được crash reset (best-effort — DB đã sạch).
    dirs_wiped = _wipe_conversation_dirs()

    # re-seed nghiệp vụ (load_seed idempotent: TRUNCATE + INSERT business tables + loans.status gốc)
    seeded = load_seed()

    # verify: đếm row sau reset (vận hành = 0, nghiệp vụ = seed count)
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    out: dict[str, int] = {}
    try:
        with conn.cursor() as cur:
            for table in [*_RUNTIME_TABLES, "loans", "customers"]:
                cur.execute(f"SELECT count(*) FROM {table}")
                out[table] = cur.fetchone()[0]
    finally:
        conn.close()
    out["_seeded_business_rows"] = sum(seeded.values())
    out["_conversation_dirs_wiped"] = dirs_wiped
    return out


def _count_active_loans() -> int:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM loans WHERE status='active'")
            return cur.fetchone()[0]
    finally:
        conn.close()


if __name__ == "__main__":
    result = reset_demo()
    print("=== DEMO RESET xong ===")
    print(f"  vận hành xoá sạch: {', '.join(t + '=' + str(result[t]) for t in _RUNTIME_TABLES)}")
    print(
        f"  nghiệp vụ re-seed: loans={result['loans']} customers={result['customers']} "
        f"(business rows tổng={result['_seeded_business_rows']})"
    )
    print(f"  loans.status active (demo giải ngân lại được): {_count_active_loans()}")
