"""Application-level JWT and authentication configuration.

Read secrets from the environment, using defaults only for development.
DATABASE_URL remains in app/db/config.py.
"""

from __future__ import annotations

import os
import re
from ipaddress import ip_address
from urllib.parse import urlsplit

_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _valid_origin_host(host: str) -> bool:
    """Accept exact DNS, IPv4, or IPv6 hosts; reject wildcards and ambiguous names."""
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


# JWT secret comes from the environment. The fallback is only for the local demo;
# production must set JWT_SECRET and never commit a real secret (D-12).
DEFAULT_JWT_SECRET = "shb-digital-dev-secret-change-in-prod"
JWT_SECRET = os.environ.get("JWT_SECRET", DEFAULT_JWT_SECRET)
JWT_ALG = "HS256"
JWT_TTL_SECONDS = int(os.environ.get("JWT_TTL_SECONDS", str(12 * 3600)))  # Twelve-hour work shift.

# EventSource cannot set custom headers, so the JWT is also carried by a cookie.
AUTH_COOKIE = "shb_token"


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse env bool: '1'/'true'/'yes'/'on' (case-insensitive) = True."""
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


# D-39: DEV_SKIP_AUTH grants admin access to every request. It defaults off and
# must never be enabled in a real deployment; startup logs a warning if enabled.
DEV_SKIP_AUTH = _env_bool("DEV_SKIP_AUTH", default=False)

# DEV_SKIP_AUTH supplies admin claims without a cookie/JWT; resolve the subject from DB as needed.
DEV_ADMIN_CLAIMS = {"username": "admin", "role": "admin"}

# D-56: Google OAuth is an additional customer authentication path, disabled by
# default. Read the module attribute at use sites to allow test monkeypatching.
AUTH_GOOGLE_ENABLED = _env_bool("AUTH_GOOGLE_ENABLED", default=False)
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = os.environ.get(
    "GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback"
)
# Return to the frontend after setting the cookie; host-based cookies also work on localhost.
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

# Apply the Secure flag to all auth cookies. It defaults off for local HTTP;
# HTTPS deployments must set COOKIE_SECURE=1.
COOKIE_SECURE = _env_bool("COOKIE_SECURE", default=False)

# Embedded clients on other origins require an explicit allowlist. Empty means
# no CORS middleware and preserves the same-origin reverse-proxy deployment.
CORS_ORIGINS = parse_cors_origins(os.environ.get("SHB_CORS_ORIGINS"))
