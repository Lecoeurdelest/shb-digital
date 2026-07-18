"""App-level config — JWT + auth. Không hardcode secret (đọc env, default dev-only).

DATABASE_URL vẫn ở app/db/config.py (nguồn DB). File này lo phần auth/JWT.
"""

from __future__ import annotations

import os

# JWT: HS256, secret từ env. Default CHỈ cho dev/demo on-premise (1 lệnh compose) — PROD thật
# đặt JWT_SECRET qua env. Không commit secret thật (D-12 .env gitignored).
JWT_SECRET = os.environ.get("JWT_SECRET", "shb-digital-dev-secret-change-in-prod")
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
