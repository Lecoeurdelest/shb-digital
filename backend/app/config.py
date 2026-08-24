"""App-level config — JWT + auth. Không hardcode secret (đọc env, default dev-only).

DATABASE_URL vẫn ở app/db/config.py (nguồn DB). File này lo phần auth/JWT.
"""

from __future__ import annotations

import os
import re
from ipaddress import ip_address
from urllib.parse import urlsplit

_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _valid_origin_host(host: str) -> bool:
    """DNS/IPv4/IPv6 literal hợp lệ; wildcard và hostname mơ hồ bị chặn."""
    try:
        ip_address(host)
        return True
    except ValueError:
        labels = host.rstrip(".").split(".")
        return bool(labels) and all(_HOST_LABEL.fullmatch(label) for label in labels)


def parse_cors_origins(raw: str | None) -> tuple[str, ...]:
    """Parse exact browser origins; empty = CORS off, invalid input = fail-fast at startup."""
    if raw is None or not raw.strip():
        return ()
    origins: list[str] = []
    for item in raw.split(","):
        origin = item.strip()
        if not origin:
            raise ValueError("SHB_CORS_ORIGINS contains an empty origin")
        if "*" in origin:
            raise ValueError("SHB_CORS_ORIGINS does not allow wildcards")
        parsed = urlsplit(origin)
        try:
            port = parsed.port  # trigger validation for malformed/out-of-range ports
        except ValueError as exc:
            raise ValueError(f"invalid CORS origin port: {origin!r}") from exc
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"CORS origin must use http/https with a host: {origin!r}")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError(f"CORS origin must not contain userinfo: {origin!r}")
        if parsed.path or "?" in origin or "#" in origin:
            raise ValueError(f"CORS origin must not contain path, query, or fragment: {origin!r}")
        if not _valid_origin_host(parsed.hostname):
            raise ValueError(f"invalid CORS origin host: {origin!r}")
        host = parsed.hostname.lower().rstrip(".")
        authority = f"[{host}]" if ":" in host else host
        scheme = parsed.scheme.lower()
        default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
        canonical = f"{scheme}://{authority}{f':{port}' if port is not None and not default_port else ''}"
        if canonical not in origins:
            origins.append(canonical)
    return tuple(origins)


# JWT: HS256, secret từ env. Default CHỈ cho dev/demo on-premise (1 lệnh compose) — PROD thật
# đặt JWT_SECRET qua env. Không commit secret thật (D-12 .env gitignored).
DEFAULT_JWT_SECRET = "shb-digital-dev-secret-change-in-prod"
JWT_SECRET = os.environ.get("JWT_SECRET", DEFAULT_JWT_SECRET)
JWT_ALG = "HS256"
JWT_TTL_SECONDS = int(os.environ.get("JWT_TTL_SECONDS", str(12 * 3600)))  # 12h ca làm việc

# Cookie mang JWT (EventSource không set header — CONTRACT §1 · streaming-sse §4)
AUTH_COOKIE = "shb_token"


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse env bool: '1'/'true'/'yes'/'on' (case-insensitive) = True."""
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


# DEV_SKIP_AUTH (D-39): ON → mọi request = admin (bỏ login, dev/demo nội bộ tiện). Default OFF
# (an toàn — phải bật tường minh qua env). PROD/demo thật KHÔNG set. Boot log cảnh báo khi ON.
DEV_SKIP_AUTH = _env_bool("DEV_SKIP_AUTH", default=False)

# Claims admin seed trả thẳng khi DEV_SKIP_AUTH ON (không cần cookie/JWT). sub uuid lấy DB lúc dùng.
DEV_ADMIN_CLAIMS = {"username": "admin", "role": "admin"}

# ── Google OAuth (cửa phát JWT THÊM cho persona KHÁCH D-56 — port pattern có sẵn, người cấp env) ──
# Default OFF: thiếu env → app chạy y hệt cũ (login user/pass + DEV_SKIP_AUTH). Đọc các giá trị này
# qua module attr (`config.AUTH_GOOGLE_ENABLED`) để test monkeypatch được — KHÔNG from-import.
AUTH_GOOGLE_ENABLED = _env_bool("AUTH_GOOGLE_ENABLED", default=False)
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = os.environ.get(
    "GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback"
)
# FE redirect về sau callback (cookie đã set; cookie theo host, không phân biệt port → localhost OK)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

# Secure flag cho MỌI cookie auth (login + google + oauth_state). Default OFF (dev http).
# Deploy https (digital.tinhdev.com) → đặt COOKIE_SECURE=1: cookie không bao giờ đi qua http trần.
COOKIE_SECURE = _env_bool("COOKIE_SECURE", default=False)

# SDK nhúng khác-origin chỉ mở cho allowlist tường minh. Rỗng = không có CORS
# middleware, giữ nguyên mô hình reverse-proxy cùng origin hiện tại.
CORS_ORIGINS = parse_cors_origins(os.environ.get("SHB_CORS_ORIGINS"))
