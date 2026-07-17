"""Auth dependencies — require_user / require_admin (cho router T1-2+ dùng).

Đọc JWT từ cookie (CONTRACT §1: EventSource không set header → cookie), decode → claims.
Thiếu/hỏng token → 401 envelope 4-field. Sai role → 403.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request

from app.auth.security import decode_token
from app.config import AUTH_COOKIE
from app.errors import ApiError


def _claims_from_request(request: Request) -> dict[str, Any]:
    token = request.cookies.get(AUTH_COOKIE)
    # fallback: Bearer header (REST client/test tiện) — EventSource vẫn dùng cookie
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    claims = decode_token(token) if token else None
    if claims is None:
        raise ApiError(
            status_code=401,
            code="unauthorized",
            message="Chưa đăng nhập hoặc phiên hết hạn.",
            hint="Đăng nhập lại qua POST /api/auth/login.",
            retryable=False,
        )
    return claims


def require_user(request: Request) -> dict[str, Any]:
    """Bất kỳ account đã đăng nhập (user hoặc admin)."""
    return _claims_from_request(request)


def require_admin(request: Request) -> dict[str, Any]:
    """Chỉ admin (quản lý/compliance — D-19). Dùng cho approvals/audit endpoints (S4)."""
    claims = _claims_from_request(request)
    if claims.get("role") != "admin":
        raise ApiError(
            status_code=403,
            code="forbidden",
            message="Chỉ quản lý (admin) được thao tác này.",
            hint="Đăng nhập bằng account admin.",
            retryable=False,
        )
    return claims
