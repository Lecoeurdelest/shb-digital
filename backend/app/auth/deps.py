from __future__ import annotations

import logging
from typing import Any

from fastapi import Request

from app.auth.security import decode_token
from app.config import AUTH_COOKIE, DEV_ADMIN_CLAIMS, DEV_SKIP_AUTH
from app.errors import ApiError
from app.storage import connect_core
from app.tenancy import DEFAULT_TENANT_ID

log = logging.getLogger("auth")


_dev_admin_sub: str | None = None


def _dev_admin_claims() -> dict[str, Any]:

    global _dev_admin_sub
    if _dev_admin_sub is None:
        try:
            conn = connect_core()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users WHERE username='admin' LIMIT 1")
                    row = cur.fetchone()
                    _dev_admin_sub = str(row[0]) if row else "dev-admin"
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            _dev_admin_sub = "dev-admin"
    return {**DEV_ADMIN_CLAIMS, "sub": _dev_admin_sub, "tenant_id": DEFAULT_TENANT_ID}


def _with_tenant_context(claims: dict[str, Any]) -> dict[str, Any]:
    """Resolve legacy JWTs that predate D-79 from the user row; never guess another tenant."""
    if claims.get("tenant_id"):
        return claims
    sub, username = claims.get("sub"), claims.get("username")
    if not sub or not username:
        raise ApiError(
            401,
            "tenant_context_missing",
            "The session is missing its tenant scope.",
            "Sign in again to refresh the session.",
            retryable=False,
        )
    try:
        conn = connect_core()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id FROM users WHERE id::text=%s AND username=%s",
                    (sub, username),
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        log.warning("failed to resolve tenant for legacy token: %s", type(exc).__name__)
        row = None
    if row is None:
        raise ApiError(
            401,
            "tenant_context_missing",
            "The session tenant scope could not be determined.",
            "Sign in again or contact an administrator.",
            retryable=False,
        )
    return {**claims, "tenant_id": str(row[0])}


def _claims_from_request(request: Request) -> dict[str, Any]:

    if DEV_SKIP_AUTH:
        return _dev_admin_claims()
    token = request.cookies.get(AUTH_COOKIE)

    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    claims = decode_token(token) if token else None
    if claims is None:
        raise ApiError(
            status_code=401,
            code="unauthorized",
            message="The user is not signed in or the session has expired.",
            hint="Sign in again through POST /api/auth/login.",
            retryable=False,
        )
    return _with_tenant_context(claims)


def require_user(request: Request) -> dict[str, Any]:

    return _claims_from_request(request)


def require_admin(request: Request) -> dict[str, Any]:

    claims = _claims_from_request(request)
    if claims.get("role") != "admin":
        raise ApiError(
            status_code=403,
            code="forbidden",
            message="Only managers may perform this action.",
            hint="Manager permissions are required.",
            retryable=False,
        )
    return claims


def can_access_conv(conv: dict[str, Any], claims: dict[str, Any]) -> bool:

    if str(conv.get("tenant_id")) != str(claims.get("tenant_id")):
        return False
    return claims.get("role") == "admin" or conv.get("user_id") == claims.get("username")
