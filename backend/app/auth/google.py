"""Google OAuth — tầng service: gọi Google (đổi code → token → userinfo) + upsert user KHÁCH.

Port pattern Authorization-Code flow đã chạy prod (QA Runner) → style shb: httpx SYNC (router shb
là def thường), psycopg2 (nhất quán auth/service.py), lỗi ném GoogleOAuthError để router dịch ra
ApiError envelope 4-field. KHÔNG biết HTTP request/response của app (router lo), KHÔNG biết JWT
(security.py lo). Test monkeypatch 2 hàm exchange_code/fetch_userinfo — không cần mạng Google.
"""

from __future__ import annotations

from typing import Any

import httpx
import psycopg2
import psycopg2.extras

from app import config
from app.db.config import DATABASE_URL

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleOAuthError(Exception):
    """Google trả lỗi / thiếu field khi đổi code hoặc lấy userinfo — router dịch ra 502."""


def is_configured() -> bool:
    """Đủ env chưa: bật cờ + có client_id/secret. redirect_uri có default localhost."""
    return bool(
        config.AUTH_GOOGLE_ENABLED
        and config.GOOGLE_OAUTH_CLIENT_ID
        and config.GOOGLE_OAUTH_CLIENT_SECRET
    )


def exchange_code(code: str) -> str:
    """Đổi authorization code → access_token (server-side, mang client_secret — FE không thấy)."""
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": config.GOOGLE_OAUTH_CLIENT_SECRET,
                "redirect_uri": config.GOOGLE_OAUTH_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        raise GoogleOAuthError(f"token exchange failed: {resp.text[:200]}")
    access = resp.json().get("access_token")
    if not access:
        raise GoogleOAuthError("Google không trả access_token")
    return access


def fetch_userinfo(access_token: str) -> dict[str, Any]:
    """Lấy {sub, email, name, ...} — email đã được Google verify."""
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    if resp.status_code != 200:
        raise GoogleOAuthError(f"userinfo fetch failed: {resp.text[:200]}")
    info = resp.json()
    if not info.get("sub") or not info.get("email"):
        raise GoogleOAuthError("userinfo thiếu sub/email")
    return info


def upsert_google_user(*, google_sub: str, email: str) -> dict[str, Any]:
    """Tìm user theo google_sub; chưa có → tạo KHÁCH MỚI role='customer' (D-56).

    - username = email (unique users.username giữ nguyên bất biến).
    - pass_hash NULL (không có mật khẩu — login password với user này fail 401 bình thường).
    - owner_id NULL = khách mới CHƯA có hồ sơ nghiệp vụ — form intake (D-57 S9) sẽ gắn sau.
    Idempotent: gọi lại cùng sub → trả đúng row cũ. Trả {id, username, role}.
    """
    email_norm = email.lower().strip()
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, username, role FROM users WHERE google_sub=%s", (google_sub,)
            )
            row = cur.fetchone()
            if row:
                return dict(row)
            # Khách mới. Race 2 callback song song → ON CONFLICT (google_sub) bỏ qua rồi SELECT lại.
            cur.execute(
                "INSERT INTO users (username, pass_hash, role, owner_id, email, google_sub) "
                "VALUES (%s, NULL, 'customer', NULL, %s, %s) "
                "ON CONFLICT (google_sub) DO NOTHING",
                (email_norm, email_norm, google_sub),
            )
            conn.commit()
            cur.execute(
                "SELECT id, username, role FROM users WHERE google_sub=%s", (google_sub,)
            )
            return dict(cur.fetchone())
    finally:
        conn.close()
