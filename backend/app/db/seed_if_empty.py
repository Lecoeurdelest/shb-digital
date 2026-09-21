from __future__ import annotations

import logging

import psycopg2

from app.db.config import DATABASE_URL
from app.db.seed_from_lab import load_seed
from app.runtime_security import validate_runtime_security

log = logging.getLogger("db.seed_if_empty")


def _has_business_data(database_url: str = DATABASE_URL) -> bool:

    try:
        conn = psycopg2.connect(database_url)
    except psycopg2.Error as e:
        log.warning("seed_if_empty: database connection failed (%s); treating it as empty", e)
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM assumptions")
            return cur.fetchone()[0] > 0
    except psycopg2.Error:
        return False
    finally:
        conn.close()


def seed_if_empty(database_url: str = DATABASE_URL) -> bool:

    validate_runtime_security()
    if _has_business_data(database_url):
        log.info("seed_if_empty: business data exists; skipping seed to preserve registered users and durable sessions")
        return False
    log.info("seed_if_empty: database is empty; loading seed data from the LAB sibling or D-62 snapshot")
    load_seed(database_url=database_url)
    return True


if __name__ == "__main__":
    seeded = seed_if_empty()
    print("seeded" if seeded else "skipped (business data already exists)")
