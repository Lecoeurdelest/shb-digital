from __future__ import annotations

import os

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db
from .conftest import wait_for_conversation_idle as _wait_for_conversation_idle

_LIVE = os.environ.get("RUN_LIVE_SDK") == "1"


def _seeded(username: str) -> bool:
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=2)
    except psycopg2.Error:
        return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM users WHERE username=%s", (username,))
        return cur.fetchone()[0] >= 1
    except psycopg2.Error:
        return False
    finally:
        conn.close()


def _cleanup_conv(conv_id: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM tasks WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()


async def _login(client: AsyncClient, username: str, password: str):
    return await client.post("/api/auth/login", json={"username": username, "password": password})


# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════


@requires_db
@pytest.mark.asyncio
async def test_api_me_new_route_matches_auth_me():

    if not _seeded("c001"):
        pytest.skip("Required test prerequisite is unavailable.")
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r_login = await _login(client, "c001", "c001")
            assert r_login.status_code == 200

            r_new = await client.get("/api/me")
            r_old = await client.get("/api/auth/me")
            assert r_new.status_code == 200
            assert r_old.status_code == 200
            body_new, body_old = r_new.json(), r_old.json()
            assert body_new["username"] == "c001"
            assert body_new["role"] == "customer"
            assert body_new["owner_id"] == "C001"
            assert body_new == body_old, "Expected invariant was not satisfied at source line 75."


# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════


@requires_db
@pytest.mark.asyncio
async def test_customer_list_only_own_convs_not_others():

    if not _seeded("c001") or not _seeded("b001"):
        pytest.skip("Required test prerequisite is unavailable.")
    conv_c001: str | None = None
    conv_b001: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await _login(client, "c001", "c001")
                r = await client.post("/api/conversations", json={"title": "case-c001-list-test"})
                assert r.status_code == 201
                conv_c001 = r.json()["id"]

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client2:
                await _login(client2, "b001", "b001")
                r2 = await client2.post("/api/conversations", json={"title": "case-b001-list-test"})
                assert r2.status_code == 201
                conv_b001 = r2.json()["id"]

                await _login(client2, "c001", "c001")
                r_list = await client2.get("/api/conversations")
                assert r_list.status_code == 200
                ids = {c["id"] for c in r_list.json()}
                assert conv_c001 in ids, "Expected invariant was not satisfied at source line 109."
                assert conv_b001 not in ids, "Expected invariant was not satisfied at source line 110."
    finally:
        if conv_c001:
            _cleanup_conv(conv_c001)
        if conv_b001:
            _cleanup_conv(conv_b001)


@requires_db
@pytest.mark.asyncio
async def test_admin_list_sees_customer_convs():

    if not _seeded("c001"):
        pytest.skip("Required test prerequisite is unavailable.")
    conv_c001: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await _login(client, "c001", "c001")
                r = await client.post("/api/conversations", json={"title": "case-c001-admin-visibility"})
                assert r.status_code == 201
                conv_c001 = r.json()["id"]

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client2:
                await _login(client2, "admin", "admin")
                r_list = await client2.get("/api/conversations")
                assert r_list.status_code == 200
                ids = {c["id"] for c in r_list.json()}
                assert conv_c001 in ids, "Expected invariant was not satisfied at source line 138."
    finally:
        if conv_c001:
            _cleanup_conv(conv_c001)


# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════


@requires_db
@pytest.mark.asyncio
async def test_customer_chat_into_others_conv_404():

    if not _seeded("c001") or not _seeded("b001"):
        pytest.skip("Required test prerequisite is unavailable.")
    conv_b001: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await _login(client, "b001", "b001")
                r = await client.post("/api/conversations", json={"title": "case-b001-chat-guard"})
                assert r.status_code == 201
                conv_b001 = r.json()["id"]

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client2:
                await _login(client2, "c001", "c001")
                r_chat = await client2.post(f"/api/conversations/{conv_b001}/chat", json={"content": "hello"})
                assert r_chat.status_code == 404, "Expected invariant was not satisfied at source line 167."
                body = r_chat.json()
                assert set(body) == {"code", "message", "hint", "retryable"}
                assert body["code"] == "not_found"

            conn = psycopg2.connect(DATABASE_URL)
            try:
                cur = conn.cursor()
                cur.execute("SELECT count(*) FROM messages WHERE conv_id=%s AND content=%s", (conv_b001, "hello"))
                assert cur.fetchone()[0] == 0, "Expected invariant was not satisfied at source line 178."
            finally:
                conn.close()
    finally:
        if conv_b001:
            _cleanup_conv(conv_b001)


# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════


@requires_db
@pytest.mark.asyncio
async def test_customer_sse_others_conv_404():

    if not _seeded("c001") or not _seeded("b001"):
        pytest.skip("Required test prerequisite is unavailable.")
    conv_b001: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await _login(client, "b001", "b001")
                r = await client.post("/api/conversations", json={"title": "case-b001-sse-guard"})
                assert r.status_code == 201
                conv_b001 = r.json()["id"]

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client2:
                await _login(client2, "c001", "c001")
                async with client2.stream("GET", f"/api/conversations/{conv_b001}/sse") as r_sse:
                    assert r_sse.status_code == 404, "Expected invariant was not satisfied at source line 209."
    finally:
        if conv_b001:
            _cleanup_conv(conv_b001)


@requires_db
@pytest.mark.asyncio
async def test_customer_interrupt_others_conv_404():

    if not _seeded("c001") or not _seeded("b001"):
        pytest.skip("Required test prerequisite is unavailable.")
    conv_b001: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await _login(client, "b001", "b001")
                r = await client.post("/api/conversations", json={"title": "case-b001-interrupt-guard"})
                assert r.status_code == 201
                conv_b001 = r.json()["id"]

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client2:
                await _login(client2, "c001", "c001")
                r_int = await client2.post(f"/api/conversations/{conv_b001}/interrupt", json={"target": "some-task-id"})
                assert r_int.status_code == 404, "Expected invariant was not satisfied at source line 233."
    finally:
        if conv_b001:
            _cleanup_conv(conv_b001)


# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════

pytestmark_live = pytest.mark.skipif(not _LIVE, reason="Optional integration prerequisite is unavailable.")


@requires_db
@pytestmark_live
@pytest.mark.asyncio
async def test_main_inject_live_customer_gets_anh_chi_tone():

    if not _seeded("c001"):
        pytest.skip("Required test prerequisite is unavailable.")
    conv_id: str | None = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120.0) as client:
                await _login(client, "c001", "c001")
                r = await client.post("/api/conversations", json={"title": "live-main-inject-c001"})
                assert r.status_code == 201
                conv_id = r.json()["id"]

                r_chat = await client.post(
                    f"/api/conversations/{conv_id}/chat",
                    json={"content": "Hello, what is the current status of my loan?"},
                )
                assert r_chat.status_code == 202

                await _wait_for_conversation_idle(client, conv_id, timeout_s=90.0)

                r_state = await client.get(f"/api/conversations/{conv_id}")
                assert r_state.status_code == 200
                messages = r_state.json().get("messages", [])
                assistant_msgs = [m["content"] for m in messages if m.get("sender") == "assistant"]
                assert assistant_msgs, "Expected invariant was not satisfied at source line 277."
                combined = " ".join(assistant_msgs).lower()

                leaked_terms = [t for t in ("credit_assess", "tool_call", "dispatch", "sub-agent") if t in combined]
                assert not leaked_terms, "Expected invariant was not satisfied at source line 281."

                _cleanup_conv(conv_id)
    except AssertionError:
        raise
