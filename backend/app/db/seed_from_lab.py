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
# SNAPSHOT deploy (D-62): bản chụp trong repo — repo tự chứa seed khi VM clone-trần KHÔNG có LAB
# sibling. FALLBACK CHAIN: LAB path (dev — hành vi cũ) → snapshot (deploy tự rơi vào). 0 config.
SNAPSHOT_SEED_DB = REPO_ROOT / "deploy" / "seed" / "shb-132.db"


def _resolve_seed_db() -> Path:
    """LAB sibling path nếu tồn tại (dev — nguồn sự thật); else snapshot repo (deploy). D-62."""
    return LAB_SEED_DB if LAB_SEED_DB.exists() else SNAPSHOT_SEED_DB


# (table, columns) — cột KHỚP SQLite LAB, giữ đúng thứ tự cho INSERT positional (task T1-1 §A)
TABLES: list[tuple[str, list[str]]] = [
    # T7-1: +id_number/address (khách) + tax_code/address (DN) — trụ ①công an đối chiếu nhân thân
    # T12-5 FAIL B: +segment (mass|vip|staff) — product_suggest match theo phân khúc khách.
    (
        "customers",
        ["id", "full_name", "age", "occupation", "monthly_income", "region", "id_number", "address", "segment"],
    ),
    ("businesses", ["id", "name", "sector", "annual_revenue", "equity", "years_operating", "tax_code", "address"]),
    ("loans", ["loan_id", "owner_id", "principal", "outstanding", "monthly_payment", "status"]),
    ("collaterals", ["id", "owner_id", "type", "appraised_value", "docs_status"]),
    ("cic_records", ["owner_id", "cic_group", "history_note"]),
    ("assumptions", ["key", "value"]),
    # T12-5 FAIL B: products catalog (gói vay) — product_list/product_suggest. Cột khớp LAB shb-132.db.
    (
        "products",
        [
            "id",
            "name",
            "loan_type",
            "rate_annual",
            "term_max_months",
            "amount_min_vnd",
            "amount_max_vnd",
            "fee_pct",
            "income_min_vnd",
            "cic_max_group",
            "segment",
            "status",
            "note",
        ],
    ),
    # Legal tables (T2-2 — mount legal thật)
    ("legal_requirements", ["loan_type", "doc_code", "doc_name", "mandatory"]),
    ("owner_documents", ["owner_id", "doc_code", "status"]),
    ("collateral_legal", ["collateral_id", "dispute_status", "zoning_status", "note"]),
    ("restricted_purposes", ["purpose_code", "purpose_name", "restriction", "legal_basis"]),
    # Legal 3-trụ tables (T7-1 — mount legal đầy đủ; assessments = sổ GHI runtime → KHÔNG seed)
    (
        "police_records",
        ["owner_id", "id_number", "full_name", "address", "criminal_status", "record_type", "record_year", "notes"],
    ),
    (
        "employment_records",
        ["owner_id", "employer", "position", "tenure_months", "verified_income_vnd", "status", "verified_at"],
    ),
    # T12-2: 4 tầng retrieval (world 8bf6b4). Cột KHỚP migration d7f1a2c9e4b0 = LAB seed_retrieval.DDL.
    # embedding (BLOB→bytea) cần psycopg2.Binary — xem _row_values. note_id transfer THẬT (citation ổn).
    (
        "wiki_pages",
        [
            "id",
            "role",
            "title",
            "topic",
            "tags",
            "legal_basis",
            "effective_from",
            "effective_to",
            "status",
            "body",
            "source_file",
            "so_hieu",
            "dieu",
            "amended_by",
            "source_url",
            "crawled_at",
        ],
    ),
    ("wiki_links", ["from_page", "to_page"]),
    ("interaction_notes", ["note_id", "owner_id", "ts", "channel", "rm", "note_text", "embedding"]),
    ("party_relations", ["from_id", "to_id", "relation", "pct"]),
    # T12-3b: ops pipeline (world 8bf6b4). Cột KHỚP migration e8b3f5a1c920 = LAB shb-132.db.
    (
        "applications",
        [
            "id",
            "owner_id",
            "product_id",
            "loan_amount_vnd",
            "loan_type",
            "collateral_id",
            "status",
            "credit_ok",
            "legal_ok",
            "human_approval",
            "approval_ref",
            "created_at",
        ],
    ),
    (
        "disbursements",
        ["id", "application_id", "amount_vnd", "beneficiary", "status", "executed_at", "receipt_code"],
    ),
    ("procedure_steps", ["application_id", "step", "status", "done_at"]),
]


def _is_numeric(value: object) -> bool:
    """True nếu `value` parse được float — dùng lọc assumptions (D-28)."""
    try:
        float(value)  # type: ignore[arg-type]
        return True
    except (TypeError, ValueError):
        return False


# assumption key CHỮ mà legal-pack (T7-1) cần nạp — sau D-58 credit._assumptions graceful-skip
# string nên nạp AN TOÀN. Chỉ 2 key legal.py đọc (blocked_record_types qua _assumption_str +
# lane_policy_version qua _assumption_str). 4 key chữ còn lại (products/ops-pack) về khi mount
# pack đó — giữ scope T7-1 gọn (dispatch: "bỏ filter 2 key legal").
_LEGAL_STRING_KEYS = frozenset({"blocked_record_types", "lane_policy_version"})


def _filter_rows(table: str, cols: list[str], rows: list) -> list:
    """Lọc rows ngoài scope pack đã mount (D-28).

    `assumptions` trong seed LAB gộp value CHỮ (blocked_record_types, lane_policy_version,
    products_source...). Nạp dòng numeric + 2 key legal T7-1 cần; bỏ key chữ của pack chưa
    mount (products/ops) để giữ scope gọn. Sau D-58 (credit._assumptions re-sync LAB
    graceful-skip), string key KHÔNG còn làm credit_assess crash — nạp legal key an toàn.
    """
    if table == "assumptions":
        vcol = cols[cols.index("value")]
        kcol = cols[cols.index("key")]
        return [r for r in rows if _is_numeric(r[vcol]) or r[kcol] in _LEGAL_STRING_KEYS]
    return rows


def _row_values(cols: list[str], row: sqlite3.Row) -> tuple:
    """Giá trị positional cho INSERT. `embedding` (BLOB SQLite = bytes) → psycopg2.Binary cho bytea
    (T12-2 — không wrap thì psycopg2 vẫn adapt bytes nhưng Binary tường minh + None-safe). Cột khác
    nguyên giá trị."""
    out = []
    for c in cols:
        v = row[c]
        out.append(psycopg2.Binary(v) if c == "embedding" and v is not None else v)
    return tuple(out)


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


def load_seed(sqlite_path: Path | None = None, database_url: str = DATABASE_URL) -> dict[str, int]:
    """Đọc `sqlite_path`, ghi vào PG tại `database_url`. Trả {table: row_count} đã nạp.

    sqlite_path=None (mặc định) → resolve fallback chain D-62: LAB sibling → snapshot repo. Caller
    truyền path cụ thể vẫn tôn trọng (test/tool). Dev có LAB → hành vi cũ y nguyên."""
    if sqlite_path is None:
        sqlite_path = _resolve_seed_db()
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
                    values = [_row_values(cols, r) for r in rows]
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
