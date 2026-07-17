"""FastAPI app entrypoint — S1 scaffold nền (T1-1).

Có: health + auth (login, JWT cookie, 2 account seed). Error envelope 4-field toàn hệ.
Orchestrator/chat/SSE routes land in T1-2/T1-3 (out of scope here — sẽ thêm router).
"""

from __future__ import annotations

from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.errors import register_error_handler

app = FastAPI(title="SHB Digital Expert Guild")

register_error_handler(app)  # ApiError + validation → body 4-field trần (CONTRACT §0)
app.include_router(auth_router)


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}
