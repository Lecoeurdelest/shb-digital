"""Envelope lỗi 4-field — 1 shape cả hệ (CONTRACT §0 · SPEC §5).

MỌI lỗi toàn hệ: {code, message, hint, retryable}. REST dùng HTTP status phân loại;
body lỗi mới là 4-field. Helper này = nguồn DUY NHẤT dựng error body — không rải rác.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse


def error_body(code: str, message: str, hint: str, retryable: bool = False) -> dict[str, Any]:
    """Dict 4-field thuần (SSE/tool cũng dùng shape này)."""
    return {"code": code, "message": message, "hint": hint, "retryable": retryable}


class ApiError(HTTPException):
    """HTTPException mang envelope 4-field. Raise trong router/service → handler render body chuẩn."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        hint: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(status_code=status_code, detail=error_body(code, message, hint, retryable))


def register_error_handler(app: Any) -> None:
    """Bắt ApiError → JSONResponse body 4-field TRẦN (không bọc {detail}).
    FastAPI mặc định bọc HTTPException.detail trong {"detail": ...}; ta trả detail thẳng
    để khớp CONTRACT (error = 4-field trần)."""
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(ApiError)
    async def _api_error(_req: Any, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_req: Any, exc: RequestValidationError) -> JSONResponse:
        # body sai shape (thiếu field/sai kiểu) → 400 envelope 4-field, không leak trace pydantic
        return JSONResponse(
            status_code=400,
            content=error_body(
                "bad_request",
                f"body không hợp lệ: {exc.errors()[0].get('msg', 'validation error') if exc.errors() else ''}",
                "Kiểm lại field bắt buộc + kiểu dữ liệu theo CONTRACT.",
                retryable=True,
            ),
        )
