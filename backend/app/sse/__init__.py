"""SSE realtime FE↔BE (SPEC §9, streaming-sse.md). In-process 1-worker fanout (N4, không Redis).

DB là nguồn sự thật render; SSE chỉ thông báo. Mất event → FE refetch GET /conversations/{id}.
- bus.py    — fanout {conv_id: set[Queue]}, publish put_nowait (không block)
- redact.py — lọc secret trước khi bắn (khẩu vị bank)
- emit.py   — envelope 1 shape + seq per-turn + cổng bắn duy nhất
"""
