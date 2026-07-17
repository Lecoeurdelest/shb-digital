"""Primitive bảo mật auth: hash mật khẩu (bcrypt) + JWT encode/decode (PyJWT).

Thuần — không biết HTTP/DB. router/service gọi. bcrypt tự salt; JWT HS256 secret từ config.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import bcrypt
import jwt

from app.config import JWT_ALG, JWT_SECRET, JWT_TTL_SECONDS


def hash_password(plain: str) -> str:
    """bcrypt hash (tự sinh salt). Trả str để lưu cột pass_hash."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """So mật khẩu với hash. False (không raise) khi hash hỏng — sai credential là 401 bình thường."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def make_token(*, user_id: str, username: str, role: str) -> str:
    """JWT HS256: sub=user_id, kèm username+role, exp theo TTL."""
    now = dt.datetime.now(dt.UTC)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + dt.timedelta(seconds=JWT_TTL_SECONDS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict[str, Any] | None:
    """Giải mã + verify. Trả claims dict, hoặc None nếu hỏng/hết hạn (caller → 401)."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.InvalidTokenError:
        return None
