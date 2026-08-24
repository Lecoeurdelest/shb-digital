"""Tenant context primitives.

Tenant identity is server-owned: routers obtain it from authenticated claims and never accept it
from request bodies or query parameters. Keeping this tiny module dependency-light avoids each
service inventing a fallback with different isolation semantics.
"""

from __future__ import annotations

from typing import Any

from app.errors import ApiError

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def tenant_id_from_claims(claims: dict[str, Any]) -> str:
    tenant_id = claims.get("tenant_id")
    if tenant_id:
        return str(tenant_id)
    # require_user normally enriches legacy JWTs before a router sees them. Fail closed here so a
    # future endpoint cannot silently turn a missing context into access to the default tenant.
    raise ApiError(
        status_code=401,
        code="tenant_context_missing",
        message="Phiên đăng nhập thiếu phạm vi đơn vị.",
        hint="Đăng nhập lại để làm mới phiên.",
        retryable=False,
    )
