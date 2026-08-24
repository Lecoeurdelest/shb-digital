"""Chuông cửa webhook cho bàn duyệt (D-71) — allowlist nhỏ, best-effort sau commit.

Webhook chỉ báo có việc và mang deep-link về Control Tower. Approval và RFI đều dựng body mới từ
allowlist riêng, không nhận nguyên row nghiệp vụ. Không outbox; retry hữu hạn có thể tạo bản tin
trùng theo CONTRACT §8/§11f.
"""

from __future__ import annotations

import asyncio
import logging
import os
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx

from app.case_intake.normalization import normalize_missing_fields
from app.notify.hooks import app_url

log = logging.getLogger("notify.channels")

_ALLOWED_STATUSES = {"pending", "approved", "rejected"}
_RETRY_DELAYS = (1.0, 3.0)
_bg_tasks: set[asyncio.Task[Any]] = set()


def _amount_vnd(row: dict[str, Any]) -> int | None:
    payload = row.get("payload")
    if not isinstance(payload, dict):
        return None
    raw = payload.get("amount") if "amount" in payload else payload.get("amount_vnd")
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not value.is_finite() or value != value.to_integral_value():
        return None
    return int(value)


def _event_of(row: dict[str, Any], status: str) -> dict[str, Any] | None:
    """Tạo object mới từ allowlist; không bao giờ mutate/merge approval business payload."""
    approval_id = row.get("id") or row.get("approval_id")
    action = row.get("action")
    conv_id = row.get("conv_id")
    if status not in _ALLOWED_STATUSES or not approval_id or not action or not conv_id:
        return None
    deep_link = f"{app_url().rstrip('/')}/?{urlencode({'tab': 'approvals', 'approval': str(approval_id)})}"
    return {
        "action": str(action),
        "conv_id": str(conv_id)[:8],
        "status": status,
        "deep_link": deep_link,
        "amount": _amount_vnd(row),
    }


def _generic_body(event: dict[str, Any], include_amount: bool) -> dict[str, Any]:
    body = {key: event[key] for key in ("action", "conv_id", "status", "deep_link")}
    if include_amount and event["amount"] is not None:
        body["amount"] = event["amount"]
    return body


def _lark_body(event: dict[str, Any], include_amount: bool) -> dict[str, Any]:
    content = f"**{event['action']}** · ca `{event['conv_id']}` · {event['status']}"
    if include_amount and event["amount"] is not None:
        content += f" · {event['amount']} VND"
    return {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "BANK Digital · Approval doorbell"}},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "Open Control Tower"},
                            "type": "primary",
                            "url": event["deep_link"],
                        }
                    ],
                },
            ],
        },
    }


async def _post_with_retries(
    webhook_url: str,
    channel: str,
    event: dict[str, Any],
    body: dict[str, Any],
) -> None:
    """Ba attempts tổng: ngay, +1s, +3s; chỉ retry lỗi vận chuyển, 429 và 5xx."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        for attempt in range(1, 4):
            if attempt > 1:
                await asyncio.sleep(_RETRY_DELAYS[attempt - 2])
            try:
                response = await client.post(webhook_url, json=body)
            except httpx.RequestError as exc:
                log.warning(
                    "webhook channel=%s event_status=%s conv=%s attempt=%s exception=%s",
                    channel,
                    event["status"],
                    event["conv_id"],
                    attempt,
                    type(exc).__name__,
                )
                if attempt < 3:
                    continue
                return

            retryable = response.status_code == 429 or 500 <= response.status_code < 600
            if 200 <= response.status_code < 300:
                return
            log.warning(
                "webhook channel=%s event_status=%s conv=%s attempt=%s http_status=%s",
                channel,
                event["status"],
                event["conv_id"],
                attempt,
                response.status_code,
            )
            if not retryable or attempt == 3:
                return


async def _deliver_guarded(
    webhook_url: str,
    channel: str,
    event: dict[str, Any],
    body: dict[str, Any],
) -> None:
    try:
        await _post_with_retries(webhook_url, channel, event, body)
    except Exception as exc:  # noqa: BLE001 — chuông cửa không được làm hỏng nghiệp vụ đã commit
        log.warning(
            "webhook channel=%s event_status=%s conv=%s attempt=0 exception=%s",
            channel,
            event["status"],
            event["conv_id"],
            type(exc).__name__,
        )


def _schedule(row: dict[str, Any], status: str) -> None:
    webhook_url = os.environ.get("SHB_NOTIFY_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return
    channel = os.environ.get("SHB_NOTIFY_CHANNEL", "generic").strip()
    if channel not in {"generic", "lark"}:
        log.warning("webhook disabled channel=invalid event_status=%s conv=%s", status, str(row.get("conv_id", ""))[:8])
        return
    event = _event_of(row, status)
    if event is None:
        log.warning("webhook drop channel=%s event_status=%s conv=%s", channel, status, str(row.get("conv_id", ""))[:8])
        return
    include_amount = os.environ.get("SHB_NOTIFY_INCLUDE_AMOUNT") == "1"
    body = _generic_body(event, include_amount) if channel == "generic" else _lark_body(event, include_amount)
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_deliver_guarded(webhook_url, channel, event, body))
    except Exception as exc:  # noqa: BLE001 — caller có thể không có running loop; vẫn best-effort
        log.warning(
            "webhook channel=%s event_status=%s conv=%s attempt=0 exception=%s",
            channel,
            event["status"],
            event["conv_id"],
            type(exc).__name__,
        )
        return
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


def notify_channel_approval_pending(approval: dict[str, Any]) -> None:
    """Báo một phiếu pending mới; caller chịu trách nhiệm gọi sau commit + SSE."""
    _schedule(approval, "pending")


def notify_channel_approval_decided(approval: dict[str, Any]) -> None:
    """Báo kết quả approved/rejected; trạng thái khác bị drop ở allowlist."""
    status = str(approval.get("status", ""))
    if status not in {"approved", "rejected"}:
        return
    _schedule(approval, status)


def notify_channel_case_rfi(case_id: str, missing_fields: list[str]) -> None:
    """Schedule a minimized D-83 generic webhook after the caller's intake commit."""
    webhook_url = os.environ.get("SHB_NOTIFY_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return
    channel = os.environ.get("SHB_NOTIFY_CHANNEL", "generic").strip()
    if channel != "generic":
        log.warning("RFI webhook disabled channel=%s case=%s", channel or "invalid", str(case_id)[:8])
        return
    try:
        canonical_case_id = str(UUID(str(case_id)))
    except (TypeError, ValueError, AttributeError):
        log.warning("RFI webhook drop invalid case id")
        return
    normalized = normalize_missing_fields(missing_fields)
    if not normalized:
        return
    body = {
        "missing_fields": normalized,
        "deep_link": f"{app_url().rstrip('/')}/?{urlencode({'tab': 'cases', 'case': canonical_case_id})}",
    }
    event = {"status": "rfi", "conv_id": canonical_case_id[:8]}
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_deliver_guarded(webhook_url, "generic", event, body))
    except Exception as exc:  # noqa: BLE001 — best-effort sau commit
        log.warning("RFI webhook schedule lỗi case=%s exception=%s", canonical_case_id[:8], type(exc).__name__)
        return
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
