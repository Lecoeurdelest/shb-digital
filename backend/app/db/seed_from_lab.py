"""Load seed VALUES từ SQLite LAB sang PG (DECISIONS D-21 — load-values, KHÔNG bịa số).
Nguồn: ../shb-digital-experts/missions/shb-132/seed/shb-132.db (READ-ONLY, D-08).
Chạy SAU migration: `uv run python -m app.db.seed_from_lab`.

Idempotent: TRUNCATE rồi INSERT — chạy lại nhiều lần vẫn ra đúng 1 bộ số.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import psycopg2

from app.db.config import DATABASE_URL

# repo root = 2 cấp lên từ backend/app/db/ ; LAB nằm cạnh repo (D-08)
REPO_ROOT = Path(__file__).resolve().parents[3]
LAB_SEED_DB = REPO_ROOT.parent / "shb-digital-experts" / "missions" / "shb-132" / "seed" / "shb-132.db"

# (table, columns) — cột KHỚP SQLite LAB, giữ đúng thứ tự cho INSERT positional (task T1-1 §A)
TABLES: list[tuple[str, list[str]]] = [
    ("customers", ["id", "full_name", "age", "occupation", "monthly_income", "region"]),
    ("businesses", ["id", "name", "sector", "annual_revenue", "equity", "years_operating"]),
    ("loans", ["loan_id", "owner_id", "principal", "outstanding", "monthly_payment", "status"]),
    ("collaterals", ["id", "owner_id", "type", "appraised_value", "docs_status"]),
    ("cic_records", ["owner_id", "cic_group", "history_note"]),
    ("assumptions", ["key", "value"]),
    # Legal tables (T2-2 — mount legal thật)
    ("legal_requirements", ["loan_type", "doc_code", "doc_name", "mandatory"]),
    ("owner_documents", ["owner_id", "doc_code", "status"]),
    ("collateral_legal", ["collateral_id", "dispute_status", "zoning_status", "note"]),
    ("restricted_purposes", ["purpose_code", "purpose_name", "restriction", "legal_basis"]),
]


def _is_numeric(value: object) -> bool:
    """True nếu `value` parse được float — dùng lọc assumptions (D-28)."""
    try:
        float(value)  # type: ignore[arg-type]
        return True
    except (TypeError, ValueError):
        return False


def _filter_rows(table: str, cols: list[str], rows: list) -> list:
    """Lọc rows ngoài scope credit S1 (D-28).

    `assumptions` trong seed LAB gộp cả assumption của role LEGAL — dòng
    `legal_docs_source='gia-thuyet-lab'` có `value` là CHỮ, không phải số. S1 chỉ mount
    credit; credit.py::_assumptions làm `float(r[1])` trên MỌI dòng (chỉ except sqlite3.Error,
    KHÔNG bắt ValueError) → dòng chữ làm credit_assess CRASH. Nạp chỉ dòng `value` numeric
    = N1-sạch (KHÔNG sửa credit.py — giữ D-27). Dòng legal về khi mount legal (sprint sau).
    """
    if table == "assumptions":
        vi = cols.index("value")
        return [r for r in rows if _is_numeric(r[cols[vi]])]
    return rows


def _open_sqlite(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(
            f"Seed SQLite LAB không tồn tại tại '{path}'. "
            "Kiểm ../shb-digital-experts đã checkout cạnh repo này chưa (DECISIONS D-08). "
            "KHÔNG tự chế seed — báo team-lead nếu nguồn vắng."
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_seed(sqlite_path: Path = LAB_SEED_DB, database_url: str = DATABASE_URL) -> dict[str, int]:
    """Đọc `sqlite_path`, ghi vào PG tại `database_url`. Trả {table: row_count} đã nạp."""
    sconn = _open_sqlite(sqlite_path)
    pconn = psycopg2.connect(database_url)
    counts: dict[str, int] = {}
    try:
        with pconn.cursor() as pcur:
            for table, cols in TABLES:
                col_list = ", ".join(cols)
                placeholders = ", ".join(["%s"] * len(cols))
                rows = sconn.execute(f"SELECT {col_list} FROM {table}").fetchall()
                rows = _filter_rows(table, cols, rows)  # D-28: bỏ assumptions non-numeric
                pcur.execute(f"TRUNCATE TABLE {table} CASCADE")
                if rows:
                    values = [tuple(r[c] for c in cols) for r in rows]
                    pcur.executemany(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})", values)
                counts[table] = len(rows)
        pconn.commit()
    except Exception:
        pconn.rollback()
        raise
    finally:
        pconn.close()
        sconn.close()
    return counts


if __name__ == "__main__":
    result = load_seed()
    for table, n in result.items():
        print(f"{table}: {n} rows loaded")
