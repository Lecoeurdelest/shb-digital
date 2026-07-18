"""seed_if_empty (D-62) — nạp seed nghiệp vụ CHỈ KHI DB rỗng (entrypoint deploy).

Gate S10 "session bền": restart container GIỮA ca → resume vẫn nhớ. seed-mỗi-start (TRUNCATE+
INSERT) wipe khách C9xx đã đăng ký + owner_id dangling = phá gate. → seed CHỈ khi DB chưa có
nghiệp vụ (check rẻ `count(assumptions)`). Migration `alembic upgrade head` vẫn LUÔN chạy (idempotent,
ngoài module này). Reset CHỦ ĐỘNG = `python -m app.db.reset_demo` trong container (không tự động).

Chạy: `uv run python -m app.db.seed_if_empty` (entrypoint compose sau migration).
"""

from __future__ import annotations

import logging

import psycopg2

from app.db.config import DATABASE_URL
from app.db.seed_from_lab import load_seed

log = logging.getLogger("db.seed_if_empty")


def _has_business_data(database_url: str = DATABASE_URL) -> bool:
    """True nếu DB đã có seed nghiệp vụ (assumptions > 0). DB lỗi/bảng thiếu → False (để seed thử)."""
    try:
        conn = psycopg2.connect(database_url)
    except psycopg2.Error as e:
        log.warning("seed_if_empty: DB chưa kết nối được (%s) — coi như rỗng", e)
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM assumptions")
            return cur.fetchone()[0] > 0
    except psycopg2.Error:
        return False  # bảng chưa có (migration chưa xong?) → coi như rỗng
    finally:
        conn.close()


def seed_if_empty(database_url: str = DATABASE_URL) -> bool:
    """Nạp seed CHỈ khi DB rỗng. Trả True = đã seed; False = skip (đã có data — giữ khách C9xx)."""
    if _has_business_data(database_url):
        log.info("seed_if_empty: DB đã có nghiệp vụ → SKIP seed (giữ khách đăng ký, gate session-bền)")
        return False
    log.info("seed_if_empty: DB rỗng → nạp seed từ nguồn (LAB sibling hoặc snapshot D-62)")
    load_seed(database_url=database_url)
    return True


if __name__ == "__main__":
    seeded = seed_if_empty()
    print("seeded" if seeded else "skipped (DB đã có nghiệp vụ)")
