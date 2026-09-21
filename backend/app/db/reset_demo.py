from __future__ import annotations

import logging
import shutil

import psycopg2

from app.db.config import DATABASE_URL
from app.db.seed_from_lab import load_seed

log = logging.getLogger("db.reset_demo")


_RUNTIME_TABLES = [
    "shadow_reviews",
    "assessments",
    "tool_calls",
    "cards",
    "approvals",
    "tasks",
    "messages",
    "conversations",
    "conversation_groups",
]


def _wipe_conversation_dirs() -> int:

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
        except OSError as e:
            log.warning("failed to wipe conversation directory %s (ignored): %s", child.name, e)
    return removed


def reset_demo(database_url: str = DATABASE_URL) -> dict[str, int]:

    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for table in _RUNTIME_TABLES:
                cur.execute(f"TRUNCATE TABLE {table} CASCADE")
    finally:
        conn.close()

    dirs_wiped = _wipe_conversation_dirs()

    seeded = load_seed()

    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET owner_id=NULL WHERE owner_id LIKE 'C9%%'")
    finally:
        conn.close()

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
    print("=== DEMO RESET COMPLETE ===")
    print(f"  runtime data cleared: {', '.join(t + '=' + str(result[t]) for t in _RUNTIME_TABLES)}")
    print(
        f"  business data reseeded: loans={result['loans']} customers={result['customers']} "
        f"(total business rows={result['_seeded_business_rows']})"
    )
    print(f"  loans.status active (demo can be disbursed again): {_count_active_loans()}")
