"""FastAPI app entrypoint — S1 scaffold nền (T1-1) + orchestrator boot (T1-2).

Có: health + auth (login, JWT cookie, 2 account seed). Error envelope 4-field toàn hệ.
Startup: boot orchestrator (gán SDK runner cho seam + nối event sink) + dọn task mồ côi (§7).
Chat/SSE routes land in T1-3 (dùng orch.room.handle_room_event).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.approvals import router as approvals_router
from app.api.audit import router as audit_router
from app.api.compare import router as compare_router
from app.api.conversations import router as conversations_router
from app.api.interrupt import router as interrupt_router
from app.api.models import router as models_router
from app.api.sse import router as sse_router
from app.auth.router import router as auth_router
from app.errors import register_error_handler

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # boot-cleanup (§7): task DB queued/running mồ côi từ đời trước → failed('server restart')
    # DEV_SKIP_AUTH cảnh báo (D-39): flag ON → mọi request = admin, không được dùng prod/demo thật
    from app.config import DEV_SKIP_AUTH
    from app.orch import main_session, registry, store

    if DEV_SKIP_AUTH:
        log.warning("⚠️  DEV_SKIP_AUTH ON — mọi request = admin, BỎ auth. KHÔNG dùng prod/demo thật.")

    registry.reset_all()
    try:
        # S6 (A): boot_time NGAY đầu startup → cleanup chỉ quét task ĐỜI TRƯỚC (queued_at < boot_time),
        # KHÔNG quét task đời-này. datetime.now(UTC) khớp queued_at (timestamptz).
        from datetime import UTC, datetime

        boot_time = datetime.now(UTC)
        n = await store.cleanup_orphans(boot_time)
        if n:
            log.info("boot-cleanup: %d task mồ côi (đời trước) → failed(server restart)", n)
    except Exception as e:  # noqa: BLE001 — DB chưa sẵn lúc boot không được chặn app lên
        log.warning("boot-cleanup skip (DB?): %s", e)
    main_session.boot()  # gán SDK runner cho seam + nối event sink (sub xong → wake main)
    yield


app = FastAPI(title="SHB Digital Expert Guild", lifespan=lifespan)

register_error_handler(app)  # ApiError + validation → body 4-field trần (CONTRACT §0)
app.include_router(auth_router)
app.include_router(conversations_router)  # conversations + chat (T1-3)
app.include_router(sse_router)  # SSE stream (T1-3)
app.include_router(approvals_router)  # approvals decide + list (T3-2)
app.include_router(models_router)  # providers/models cho FE dropdown (D-45b)
app.include_router(audit_router)  # tool_calls audit search (T4-1 §11)
app.include_router(interrupt_router)  # POST /interrupt huỷ sub (T4-3 §4.3)
app.include_router(compare_router)  # POST /compare single vs multi (T4-4 deliverable #5)


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}
