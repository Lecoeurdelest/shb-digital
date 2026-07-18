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
from app.api.conversations import router as conversations_router
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
        n = await store.cleanup_orphans()
        if n:
            log.info("boot-cleanup: %d task mồ côi → failed(server restart)", n)
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


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}
