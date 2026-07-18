"""Hook thông báo (T9-2) — notify_conv_owner: gửi mail cho KHÁCH sở hữu ca (best-effort async).

Gọi SAU sự kiện (decide/receipt) đã commit + SSE đã bắn. Fire-and-forget (asyncio task) — KHÔNG
chặn flow duyệt/resume. Ca creator = bank / không email → skip im (log debug). §12 best-effort.

GC-safe: giữ ref task + try/except-log (mirror _emit_and_wake) — exception task không rơi vào
asyncio default handler.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import psycopg2
import psycopg2.extras

from app.db.config import DATABASE_URL

log = logging.getLogger("notify.hooks")

_bg_tasks: set[asyncio.Task[Any]] = set()  # giữ ref (create_task không giữ → GC giết task giữa chừng)


def app_url() -> str:
    """Link app cho CTA mail — env APP_URL (default localhost:5173; S10 → digital.tinhdev.com)."""
    return os.environ.get("APP_URL", "http://localhost:5173")


def owner_greeting(conv_id: str) -> str:
    """Tên khách sở hữu ca (customers.full_name qua owner_id) cho 'Kính gửi'. Không có → 'Quý khách'."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT cust.full_name FROM conversations c JOIN users u ON c.user_id=u.username "
                    "JOIN customers cust ON u.owner_id=cust.id WHERE c.id::text=%s",
                    (conv_id,),
                )
                row = cur.fetchone()
                return row[0] if row and row[0] else "Quý khách"
        finally:
            conn.close()
    except psycopg2.Error:
        return "Quý khách"


def _conv_owner_email(conv_id: str) -> str | None:
    """Email KHÁCH tạo ca (conversations.user_id → users role=customer + email NOT NULL). None = bank
    /không email → skip. Best-effort (DB lỗi → None, không raise)."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT u.email FROM conversations c JOIN users u ON c.user_id=u.username "
                    "WHERE c.id::text=%s AND u.role='customer' AND u.email IS NOT NULL",
                    (conv_id,),
                )
                row = cur.fetchone()
                return row["email"] if row else None
        finally:
            conn.close()
    except psycopg2.Error as e:
        log.warning("tra email owner ca %s lỗi (bỏ qua notify): %s", conv_id, e)
        return None


def notify_conv_owner(conv_id: str, subject: str, body: str, html_body: str | None = None) -> None:
    """Bắn mail cho khách sở hữu ca — FIRE-AND-FORGET (không await, không chặn caller).

    html_body có → mail multipart HTML brand (plain body fallback). Lookup email + gửi CHẠY trong
    background task (to_thread — smtplib sync). Ca bank/không email → task tự skip. Gọi từ async
    context (approvals decide, gated handler)."""

    async def _run() -> None:
        try:
            from app.notify.email import send_email

            to = await asyncio.to_thread(_conv_owner_email, conv_id)
            if not to:
                log.debug("notify skip ca %s: owner không phải khách-có-email", conv_id)
                return
            await asyncio.to_thread(send_email, to, subject, body, html_body)
        except Exception as e:  # noqa: BLE001 — best-effort: lỗi notify KHÔNG xuyên lên flow chính
            log.warning("notify_conv_owner ca %s lỗi: %s", conv_id, e)

    task = asyncio.ensure_future(_run())
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)  # GC-safe: bỏ ref khi xong
