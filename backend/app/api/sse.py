"""SSE endpoint (streaming-sse §4). GET /conversations/{id}/sse → text/event-stream.

4 header sống-còn (X-Accel-Buffering:no THIẾU = chết im sau nginx) + heartbeat 15s +
finally unsubscribe (mọi đường thoát dọn subscriber). Cap connection/conv. Auth cookie
(EventSource không set custom header — require_user đọc cookie shb_token).
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.auth.deps import require_user
from app.errors import ApiError
from app.sse import bus

router = APIRouter(prefix="/api/conversations", tags=["sse"])

_HEARTBEAT = 15.0

_SSE_HEADERS = {
    "Cache-Control": "no-cache",  # chặn cache proxy/browser
    "X-Accel-Buffering": "no",  # tắt buffering nginx — THIẾU LÀ SSE CHẾT IM
    "Connection": "keep-alive",
    "Content-Encoding": "identity",  # chặn middleware gzip gom frame
}


@router.get("/{conv_id}/sse")
async def sse(conv_id: str, request: Request, claims: dict = Depends(require_user)) -> StreamingResponse:
    """Server-Sent Events stream for a conversation (live cards/thinking/status; others → 404-hide)."""
    # D-56 scoping: customer subscribe ca người khác → 404 (hide), KHÔNG stream. admin → mọi ca.
    from app.auth.deps import can_access_conv
    from app.orch import store

    conv = await store.get_conversation(conv_id)
    if conv is None or not can_access_conv(conv, claims):
        raise ApiError(404, "not_found", f"Không có ca '{conv_id}'.", "Kiểm lại id ca.", retryable=False)
    if bus.conn_count(conv_id) >= bus.MAX_CONN_PER_CONV:
        raise ApiError(429, "too_many_connections", "Quá số kết nối SSE cho ca này.", "Đóng bớt tab.", retryable=True)
    q = bus.subscribe(conv_id)

    async def gen():
        try:
            yield ": connected\n\n"  # flush frame đầu, mở đường ống ngay
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=_HEARTBEAT)
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                except TimeoutError:
                    # S6: heartbeat = EVENT THẬT (data:) không comment (: ...) — native EventSource
                    # NUỐT comment frame → FE onmessage KHÔNG thấy → watchdog kích sai. type='ping'
                    # cùng shape SSEEnvelope → FE parse → bỏ qua render + RESET watchdog (FE chốt).
                    ping = {
                        "type": "ping",
                        "conversation_id": conv_id,
                        "seq": None,
                        "ts": datetime.now(UTC).isoformat(),
                        "data": {},
                    }
                    yield f"data: {json.dumps(ping, ensure_ascii=False)}\n\n"
        finally:
            bus.unsubscribe(conv_id, q)  # MỌI đường thoát dọn subscriber

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)
