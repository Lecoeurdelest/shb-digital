"""Auth service — business logic đăng nhập. KHÔNG biết HTTP (router lo), KHÔNG biết JWT shape
(security.py lo). Query users qua psycopg2 (nhất quán seed_from_lab; S1 chưa cần SQLAlchemy session)."""

from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

from app.auth.security import make_token, verify_password
from app.db.config import DATABASE_URL


def _get_user_by_username(username: str) -> dict[str, Any] | None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, username, pass_hash, role FROM users WHERE username=%s",
                (username,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    """Trả {token, user:{username, role}} khi credential đúng; None khi sai (router → 401).

    So mật khẩu bằng bcrypt (không lộ user-có-tồn-tại-hay-không qua timing khác biệt lớn —
    verify_password vẫn chạy trên hash rỗng nếu user vắng để giảm chênh timing)."""
    user = _get_user_by_username(username)
    stored_hash = user["pass_hash"] if user else ""
    if not verify_password(password, stored_hash) or user is None:
        return None
    token = make_token(user_id=str(user["id"]), username=user["username"], role=user["role"])
    return {"token": token, "user": {"username": user["username"], "role": user["role"]}}


class UsernameTaken(Exception):
    """username đã tồn tại — router map 409 (message chung, không lộ user-nào-tồn-tại kiểu khác)."""


def register(username: str, password: str, email: str | None = None) -> dict[str, Any]:
    """Đăng ký KHÁCH MỚI (D-57): INSERT users role='customer', owner_id=NULL (chưa có hồ sơ →
    form intake tạo sau). Auto-login: trả {token, user} y login (đỡ 1 bước UX). username trùng →
    UsernameTaken (router 409). Validate format ở router (tầng HTTP) — service lo persist + token."""
    from app.auth.security import hash_password

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # INSERT … ON CONFLICT DO NOTHING RETURNING → rowcount 0 = username trùng (atomic, không
            # race check-then-insert). role='customer' owner_id NULL (chưa hồ sơ). email nullable.
            cur.execute(
                "INSERT INTO users (username, pass_hash, role, owner_id, email) "
                "VALUES (%s, %s, 'customer', NULL, %s) ON CONFLICT (username) DO NOTHING "
                "RETURNING id, username, role",
                (username, hash_password(password), email),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if row is None:
        raise UsernameTaken(username)
    token = make_token(user_id=str(row["id"]), username=row["username"], role=row["role"])
    return {"token": token, "user": {"username": row["username"], "role": row["role"]}}
