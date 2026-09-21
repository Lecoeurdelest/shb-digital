from __future__ import annotations

import re
import secrets
from urllib.parse import unquote, urlencode, urlsplit

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app import config
from app.auth import google as google_oauth
from app.auth.deps import require_user
from app.auth.security import make_token
from app.auth.service import UsernameTaken, authenticate, register
from app.config import AUTH_COOKIE, JWT_TTL_SECONDS
from app.errors import ApiError
from app.storage import connect_core
from app.tenancy import DEFAULT_TENANT_ID

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

router = APIRouter(prefix="/api/auth", tags=["auth"])

me_router = APIRouter(prefix="/api", tags=["me"])


class LoginBody(BaseModel):
    username: str
    password: str


class RegisterBody(BaseModel):
    username: str
    password: str
    email: str | None = None


def _set_auth_cookie(response: Response, token: str) -> None:

    response.set_cookie(
        key=AUTH_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=JWT_TTL_SECONDS,
        secure=config.COOKIE_SECURE,
    )


@router.post("/logout")
def logout(response: Response) -> dict:

    response.delete_cookie(
        key=AUTH_COOKIE,
        path="/",
        samesite="lax",
        secure=config.COOKIE_SECURE,
        httponly=True,
    )
    return {"ok": True}


@router.post("/login")
def login(body: LoginBody, response: Response) -> dict:

    result = authenticate(body.username, body.password)
    if result is None:
        raise ApiError(
            status_code=401,
            code="unauthorized",
            message="Incorrect username or password.",
            hint="Check the login credentials.",
            retryable=True,
        )
    _set_auth_cookie(response, result["token"])

    return result


_STATE_COOKIE = "oauth_state"
_NEXT_COOKIE = "oauth_next"


def _safe_oauth_next(value: str | None) -> str | None:

    if not value or len(value) > 2048 or not value.startswith("/") or value.startswith("//"):
        return None
    decoded = unquote(value)
    if decoded.startswith("//") or "\\" in decoded or any(ord(char) < 32 for char in decoded):
        return None
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return None
    return value


@router.get("/providers")
def providers() -> dict:

    return {"password": True, "google": google_oauth.is_configured()}


@router.get("/google/start")
def google_start(next: str | None = None) -> RedirectResponse:

    if not google_oauth.is_configured():
        raise ApiError(
            status_code=503,
            code="auth_provider_disabled",
            message="Google sign-in is not enabled on this server.",
            hint="Set AUTH_GOOGLE_ENABLED=1 and GOOGLE_OAUTH_CLIENT_ID/SECRET, then restart the server.",
            retryable=False,
        )
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": config.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    resp = RedirectResponse(f"{google_oauth.GOOGLE_AUTH_URL}?{urlencode(params)}")
    resp.set_cookie(_STATE_COOKIE, state, httponly=True, samesite="lax", max_age=600, secure=config.COOKIE_SECURE)
    safe_next = _safe_oauth_next(next)
    if safe_next is not None:
        resp.set_cookie(
            _NEXT_COOKIE,
            safe_next,
            httponly=True,
            samesite="lax",
            max_age=600,
            secure=config.COOKIE_SECURE,
        )
    else:
        resp.delete_cookie(_NEXT_COOKIE)
    return resp


@router.get("/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None) -> RedirectResponse:

    if not google_oauth.is_configured():
        raise ApiError(
            status_code=503,
            code="auth_provider_disabled",
            message="Google sign-in is not enabled on this server.",
            hint="Set AUTH_GOOGLE_ENABLED=1 and GOOGLE_OAUTH_CLIENT_ID/SECRET, then restart the server.",
            retryable=False,
        )
    if not code or not state:
        raise ApiError(
            status_code=400,
            code="oauth_malformed",
            message="The Google code or state is missing.",
            hint="Start again from /api/auth/google/start.",
            retryable=True,
        )
    if request.cookies.get(_STATE_COOKIE) != state:
        raise ApiError(
            status_code=400,
            code="oauth_state_mismatch",
            message="The state does not match; this may indicate CSRF or an expired cookie (10 minutes).",
            hint="Start again from /api/auth/google/start.",
            retryable=True,
        )
    try:
        access = google_oauth.exchange_code(code)
        info = google_oauth.fetch_userinfo(access)
    except google_oauth.GoogleOAuthError as e:
        raise ApiError(
            status_code=502,
            code="oauth_google_failed",
            message=f"Google rejected the sign-in attempt: {e}",
            hint="Try again; if the issue persists, verify client_id, secret, and redirect_uri in Google Console.",
            retryable=True,
        ) from e
    user = google_oauth.upsert_google_user(google_sub=info["sub"], email=info["email"])
    tenant_id = str(user.get("tenant_id") or DEFAULT_TENANT_ID)
    token = make_token(user_id=str(user["id"]), username=user["username"], role=user["role"], tenant_id=tenant_id)
    safe_next = _safe_oauth_next(request.cookies.get(_NEXT_COOKIE))
    destination = config.FRONTEND_URL.rstrip("/") + safe_next if safe_next is not None else config.FRONTEND_URL
    resp = RedirectResponse(destination)
    resp.set_cookie(
        key=AUTH_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=JWT_TTL_SECONDS,
        secure=config.COOKIE_SECURE,
    )
    resp.delete_cookie(_STATE_COOKIE)
    resp.delete_cookie(_NEXT_COOKIE)
    return resp


@router.post("/register", status_code=201)
def register_endpoint(body: RegisterBody, response: Response) -> dict:

    username = (body.username or "").strip()
    if not (3 <= len(username) <= 32):
        raise ApiError(
            400, "bad_username", "The username must be 3-32 characters.", "Choose another username.", retryable=False
        )
    if len(body.password or "") < 4:
        raise ApiError(
            400,
            "bad_password",
            "The password must be at least 4 characters.",
            "Choose a longer password.",
            retryable=False,
        )
    if body.email and not _EMAIL_RE.match(body.email):
        raise ApiError(
            400, "bad_email", "The email address is invalid.", "Use the name@domain format.", retryable=False
        )
    try:
        result = register(username, body.password, body.email)
    except UsernameTaken as e:
        raise ApiError(
            409, "username_taken", "The username is already in use.", "Choose another username.", retryable=False
        ) from e
    _set_auth_cookie(response, result["token"])
    return result


def _me_payload(claims: dict) -> dict:

    owner_id = _owner_id_of(claims.get("sub"))
    username, role = claims.get("username"), claims.get("role")
    tenant_id = str(claims["tenant_id"])
    return {
        "username": username,
        "role": role,
        "owner_id": owner_id,
        "tenant_id": tenant_id,
        "user": {"username": username, "role": role, "tenant_id": tenant_id},
    }


@router.get("/me")
def me_auth(claims: dict = Depends(require_user)) -> dict:

    return _me_payload(claims)


@me_router.get("/me")
def me(claims: dict = Depends(require_user)) -> dict:

    return _me_payload(claims)


def _owner_id_of(user_id: str | None) -> str | None:

    if not user_id:
        return None
    import psycopg2

    try:
        conn = connect_core()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT owner_id FROM users WHERE id::text=%s", (user_id,))
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()
    except psycopg2.Error:
        return None
