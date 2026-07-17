"""Cổng bắn SSE DUY NHẤT + seq per-turn (streaming-sse §3). Envelope 1 shape (CONTRACT §4).

Ghi DB xong mới emit (trừ chat.delta chunk — nguồn sự thật là message ghi lúc kết lượt, mang
về FE qua done.full_text). seq per-turn (turn_id): chunk đầu seq=1; done pop counter = seq cao
nhất. Gap1 (CONTRACT §4b): MỌI kết lượt bắn done (dù rỗng/lỗi) → bubble FE không treo.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.sse.bus import publish
from app.sse.redact import redact_deep

_turn_seq: dict[str, int] = {}  # 1 worker → dict thường atomic đủ


def _next_seq(turn_id: str) -> int:
    _turn_seq[turn_id] = _turn_seq.get(turn_id, 0) + 1
    return _turn_seq[turn_id]


def emit(conversation_id: str, type_: str, data: dict, seq: int | None = None) -> None:
    """Bắn 1 event (envelope 1 shape). Redact secret ở đây — cổng duy nhất, không route nào lách."""
    publish(
        conversation_id,
        {
            "type": type_,
            "conversation_id": conversation_id,
            "seq": seq,
            "ts": datetime.now(UTC).isoformat(),
            "data": redact_deep(data),
        },
    )


def emit_chat_delta(conversation_id: str, turn_id: str, chunk: str) -> None:
    emit(
        conversation_id,
        "chat.delta",
        {"turn_id": turn_id, "chunk": chunk, "done": False},
        seq=_next_seq(turn_id),
    )


def emit_chat_done(conversation_id: str, turn_id: str, full_text: str) -> None:
    """Gọi SAU khi INSERT messages commit (§5) — MỌI kết lượt (xong/lỗi/interrupt, Gap1).
    pop → done luôn có seq cao nhất; van tự lành: FE thay text ghép bằng full_text (bản DB)."""
    seq = _turn_seq.pop(turn_id, 0) + 1
    emit(
        conversation_id,
        "chat.delta",
        {"turn_id": turn_id, "chunk": "", "done": True, "full_text": full_text},
        seq=seq,
    )


def emit_task(conversation_id: str, type_: str, task_row: dict) -> None:
    """task.created / task.status — bắn NGUYÊN row (FE upsert theo id, cùng shape REST)."""
    emit(conversation_id, type_, {"task": task_row})


def emit_conversation_status(conversation_id: str, status: str) -> None:
    emit(conversation_id, "conversation.status", {"status": status})


def reset() -> None:
    """Test teardown."""
    _turn_seq.clear()
