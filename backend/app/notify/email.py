from __future__ import annotations

import html
import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Any

log = logging.getLogger("notify.email")

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 465
_TIMEOUT_S = 10


_ACCENT = {"approved": "#1a9e4b", "rejected": "#d0342c", "disbursed": "#f37021"}
_ICON = {"approved": "✅", "rejected": "✖️", "disbursed": "💸"}
_TITLE = {
    "approved": "LOAN APPROVED",
    "rejected": "LOAN REJECTED",
    "disbursed": "DISBURSEMENT COMPLETED",
}


def _vnd(amount: int) -> str:

    return f"{int(amount):,}".replace(",", ".") + " ₫"


def _info_rows(d: dict[str, Any]) -> str:

    decided_by_raw = d.get("decided_by") or ""
    decided_by = (
        "System — automatic under the delegated authority policy" if decided_by_raw == "auto-rule" else decided_by_raw
    )
    rows: list[tuple[str, str]] = [
        ("Dear", str(d.get("greeting_name") or "Customer")),
        ("Decision by", decided_by),
        ("Time", str(d.get("decided_at") or "")),
        ("Reference", str(d.get("ref") or "")),
    ]
    if d.get("assessment_id"):
        rows.append(("Assessment record", f"#{d['assessment_id']}"))
    if d.get("reject_reason"):
        rows.append(("Rejection reason", str(d["reject_reason"])))
    cell_l = 'style="padding:10px 16px;font-size:13px;color:#777;border-bottom:1px solid #f0ece8;"'
    cell_r = (
        'align="right" style="padding:10px 16px;font-size:13px;color:#222;font-weight:bold;'
        'border-bottom:1px solid #f0ece8;"'
    )
    return "".join(
        f"<tr><td {cell_l}>{html.escape(label)}</td><td {cell_r}>{html.escape(value)}</td></tr>"
        for label, value in rows
        if value
    )


def render_email_html(kind: str, d: dict[str, Any]) -> str:
    """Mail HTML brand BANK Digital (kind: approved|rejected|disbursed). Table-based + inline CSS + 600px.

    d: {greeting_name, loan_id, amount_vnd(int), decided_by, decided_at, ref, assessment_id?, app_url}."""
    accent = _ACCENT[kind]
    icon = _ICON[kind]
    title = _TITLE[kind]
    amount = _vnd(d.get("amount_vnd") or 0)
    loan_id = html.escape(str(d.get("loan_id") or ""))
    app_url = html.escape(str(d.get("app_url") or ""))
    return f"""\
<div style="margin:0;padding:0;background:#f4f5f7;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:24px 0;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:94%;background:#ffffff;border-radius:12px;overflow:hidden;font-family:Arial,Helvetica,sans-serif;box-shadow:0 1px 4px rgba(0,0,0,.08);">
  <tr><td style="background:#f37021;padding:20px 32px;">
    <span style="color:#ffffff;font-size:20px;font-weight:bold;letter-spacing:.5px;">BANK <span style="font-weight:normal;">| Digital</span></span>
    <span style="color:#ffd9c2;font-size:12px;float:right;padding-top:6px;">Digital Banking Branch</span>
  </td></tr>
  <tr><td align="center" style="padding:32px 32px 8px;">
    <div style="font-size:44px;line-height:1;">{icon}</div>
    <div style="font-size:20px;font-weight:bold;color:{accent};padding-top:10px;">{title}</div>
    <div style="font-size:34px;font-weight:bold;color:#222222;padding-top:6px;">{amount}</div>
    <div style="font-size:13px;color:#888888;padding-top:2px;">Loan {loan_id}</div>
  </td></tr>
  <tr><td style="padding:20px 32px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#faf9f8;border:1px solid #eeeae6;border-radius:8px;">
      {_info_rows(d)}
    </table>
  </td></tr>
  <tr><td align="center" style="padding:4px 32px 28px;">
    <a href="{app_url}" style="display:inline-block;background:#f37021;color:#ffffff;font-size:14px;font-weight:bold;text-decoration:none;padding:12px 32px;border-radius:24px;">View details in the application →</a>
  </td></tr>
  <tr><td style="background:#faf9f8;padding:16px 32px;border-top:1px solid #eeeae6;">
    <div style="font-size:11px;color:#999999;line-height:1.5;">Automated email from <b>BANK Digital Expert Guild</b> — VAIC 2026 demo system. Every transaction is recorded in the audit ledger. Please do not reply to this email.</div>
  </td></tr>
</table>
</td></tr></table></div>"""


def _smtp_env() -> tuple[str, str, str] | None:

    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_APP_PASSWORD")
    if not user or not password:
        return None
    from_name = os.environ.get("NOTIFY_FROM_NAME", "BANK Digital")
    return user, password, from_name


def send_email(to: str, subject: str, body: str, html_body: str | None = None) -> bool:

    env = _smtp_env()
    if env is None:
        log.info("mail no-op: SMTP environment is missing (SMTP_USER/SMTP_APP_PASSWORD); skipping '%s'", subject)
        return False
    if not to:
        log.debug("mail skipped: 'to' is empty because the case has no email")
        return False
    user, password, from_name = env
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{user}>"
    msg["To"] = to
    msg.set_content(body)  # plain-text fallback (client text-only)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    try:
        with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT, timeout=_TIMEOUT_S) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
        log.info("mail sent '%s' to %s", subject, to)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("failed to send mail '%s' to %s: %s", subject, to, e)
        return False
