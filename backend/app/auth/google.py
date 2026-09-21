from __future__ import annotations

from typing import Any

import httpx
import psycopg2
import psycopg2.extras

from app import config
from app.storage import connect_core

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleOAuthError(Exception):
    pass


def is_configured() -> bool:

    return bool(config.AUTH_GOOGLE_ENABLED and config.GOOGLE_OAUTH_CLIENT_ID and config.GOOGLE_OAUTH_CLIENT_SECRET)


def exchange_code(code: str) -> str:

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
        raise GoogleOAuthError("Google did not return an access_token")
    return access


def fetch_userinfo(access_token: str) -> dict[str, Any]:

    with httpx.Client(timeout=15.0) as client:
        resp = client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    if resp.status_code != 200:
        raise GoogleOAuthError(f"userinfo fetch failed: {resp.text[:200]}")
    info = resp.json()
    if not info.get("sub") or not info.get("email"):
        raise GoogleOAuthError("userinfo is missing sub or email")
    return info


def upsert_google_user(*, google_sub: str, email: str) -> dict[str, Any]:

    email_norm = email.lower().strip()
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, username, role, tenant_id FROM users WHERE google_sub=%s", (google_sub,))
            row = cur.fetchone()
            if row:
                return dict(row)

            cur.execute(
                "INSERT INTO users (username, pass_hash, role, owner_id, email, google_sub) "
                "VALUES (%s, NULL, 'customer', NULL, %s, %s) "
                "ON CONFLICT (google_sub) DO NOTHING",
                (email_norm, email_norm, google_sub),
            )
            conn.commit()
            cur.execute("SELECT id, username, role, tenant_id FROM users WHERE google_sub=%s", (google_sub,))
            return dict(cur.fetchone())
    finally:
        conn.close()
