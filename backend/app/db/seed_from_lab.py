from __future__ import annotations

import sqlite3
from pathlib import Path

import psycopg2

from app.db.config import DATABASE_URL

REPO_ROOT = Path(__file__).resolve().parents[3]
LAB_SEED_DB = REPO_ROOT.parent / "shb-digital-experts" / "missions" / "shb-132" / "seed" / "shb-132.db"


SNAPSHOT_SEED_DB = REPO_ROOT / "deploy" / "seed" / "shb-132.db"


def _resolve_seed_db() -> Path:

    return LAB_SEED_DB if LAB_SEED_DB.exists() else SNAPSHOT_SEED_DB


TABLES: list[tuple[str, list[str]]] = [
    (
        "customers",
        ["id", "full_name", "age", "occupation", "monthly_income", "region", "id_number", "address", "segment"],
    ),
    ("businesses", ["id", "name", "sector", "annual_revenue", "equity", "years_operating", "tax_code", "address"]),
    ("loans", ["loan_id", "owner_id", "principal", "outstanding", "monthly_payment", "status"]),
    ("collaterals", ["id", "owner_id", "type", "appraised_value", "docs_status"]),
    ("cic_records", ["owner_id", "cic_group", "history_note"]),
    ("assumptions", ["key", "value"]),
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
    ("legal_requirements", ["loan_type", "doc_code", "doc_name", "mandatory"]),
    ("owner_documents", ["owner_id", "doc_code", "status"]),
    ("collateral_legal", ["collateral_id", "dispute_status", "zoning_status", "note"]),
    ("restricted_purposes", ["purpose_code", "purpose_name", "restriction", "legal_basis"]),
    (
        "police_records",
        ["owner_id", "id_number", "full_name", "address", "criminal_status", "record_type", "record_year", "notes"],
    ),
    (
        "employment_records",
        ["owner_id", "employer", "position", "tenure_months", "verified_income_vnd", "status", "verified_at"],
    ),
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

    try:
        float(value)  # type: ignore[arg-type]
        return True
    except (TypeError, ValueError):
        return False


_LEGAL_STRING_KEYS = frozenset({"blocked_record_types", "lane_policy_version"})


def _filter_rows(table: str, cols: list[str], rows: list) -> list:

    if table == "assumptions":
        vcol = cols[cols.index("value")]
        kcol = cols[cols.index("key")]
        return [r for r in rows if _is_numeric(r[vcol]) or r[kcol] in _LEGAL_STRING_KEYS]
    return rows


def _row_values(cols: list[str], row: sqlite3.Row) -> tuple:

    out = []
    for c in cols:
        v = row[c]
        out.append(psycopg2.Binary(v) if c == "embedding" and v is not None else v)
    return tuple(out)


def _open_sqlite(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(
            f"The LAB SQLite seed does not exist at '{path}'. "
            "Check whether ../shb-digital-experts is checked out beside this repository (DECISIONS D-08). "
            "Do not invent seed data; notify the team lead if the source is unavailable."
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_seed(sqlite_path: Path | None = None, database_url: str = DATABASE_URL) -> dict[str, int]:

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
                rows = _filter_rows(table, cols, rows)
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
