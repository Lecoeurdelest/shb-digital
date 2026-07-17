"""Fanout in-process — toàn bộ 'hạ tầng realtime' của hệ (streaming-sse §1).

1 worker = 1 event loop → fanout chỉ cần dict {conv_id: set[Queue]}. publish put_nowait
(KHÔNG await — publisher không chờ client chậm). Queue đầy = client đó lỡ event → tự lành
khi reconnect+refetch (§0). Không Redis/replay-cursor (SPEC §14).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
_MAX_QUEUE = 500  # queue đầy = client không đọc (tab treo/mạng nghẽn)
MAX_CONN_PER_CONV = 10  # cap connection mỗi ca


def subscribe(conversation_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE)
    _subscribers[conversation_id].add(q)
    return q


def unsubscribe(conversation_id: str, q: asyncio.Queue) -> None:
    subs = _subscribers.get(conversation_id)
    if subs is not None:
        subs.discard(q)
        if not subs:  # phòng hết người nghe → dọn key
            _subscribers.pop(conversation_id, None)


def conn_count(conversation_id: str) -> int:
    return len(_subscribers.get(conversation_id, ()))


def publish(conversation_id: str, event: dict) -> None:
    """Sync — gọi được từ bất kỳ đâu trong luồng orchestrator không block."""
    for q in list(_subscribers.get(conversation_id, ())):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            # CHỈ client này lỡ event — tự lành khi reconnect+refetch (§0). KHÔNG await ở đây.
            pass


def reset() -> None:
    """Test teardown — dọn mọi subscriber."""
    _subscribers.clear()
