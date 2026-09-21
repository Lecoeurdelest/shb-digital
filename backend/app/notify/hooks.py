from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import psycopg2
import psycopg2.extras

from app.storage import connect_core

log = logging.getLogger("notify.hooks")

_bg_tasks: set[asyncio.Task[Any]] = set()


def app_url() -> str:
    """Return the application link for email CTAs from APP_URL (localhost:5173 by default; S10 uses production)."""
    return os.environ.get("APP_URL", "http://localhost:5173")


def owner_greeting(conv_id: str) -> str:

    try:
        conn = connect_core()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT cust.full_name FROM conversations c JOIN users u ON c.user_id=u.username "
                    "JOIN customers cust ON u.owner_id=cust.id WHERE c.id::text=%s",
                    (conv_id,),
                )
                row = cur.fetchone()
                return row[0] if row and row[0] else "Customer"
        finally:
            conn.close()
    except psycopg2.Error:
        return "Customer"


def _conv_owner_email(conv_id: str) -> str | None:

    try:
        conn = connect_core()
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
        log.warning("failed to look up email for case owner %s (notification skipped): %s", conv_id, e)
        return None


def notify_conv_owner(conv_id: str, subject: str, body: str, html_body: str | None = None) -> None:

    async def _run() -> None:
        try:
            from app.notify.email import send_email

            to = await asyncio.to_thread(_conv_owner_email, conv_id)
            if not to:
                log.debug("notification skipped for case %s: owner is not a customer with email", conv_id)
                return
            await asyncio.to_thread(send_email, to, subject, body, html_body)
        except Exception as e:  # noqa: BLE001
            log.warning("notify_conv_owner failed for case %s: %s", conv_id, e)

    task = asyncio.ensure_future(_run())
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
