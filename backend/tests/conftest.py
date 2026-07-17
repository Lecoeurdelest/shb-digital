"""Fixtures chung — kết nối PG seed thật (D-25: DATABASE_URL). Skip nếu DB không sẵn."""

from __future__ import annotations

import psycopg2
import pytest

from app.db.config import DATABASE_URL


def _db_ready() -> bool:
    """True nếu PG chạy + đã seed (assumptions có dòng). Tránh test đỏ oan khi quên up db/seed."""
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=2)
    except psycopg2.Error:
        return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM assumptions")
        n = cur.fetchone()[0]
        cur.close()
        return n > 0
    except psycopg2.Error:
        return False
    finally:
        conn.close()


requires_db = pytest.mark.skipif(
    not _db_ready(),
    reason="PG chưa sẵn/chưa seed — `docker compose up -d db` + "
    "`uv run alembic upgrade head` + `uv run python -m app.db.seed_from_lab`",
)


@pytest.fixture
def pg_conn():
    """1 psycopg2 conn tươi mỗi test; rollback + close cuối test."""
    conn = psycopg2.connect(DATABASE_URL)
    yield conn
    conn.rollback()
    conn.close()
