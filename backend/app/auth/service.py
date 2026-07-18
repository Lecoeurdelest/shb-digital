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
    # pass_hash NULL = account Google-only (không mật khẩu) → so trên "" → 401 bình thường, không 500
    stored_hash = (user["pass_hash"] or "") if user else ""
    if not verify_password(password, stored_hash) or user is None:
        return None
    token = make_token(user_id=str(user["id"]), username=user["username"], role=user["role"])
    return {"token": token, "user": {"username": user["username"], "role": user["role"]}}
