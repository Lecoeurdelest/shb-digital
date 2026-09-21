from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

from app.auth.security import make_token, verify_password
from app.storage import connect_core


def _get_user_by_username(username: str) -> dict[str, Any] | None:
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, username, pass_hash, role, tenant_id FROM users WHERE username=%s",
                (username,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def authenticate(username: str, password: str) -> dict[str, Any] | None:

    user = _get_user_by_username(username)

    stored_hash = (user["pass_hash"] or "") if user else ""
    if not verify_password(password, stored_hash) or user is None:
        return None
    tenant_id = str(user["tenant_id"])
    token = make_token(user_id=str(user["id"]), username=user["username"], role=user["role"], tenant_id=tenant_id)
    return {
        "token": token,
        "user": {"username": user["username"], "role": user["role"], "tenant_id": tenant_id},
    }


class UsernameTaken(Exception):
    pass


def register(username: str, password: str, email: str | None = None) -> dict[str, Any]:

    from app.auth.security import hash_password

    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO users (username, pass_hash, role, owner_id, email) "
                "VALUES (%s, %s, 'customer', NULL, %s) ON CONFLICT (username) DO NOTHING "
                "RETURNING id, username, role, tenant_id",
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
    tenant_id = str(row["tenant_id"])
    token = make_token(user_id=str(row["id"]), username=row["username"], role=row["role"], tenant_id=tenant_id)
    return {
        "token": token,
        "user": {"username": row["username"], "role": row["role"], "tenant_id": tenant_id},
    }
