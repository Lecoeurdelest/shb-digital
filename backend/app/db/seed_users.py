"""Seed 2 account demo (D-19 · SPEC §11): user (RM) · admin (quản lý/compliance).

Chạy sau migration: `uv run python -m app.db.seed_users`.
Idempotent: ON CONFLICT (username) DO NOTHING — chạy lại không đổi pass đã có.
Password demo = username (user/user, admin/admin) — on-premise demo; PROD đổi qua env sau.
"""

from __future__ import annotations

import os

import psycopg2

from app.auth.security import hash_password
from app.db.config import DATABASE_URL

# (username, password, role). Password demo = username; override qua env cho PROD.
SEED_ACCOUNTS = [
    ("user", os.environ.get("SEED_USER_PASSWORD", "user"), "user"),
    ("admin", os.environ.get("SEED_ADMIN_PASSWORD", "admin"), "admin"),
]


def seed_users(database_url: str = DATABASE_URL) -> dict[str, str]:
    """Insert 2 account (idempotent). Trả {username: role} đã đảm bảo tồn tại."""
    conn = psycopg2.connect(database_url)
    out: dict[str, str] = {}
    try:
        with conn.cursor() as cur:
            for username, password, role in SEED_ACCOUNTS:
                cur.execute(
                    "INSERT INTO users (username, pass_hash, role) VALUES (%s, %s, %s) "
                    "ON CONFLICT (username) DO NOTHING",
                    (username, hash_password(password), role),
                )
                out[username] = role
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return out


if __name__ == "__main__":
    result = seed_users()
    for username, role in result.items():
        print(f"user seeded: {username} ({role})")
