"""Fixtures chung — kết nối PG seed thật (D-25: DATABASE_URL). Skip nếu DB không sẵn."""

from __future__ import annotations

import asyncio

import psycopg2
import pytest
from httpx import AsyncClient

from app.db.config import DATABASE_URL


def _db_ready() -> bool:
    """True nếu PG chạy + đã seed (assumptions có dòng). Tránh test đỏ oan khi quên up db/seed."""
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=2)
    except psycopg2.Error:
        return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM assumptions")
        n = cur.fetchone()[0]
        cur.close()
        return n > 0
    except psycopg2.Error:
        return False
    finally:
        conn.close()


requires_db = pytest.mark.skipif(
    not _db_ready(),
    reason="PG chưa sẵn/chưa seed — `docker compose up -d db` + "
    "`uv run alembic upgrade head` + `uv run python -m app.db.seed_from_lab`",
)


@pytest.fixture
def pg_conn():
    """1 psycopg2 conn tươi mỗi test; rollback + close cuối test."""
    conn = psycopg2.connect(DATABASE_URL)
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture(autouse=True)
def _reset_orch_registry():
    """Reset state điều phối in-process giữa các test (tránh leak (conv,role)/slot/queue).
    No-op nếu app.orch chưa hạ cánh."""
    try:
        from app.orch import registry
    except ImportError:
        yield
        return
    registry.reset_all()
    yield
    registry.reset_all()


async def wait_for_conversation_idle(client: AsyncClient, conv_id: str, timeout_s: float = 90.0) -> None:
    """DEDUPE (S4 cuối sprint — 3 bản copy-paste khác nhau ở test_gate_s3_e2e_tester.py,
    test_gate_s4_loop_bound_tester.py, test_gate_s4_audit_tester.py → gộp 1 bản đúng duy nhất,
    chuẩn PROD "không copy-paste logic" áp cả test).

    BÀI HỌC (tester, gate T4-1 — lần chạy đầu FAIL oan): conversation KHỞI TẠO với status='idle'
    MẶC ĐỊNH (store.py _create_conversation_sync) — POST /chat set 'running' bất đồng bộ, có
    khoảng hở giữa 202 response và DB thực sự chuyển 'running'. Poll ngay lập tức có thể đọc
    trúng 'idle' CŨ (chưa từng chạy) rồi trả về SỚM SAI, coi như đã xong khi thực ra còn chưa bắt
    đầu. Fix: đợi thấy 'running' TRƯỚC (xác nhận turn đã thực sự bắt đầu) rồi mới coi 'idle' sau
    đó là ĐÃ XONG."""
    elapsed = 0.0
    interval = 3.0
    seen_running = False
    while elapsed < timeout_s:
        r = await client.get(f"/api/conversations/{conv_id}")
        status = r.json()["conversation"]["status"]
        if status == "running":
            seen_running = True
        elif status == "idle" and seen_running:
            return
        await asyncio.sleep(interval)
        elapsed += interval
    pytest.fail(
        f"conversation KHÔNG về idle-sau-running sau {timeout_s}s (conv_id={conv_id}, "
        f"seen_running={seen_running} — False nghĩa là chưa từng thấy turn thực sự chạy)"
    )
