from __future__ import annotations

import asyncio
import os
import warnings
from pathlib import Path

_TEST_DB = os.environ.get("TEST_DATABASE_URL")
if _TEST_DB:
    os.environ["DATABASE_URL"] = _TEST_DB  # test conn + app-under-test → test-db
else:
    warnings.warn(
        "TEST_DATABASE_URL is not set; tests would run against the PRIMARY database and pollute the demo queue. "
        "Set TEST_DATABASE_URL=postgresql://shb:shb@localhost:5432/shb_test to isolate tests.",
        stacklevel=2,
    )

import psycopg2  # noqa: E402
import pytest  # noqa: E402
from httpx import AsyncClient  # noqa: E402

from app.db.config import DATABASE_URL  # noqa: E402


def _db_ready() -> bool:

    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=2)
    except psycopg2.Error:
        return False
    try:
        cur = conn.cursor()

        cur.execute("SELECT (SELECT count(*) FROM assumptions), (SELECT count(*) FROM users)")
        n_assum, n_users = cur.fetchone()
        cur.close()
        return n_assum > 0 and n_users > 0
    except psycopg2.Error:
        return False
    finally:
        conn.close()


def _db_at_migration_head() -> bool:

    conn = None
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        expected = set(ScriptDirectory.from_config(config).get_heads())
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=2)
        with conn.cursor() as cur:
            cur.execute("SELECT version_num FROM alembic_version")
            actual = {row[0] for row in cur.fetchall()}
        return actual == expected
    except Exception:
        return False
    finally:
        if conn is not None:
            conn.close()


def _ensure_test_db() -> None:

    if not _TEST_DB:
        return
    import re
    import subprocess

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
            return

    env = {**os.environ, "DATABASE_URL": _TEST_DB}
    if not _db_at_migration_head():
        subprocess.run(["uv", "run", "alembic", "upgrade", "head"], env=env, check=True, capture_output=True)
    if not _db_ready():
        subprocess.run(["uv", "run", "python", "-m", "app.db.seed_from_lab"], env=env, check=True, capture_output=True)

        subprocess.run(["uv", "run", "python", "-m", "app.db.seed_users"], env=env, check=True, capture_output=True)


_ensure_test_db()


requires_db = pytest.mark.skipif(
    not _db_ready(),
    reason="Optional integration prerequisite is unavailable.",
)


requires_test_db = pytest.mark.skipif(
    not _TEST_DB or not _db_ready(),
    reason="Optional integration prerequisite is unavailable.",
)


def _embed_ready() -> bool:

    import importlib.util

    return all(importlib.util.find_spec(m) is not None for m in ("sentence_transformers", "pyvi", "numpy"))


requires_embed = pytest.mark.skipif(
    not _embed_ready(),
    reason="Optional integration prerequisite is unavailable.",
)


@pytest.fixture
def pg_conn():

    conn = psycopg2.connect(DATABASE_URL)
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture(autouse=True)
def _reset_orch_registry():

    try:
        from app.orch import registry
    except ImportError:
        yield
        return
    registry.reset_all()
    yield
    registry.reset_all()


async def wait_for_conversation_idle(client: AsyncClient, conv_id: str, timeout_s: float = 90.0) -> None:

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
    pytest.fail("Expected condition was not met at source line 163.")
