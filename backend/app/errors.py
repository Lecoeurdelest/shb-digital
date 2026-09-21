"""One four-field error envelope across the application (CONTRACT §0 · SPEC §5).

Every error has {code, message, hint, retryable}. REST uses HTTP status codes for
classification; only error bodies use this envelope. Keep construction in one place.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def error_body(code: str, message: str, hint: str, retryable: bool = False) -> dict[str, Any]:
    """Return the plain four-field shape also used by SSE and tools."""
    return {"code": code, "message": message, "hint": hint, "retryable": retryable}


class ApiError(HTTPException):
    """HTTP exception rendered as the standard four-field error body."""

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
    """Normalize HTTP and validation errors to CONTRACT §0."""
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(ApiError)
    async def _api_error(_req: Any, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_req: Any, exc: StarletteHTTPException) -> JSONResponse:
        # Starlette's routing errors bypass ApiError; normalize them here so clients do
        # not need a separate branch for {"detail": ...}.
        errors = {
            400: ("bad_request", "Invalid request.", "Check the request against the API contract."),
            401: ("unauthorized", "Not signed in or the session has expired.", "Sign in again."),
            403: (
                "forbidden",
                "You are not allowed to perform this action.",
                "Use an account with the required access.",
            ),
            404: ("not_found", "The requested resource was not found.", "Check the path or identifier."),
            405: (
                "method_not_allowed",
                "This HTTP method is not supported for the path.",
                "Use a method declared in the API contract.",
            ),
            409: ("conflict", "The request conflicts with the current state.", "Reload the state and try again."),
            429: ("rate_limited", "Too many requests.", "Wait a moment and try again."),
        }
        code, message, hint = errors.get(
            exc.status_code,
            ("http_error", "The HTTP request could not be processed.", "Check the request or try again later."),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message, hint, retryable=exc.status_code == 429 or exc.status_code >= 500),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_req: Any, exc: RequestValidationError) -> JSONResponse:
        # Validation errors retain the four-field shape without exposing a Pydantic traceback.
        return JSONResponse(
            status_code=400,
            content=error_body(
                "bad_request",
                f"Invalid body: {exc.errors()[0].get('msg', 'validation error') if exc.errors() else ''}",
                "Check required fields and data types against the API contract.",
                retryable=True,
            ),
        )
