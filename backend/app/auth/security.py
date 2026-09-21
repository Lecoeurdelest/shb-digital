from __future__ import annotations

import datetime as dt
from typing import Any

import bcrypt
import jwt

from app.config import JWT_ALG, JWT_SECRET, JWT_TTL_SECONDS
from app.tenancy import DEFAULT_TENANT_ID


def hash_password(plain: str) -> str:

    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:

    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def make_token(*, user_id: str, username: str, role: str, tenant_id: str = DEFAULT_TENANT_ID) -> str:

    now = dt.datetime.now(dt.UTC)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + dt.timedelta(seconds=JWT_TTL_SECONDS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict[str, Any] | None:

    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.InvalidTokenError:
        return None
