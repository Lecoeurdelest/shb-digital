"""Auth router — POST /api/auth/login (CONTRACT §1).

Router = tầng HTTP: nhận body, gọi service, set cookie JWT, trả resource trần / 401 envelope.
KHÔNG chứa business (service lo) — router chỉ dịch HTTP↔service.
"""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app import config
from app.auth import google as google_oauth
from app.auth.deps import require_user
from app.auth.security import make_token
from app.auth.service import authenticate
from app.config import AUTH_COOKIE, JWT_TTL_SECONDS
from app.errors import ApiError

router = APIRouter(prefix="/api/auth", tags=["auth"])
# D-56: /api/me (Export FE T8-2) — router riêng prefix /api (không /api/auth). /api/auth/me GIỮ (FE cũ).
me_router = APIRouter(prefix="/api", tags=["me"])


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginBody, response: Response) -> dict:
    """{username, password} → {token, user:{username, role}} (CONTRACT §1).
    JWT cũng set vào cookie httponly (EventSource dùng cookie — không set header được)."""
    result = authenticate(body.username, body.password)
    if result is None:
        raise ApiError(
            status_code=401,
            code="unauthorized",
            message="Sai tên đăng nhập hoặc mật khẩu.",
            hint="Kiểm lại credential. 2 account demo: user / admin.",
            retryable=True,
        )
    response.set_cookie(
        key=AUTH_COOKIE,
        value=result["token"],
        httponly=True,
        samesite="lax",
        max_age=JWT_TTL_SECONDS,
    )
    # Success = resource trần (CONTRACT §0) — trả token (FE dùng nếu cần) + user
    return result


# ── Google OAuth (persona KHÁCH D-56 — cửa phát JWT thêm; user/pass + DEV_SKIP_AUTH giữ nguyên) ──
# Flow Authorization-Code server-side (port pattern có sẵn): /google/start redirect Google (state
# cookie chống CSRF) → Google gọi /google/callback?code&state → đổi code → userinfo → upsert KHÁCH
# → set cookie JWT shb NHƯ login thường → 302 về FE. FE không cần trang callback (cookie theo host).

_STATE_COOKIE = "oauth_state"


@router.get("/providers")
def providers() -> dict:
    """Public — FE đọc lúc boot để render đúng nút login. Bool-only, không lộ key/client_id."""
    return {"password": True, "google": google_oauth.is_configured()}


@router.get("/google/start")
def google_start() -> RedirectResponse:
    """Redirect sang màn chọn account Google. State ngẫu nhiên vào cookie httponly (chống CSRF)."""
    if not google_oauth.is_configured():
        raise ApiError(
            status_code=503,
            code="auth_provider_disabled",
            message="Đăng nhập Google chưa được bật trên server này.",
            hint="Đặt AUTH_GOOGLE_ENABLED=1 + GOOGLE_OAUTH_CLIENT_ID/SECRET trong env rồi restart.",
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
    resp.set_cookie(_STATE_COOKIE, state, httponly=True, samesite="lax", max_age=600)
    return resp


@router.get("/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None) -> RedirectResponse:
    """Google gọi lại với ?code&state → verify state, đổi code, upsert KHÁCH, set cookie JWT, về FE."""
    if not google_oauth.is_configured():
        raise ApiError(
            status_code=503,
            code="auth_provider_disabled",
            message="Đăng nhập Google chưa được bật trên server này.",
            hint="Đặt AUTH_GOOGLE_ENABLED=1 + GOOGLE_OAUTH_CLIENT_ID/SECRET trong env rồi restart.",
            retryable=False,
        )
    if not code or not state:
        raise ApiError(
            status_code=400,
            code="oauth_malformed",
            message="Thiếu code hoặc state từ Google.",
            hint="Bắt đầu lại từ /api/auth/google/start.",
            retryable=True,
        )
    if request.cookies.get(_STATE_COOKIE) != state:
        raise ApiError(
            status_code=400,
            code="oauth_state_mismatch",
            message="State không khớp — có thể CSRF hoặc cookie hết hạn (10 phút).",
            hint="Bắt đầu lại từ /api/auth/google/start.",
            retryable=True,
        )
    try:
        access = google_oauth.exchange_code(code)
        info = google_oauth.fetch_userinfo(access)
    except google_oauth.GoogleOAuthError as e:
        raise ApiError(
            status_code=502,
            code="oauth_google_failed",
            message=f"Google từ chối phiên đăng nhập: {e}",
            hint="Thử lại; kéo dài → kiểm client_id/secret/redirect_uri khớp Google Console.",
            retryable=True,
        ) from e
    user = google_oauth.upsert_google_user(google_sub=info["sub"], email=info["email"])
    token = make_token(user_id=str(user["id"]), username=user["username"], role=user["role"])
    resp = RedirectResponse(config.FRONTEND_URL)
    resp.set_cookie(key=AUTH_COOKIE, value=token, httponly=True, samesite="lax", max_age=JWT_TTL_SECONDS)
    resp.delete_cookie(_STATE_COOKIE)
    return resp


def _me_payload(claims: dict) -> dict:
    """D-56: {username, role, owner_id} phẳng (Export FE T8-2) + `user` wrap (FE boot-check cũ, không
    phá). owner_id của REQUESTER (JOIN users by claims.sub). DEV_SKIP_AUTH → admin owner_id=None."""
    owner_id = _owner_id_of(claims.get("sub"))
    username, role = claims.get("username"), claims.get("role")
    return {"username": username, "role": role, "owner_id": owner_id, "user": {"username": username, "role": role}}


@router.get("/me")
def me_auth(claims: dict = Depends(require_user)) -> dict:
    """/api/auth/me — FE boot-check cũ. Giữ backward + thêm owner_id (D-56)."""
    return _me_payload(claims)


@me_router.get("/me")
def me(claims: dict = Depends(require_user)) -> dict:
    """/api/me (D-56 Export FE T8-2) — {username, role, owner_id}. Cùng payload /api/auth/me."""
    return _me_payload(claims)


def _owner_id_of(user_id: str | None) -> str | None:
    """owner_id của account (JOIN users by id). None = account ngân hàng (admin/user) hoặc không tồn tại."""
    if not user_id:
        return None
    import psycopg2

    from app.db.config import DATABASE_URL

    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT owner_id FROM users WHERE id::text=%s", (user_id,))
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()
    except psycopg2.Error:
        return None
