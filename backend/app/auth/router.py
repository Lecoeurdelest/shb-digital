"""Auth router — POST /api/auth/login (CONTRACT §1).

Router = tầng HTTP: nhận body, gọi service, set cookie JWT, trả resource trần / 401 envelope.
KHÔNG chứa business (service lo) — router chỉ dịch HTTP↔service.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.auth.deps import require_user
from app.auth.service import UsernameTaken, authenticate, register
from app.config import AUTH_COOKIE, JWT_TTL_SECONDS
from app.errors import ApiError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")  # format thô (demo-grade), không RFC đầy đủ

router = APIRouter(prefix="/api/auth", tags=["auth"])
# D-56: /api/me (Export FE T8-2) — router riêng prefix /api (không /api/auth). /api/auth/me GIỮ (FE cũ).
me_router = APIRouter(prefix="/api", tags=["me"])


class LoginBody(BaseModel):
    username: str
    password: str


class RegisterBody(BaseModel):
    username: str
    password: str
    email: str | None = None


def _set_auth_cookie(response: Response, token: str) -> None:
    """Set JWT httponly cookie — dùng chung login + register (EventSource dùng cookie, không header)."""
    response.set_cookie(
        key=AUTH_COOKIE, value=token, httponly=True, samesite="lax", max_age=JWT_TTL_SECONDS
    )


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
    _set_auth_cookie(response, result["token"])
    # Success = resource trần (CONTRACT §0) — trả token (FE dùng nếu cần) + user
    return result


@router.post("/register", status_code=201)
def register_endpoint(body: RegisterBody, response: Response) -> dict:
    """{username, password, email?} → 201 {token, user} (D-57 khách mới). Auto-login (set cookie).

    Validate (tầng HTTP): username 3-32 ký tự · password ≥4 (demo-grade) · email format thô nếu có.
    username trùng → 409 message CHUNG (không lộ user-nào-tồn-tại kiểu khác — defensive §3)."""
    username = (body.username or "").strip()
    if not (3 <= len(username) <= 32):
        raise ApiError(400, "bad_username", "Tên đăng nhập 3-32 ký tự.", "Chọn tên khác.", retryable=False)
    if len(body.password or "") < 4:
        raise ApiError(400, "bad_password", "Mật khẩu tối thiểu 4 ký tự.", "Chọn mật khẩu dài hơn.", retryable=False)
    if body.email and not _EMAIL_RE.match(body.email):
        raise ApiError(400, "bad_email", "Email không hợp lệ.", "Kiểm định dạng name@domain.", retryable=False)
    try:
        result = register(username, body.password, body.email)
    except UsernameTaken as e:
        raise ApiError(
            409, "username_taken", "Tên đăng nhập đã được dùng.", "Chọn tên đăng nhập khác.", retryable=False
        ) from e
    _set_auth_cookie(response, result["token"])
    return result


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
