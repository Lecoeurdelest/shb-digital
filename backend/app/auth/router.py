"""Auth router — POST /api/auth/login (CONTRACT §1).

Router = tầng HTTP: nhận body, gọi service, set cookie JWT, trả resource trần / 401 envelope.
KHÔNG chứa business (service lo) — router chỉ dịch HTTP↔service.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.auth.service import authenticate
from app.config import AUTH_COOKIE, JWT_TTL_SECONDS
from app.errors import ApiError

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
