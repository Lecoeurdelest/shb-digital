"""Fixtures chung — kết nối PG seed thật. Skip nếu DB không sẵn.

TÁCH DB TEST (luật vận hành → code): test chạy DB RIÊNG (TEST_DATABASE_URL, mặc định `shb_test`)
để KHÔNG bơm rác vào queue/Control Tower DB demo. Override env `DATABASE_URL=<test-db>` NGAY ĐẦU
file — TRƯỚC bất kỳ `from app.db.config import` (config đọc env lúc import) → cả app-under-test +
test conn dùng test-db trong phiên test. env TEST_DATABASE_URL không set → dùng DB chính (dev
nhanh) + WARNING (tránh bơm rác demo mà không biết).

LUẬT TEST PHÁ HOẠI = ENV-GATED (T7-4 rider — sự cố thật: test reset_demo wipe DEMO DB khi tester
quên TEST_DATABASE_URL, warning KHÔNG đủ chặn). Mọi test GỌI reset_demo / TRUNCATE / xoá runtime
trên DATABASE_URL PHẢI mang `@requires_test_db` (skip cứng khi thiếu TEST_DATABASE_URL) — KHÔNG
BAO GIỜ chạy trên DB chính kể cả có warning. Test chỉ SEED thêm row (assessments) rồi tự dọn thì
`@requires_db` đủ; test WIPE/reset toàn bộ = `@requires_test_db`.

LUẬT TEST KHÔNG PHỤ THUỘC SECRET THẬT (T11-1 CI — sự cố thật: test_conv_provider_env_keyed FAIL
trên CI vì .env gitignored không có key zai). Test cần key provider/SMTP chỉ để kiểm SHAPE (env
inject, không gọi API) → `monkeypatch.setenv("zai"/"WRAP_API_KEY", "dummy")` (reload đọc os.environ
merge-over .env). Test NÀO thật sự gọi API bằng key → env-gate skip như live-SDK (RUN_LIVE_SDK).
Local-mirror phải mirror cả SỰ VẮNG MẶT secret: verify bằng `mv .env /tmp && pytest && mv lại`.
"""

from __future__ import annotations

import asyncio
import os
import warnings

# ⚠️ PHẢI set env TRƯỚC mọi app import (config.py đọc os.environ lúc import module).
_TEST_DB = os.environ.get("TEST_DATABASE_URL")
if _TEST_DB:
    os.environ["DATABASE_URL"] = _TEST_DB  # test conn + app-under-test → test-db
else:
    warnings.warn(
        "TEST_DATABASE_URL không set — test chạy trên DB CHÍNH (bơm rác vào queue/Tower demo). "
        "Set TEST_DATABASE_URL=postgresql://shb:shb@localhost:5432/shb_test để tách.",
        stacklevel=2,
    )

import psycopg2  # noqa: E402
import pytest  # noqa: E402
from httpx import AsyncClient  # noqa: E402

from app.db.config import DATABASE_URL  # noqa: E402 — sau khi override env ở trên


def _db_ready() -> bool:
    """True nếu PG chạy + đã seed (assumptions có dòng). Tránh test đỏ oan khi quên up db/seed."""
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=2)
    except psycopg2.Error:
        return False
    try:
        cur = conn.cursor()
        # seed đủ = nghiệp vụ (assumptions) VÀ users (auth) — half-setup (nghiệp vụ có, users thiếu →
        # login 401 oan) → coi CHƯA sẵn để _ensure_test_db seed_users lại (edge tách-DB test).
        cur.execute("SELECT (SELECT count(*) FROM assumptions), (SELECT count(*) FROM users)")
        n_assum, n_users = cur.fetchone()
        cur.close()
        return n_assum > 0 and n_users > 0
    except psycopg2.Error:
        return False
    finally:
        conn.close()


def _ensure_test_db() -> None:
    """Auto-setup test-db (CHỈ khi TEST_DATABASE_URL set + db đó CHƯA seed): CREATE DATABASE (nếu
    thiếu) → migrate head → seed. Idempotent — chạy lại no-op nếu đã seed. KHÔNG đụng DB chính
    (chỉ chạy khi có TEST_DATABASE_URL riêng)."""
    if not _TEST_DB or _db_ready():
        return  # không có test-db riêng, HOẶC test-db đã sẵn → không setup lại
    import re
    import subprocess

    # CREATE DATABASE <test> nếu chưa có — connect tới db 'postgres' (admin), tách tên db test.
    m = re.match(r"(postgresql://[^/]+)/(\w+)", _TEST_DB)
    if m:
        base, dbname = m.group(1), m.group(2)
        try:
            admin = psycopg2.connect(f"{base}/postgres", connect_timeout=2)
            admin.autocommit = True
            with admin.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (dbname,))
                if not cur.fetchone():
                    cur.execute(f'CREATE DATABASE "{dbname}"')
            admin.close()
        except psycopg2.Error:
            return  # không tạo được (quyền/conn) → _db_ready vẫn False → test skip với reason
    # migrate head + seed nghiệp vụ + seed users (auth) trên test-db. DATABASE_URL đã trỏ test-db.
    env = {**os.environ, "DATABASE_URL": _TEST_DB}
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], env=env, check=False, capture_output=True)
    subprocess.run(["uv", "run", "python", "-m", "app.db.seed_from_lab"], env=env, check=False, capture_output=True)
    # seed users (admin/user) — test authz/login CẦN (thiếu → login 401 thay verdict thật).
    subprocess.run(["uv", "run", "python", "-m", "app.db.seed_users"], env=env, check=False, capture_output=True)


_ensure_test_db()  # session-setup 1 lần lúc load conftest (sau override env, trước collection).


requires_db = pytest.mark.skipif(
    not _db_ready(),
    reason="PG chưa sẵn/chưa seed — `docker compose up -d db` + "
    "`uv run alembic upgrade head` + `uv run python -m app.db.seed_from_lab` "
    "(hoặc set TEST_DATABASE_URL để auto-setup test-db riêng)",
)

# GATE PHÁ HOẠI (T7-4 rider): test WIPE/reset toàn bộ (reset_demo, TRUNCATE runtime) → SKIP CỨNG
# khi thiếu TEST_DATABASE_URL — chặn wipe nhầm DB chính dù DB chính đang seeded (requires_db pass).
# Chồng requires_db: phải CÓ test-db riêng VÀ db sẵn. Warning không đủ — người quên env vẫn bị chặn.
requires_test_db = pytest.mark.skipif(
    not _TEST_DB or not _db_ready(),
    reason="TEST PHÁ HOẠI (reset/wipe) — CHỈ chạy khi TEST_DATABASE_URL set (test-db riêng). "
    "Không set → skip để KHÔNG wipe DB chính. Set TEST_DATABASE_URL=postgresql://shb:shb@localhost:5432/shb_test.",
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
