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
