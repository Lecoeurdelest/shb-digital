"""Seed account demo (D-19 · SPEC §11 · D-56 persona khách): user/admin (NGÂN HÀNG) + c001/b001 (KHÁCH).

Chạy sau migration: `uv run python -m app.db.seed_users`.
Idempotent: ON CONFLICT (username) DO NOTHING — chạy lại không đổi pass đã có.
Password demo = username — on-premise demo; PROD đổi qua env sau.
D-56: account NGÂN HÀNG (admin/user) owner_id=NULL; account KHÁCH (customer) owner_id map → customers/businesses.
"""

from __future__ import annotations

import os

import psycopg2

from app.auth.security import hash_password
from app.db.config import DATABASE_URL

# (username, password, role, owner_id). Password demo = username; owner_id: bank=None, khách=mã owner.
SEED_ACCOUNTS = [
    ("user", os.environ.get("SEED_USER_PASSWORD", "user"), "user", None),  # NGÂN HÀNG (RM)
    ("admin", os.environ.get("SEED_ADMIN_PASSWORD", "admin"), "admin", None),  # NGÂN HÀNG (quản lý)
    ("c001", os.environ.get("SEED_C001_PASSWORD", "c001"), "customer", "C001"),  # KHÁCH cá nhân → C001
    ("b001", os.environ.get("SEED_B001_PASSWORD", "b001"), "customer", "B001"),  # KHÁCH DN → B001
    # T7-4: KHÁCH C019 (Huỳnh Văn Phong) — lane-green cả 300/700tr + loan L108 594tr active =
    # tổ hợp DUY NHẤT cho cảnh demo "hồ sơ XANH tự duyệt TRÊN ngưỡng" (c001/C001 yellow = tương phản).
    ("c019", os.environ.get("SEED_C019_PASSWORD", "c019"), "customer", "C019"),
]


def seed_users(database_url: str = DATABASE_URL) -> dict[str, str]:
    """Insert account (idempotent). Trả {username: role} đã đảm bảo tồn tại. owner_id set cho khách."""
    conn = psycopg2.connect(database_url)
    out: dict[str, str] = {}
    try:
        with conn.cursor() as cur:
            for username, password, role, owner_id in SEED_ACCOUNTS:
                cur.execute(
                    "INSERT INTO users (username, pass_hash, role, owner_id) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (username) DO NOTHING",
                    (username, hash_password(password), role, owner_id),
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
