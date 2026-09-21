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
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
    "Content-Encoding": "identity",
}


@router.get("/{conv_id}/sse")
async def sse(conv_id: str, request: Request, claims: dict = Depends(require_user)) -> StreamingResponse:
    """Server-Sent Events stream for a conversation (live cards/thinking/status; others → 404-hide)."""

    from app.auth.deps import can_access_conv
    from app.orch import store

    conv = await store.get_conversation(conv_id)
    if conv is None or not can_access_conv(conv, claims):
        raise ApiError(404, "not_found", f"Case '{conv_id}' does not exist.", "Check the case ID.", retryable=False)
    if bus.conn_count(conv_id) >= bus.MAX_CONN_PER_CONV:
        raise ApiError(
            429,
            "too_many_connections",
            "This case has too many SSE connections.",
            "Close some browser tabs.",
            retryable=True,
        )
    q = bus.subscribe(conv_id)

    async def gen():
        try:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=_HEARTBEAT)
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                except TimeoutError:
                    ping = {
                        "type": "ping",
                        "conversation_id": conv_id,
                        "seq": None,
                        "ts": datetime.now(UTC).isoformat(),
                        "data": {},
                    }
                    yield f"data: {json.dumps(ping, ensure_ascii=False)}\n\n"
        finally:
            bus.unsubscribe(conv_id, q)

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)
