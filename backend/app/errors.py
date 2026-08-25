"""Envelope lỗi 4-field — 1 shape cả hệ (CONTRACT §0 · SPEC §5).

MỌI lỗi toàn hệ: {code, message, hint, retryable}. REST dùng HTTP status phân loại;
body lỗi mới là 4-field. Helper này = nguồn DUY NHẤT dựng error body — không rải rác.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


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
    """Mọi lỗi HTTP/validation đều về body 4-field trần theo CONTRACT §0."""
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(ApiError)
    async def _api_error(_req: Any, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_req: Any, exc: StarletteHTTPException) -> JSONResponse:
        # Router-level 404/405 do Starlette sinh không đi qua ApiError. Chuẩn hoá tại cổng cuối
        # để FE không phải có nhánh riêng cho {"detail": ...}.
        errors = {
            400: ("bad_request", "Yêu cầu không hợp lệ.", "Kiểm tra lại request theo CONTRACT."),
            401: ("unauthorized", "Chưa đăng nhập hoặc phiên hết hạn.", "Đăng nhập lại."),
            403: ("forbidden", "Bạn không có quyền thực hiện thao tác này.", "Dùng tài khoản có quyền phù hợp."),
            404: ("not_found", "Không tìm thấy tài nguyên được yêu cầu.", "Kiểm tra lại đường dẫn hoặc định danh."),
            405: (
                "method_not_allowed",
                "Phương thức HTTP không được hỗ trợ cho đường dẫn này.",
                "Dùng phương thức được khai báo trong CONTRACT.",
            ),
            409: ("conflict", "Yêu cầu xung đột với trạng thái hiện tại.", "Tải lại trạng thái rồi thử lại."),
            429: ("rate_limited", "Hệ thống đang giới hạn tần suất yêu cầu.", "Chờ một lúc rồi thử lại."),
        }
        code, message, hint = errors.get(
            exc.status_code,
            ("http_error", "Không thể xử lý yêu cầu HTTP.", "Kiểm tra lại yêu cầu hoặc thử lại sau."),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message, hint, retryable=exc.status_code == 429 or exc.status_code >= 500),
            headers=exc.headers,
        )

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
