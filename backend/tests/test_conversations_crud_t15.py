from __future__ import annotations

import psycopg2
import psycopg2.extras
from fastapi.testclient import TestClient

from app.db.config import DATABASE_URL
from app.main import app
from app.orch import registry

from .conftest import requires_db

client = TestClient(app)


def _admin():
    return client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).cookies


def _mk_conv(title: str = "Test case", provider: str | None = None, model: str | None = None) -> str:
    r = client.post(
        "/api/conversations",
        json={"title": title, "provider": provider, "model": model},
        cookies=_admin(),
    )
    return r.json()["id"]


def _raw(sql: str, args: tuple = ()) -> list:
    c = psycopg2.connect(DATABASE_URL)
    c.autocommit = True
    try:
        with c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, args)
            return cur.fetchall() if cur.description else []
    finally:
        c.close()


def _cleanup(conv_id: str) -> None:
    _raw("DELETE FROM approvals WHERE conv_id=%s", (conv_id,))
    _raw("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
    _raw("DELETE FROM tasks WHERE conv_id=%s", (conv_id,))
    _raw("DELETE FROM messages WHERE conv_id=%s", (conv_id,))
    _raw("DELETE FROM conversations WHERE id::text=%s", (conv_id,))


# ── PATCH rename + switch ────────────────────────────────────────────────────


@requires_db
def test_patch_rename_title():
    cid = _mk_conv("Old title")
    try:
        r = client.patch(f"/api/conversations/{cid}", json={"title": "New title"}, cookies=_admin())
        assert r.status_code == 200
        assert r.json()["title"] == "New title"

        assert _raw("SELECT title FROM conversations WHERE id::text=%s", (cid,))[0]["title"] == "New title"
    finally:
        _cleanup(cid)


@requires_db
def test_patch_switch_provider_and_model_valid():

    cid = _mk_conv("Switch", provider="zai", model="glm-4.6")
    try:
        r = client.patch(
            f"/api/conversations/{cid}",
            json={"provider": "wrap", "model": "gpt-5.5"},
            cookies=_admin(),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["provider"] == "wrap" and body["model"] == "gpt-5.5"
        row = _raw("SELECT provider, model FROM conversations WHERE id::text=%s", (cid,))[0]
        assert row["provider"] == "wrap" and row["model"] == "gpt-5.5"  # persisted
    finally:
        _cleanup(cid)


@requires_db
def test_patch_bad_provider_400():
    cid = _mk_conv()
    try:
        r = client.patch(f"/api/conversations/{cid}", json={"provider": "ghost-x"}, cookies=_admin())
        assert r.status_code == 400
        assert r.json()["code"] == "bad_provider"
    finally:
        _cleanup(cid)


@requires_db
def test_patch_bad_model_for_provider_400():

    cid = _mk_conv()
    try:
        r = client.patch(
            f"/api/conversations/{cid}",
            json={"provider": "zai", "model": "gpt-5.5"},
            cookies=_admin(),
        )
        assert r.status_code == 400
        assert r.json()["code"] == "bad_model"
    finally:
        _cleanup(cid)


@requires_db
def test_patch_model_only_validated_against_current_provider():

    cid = _mk_conv("model-only", provider="wrap", model="gpt-5.5")
    try:
        ok = client.patch(f"/api/conversations/{cid}", json={"model": "gpt-5.4"}, cookies=_admin())
        assert ok.status_code == 200 and ok.json()["model"] == "gpt-5.4"

        bad = client.patch(f"/api/conversations/{cid}", json={"model": "glm-4.6"}, cookies=_admin())
        assert bad.status_code == 400 and bad.json()["code"] == "bad_model"
    finally:
        _cleanup(cid)


@requires_db
def test_patch_empty_body_400():
    cid = _mk_conv()
    try:
        r = client.patch(f"/api/conversations/{cid}", json={}, cookies=_admin())
        assert r.status_code == 400
        assert r.json()["code"] == "empty_patch"
    finally:
        _cleanup(cid)


@requires_db
def test_patch_other_users_conv_404_hide():

    import uuid

    u1 = "pt1_" + uuid.uuid4().hex[:6]
    u2 = "pt2_" + uuid.uuid4().hex[:6]
    r1 = client.post("/api/auth/register", json={"username": u1, "password": "pass1"})
    cid = client.post("/api/conversations", json={"title": "owned by u1"}, cookies=r1.cookies).json()["id"]
    r2 = client.post("/api/auth/register", json={"username": u2, "password": "pass1"})
    try:
        r = client.patch(f"/api/conversations/{cid}", json={"title": "hijack"}, cookies=r2.cookies)
        assert r.status_code == 404
        assert r.json()["code"] == "not_found"
    finally:
        _cleanup(cid)
        for u in (u1, u2):
            _raw("DELETE FROM users WHERE username=%s", (u,))


@requires_db
def test_patch_switch_while_running_409_but_rename_ok():

    cid = _mk_conv("running", provider="zai", model="glm-4.6")
    registry.mark_busy(cid)
    try:
        # switch → 409
        sw = client.patch(f"/api/conversations/{cid}", json={"provider": "wrap"}, cookies=_admin())
        assert sw.status_code == 409 and sw.json()["code"] == "conv_running"

        rn = client.patch(f"/api/conversations/{cid}", json={"title": "rename while running"}, cookies=_admin())
        assert rn.status_code == 200 and rn.json()["title"] == "rename while running"
    finally:
        registry.clear_busy(cid)
        _cleanup(cid)


# ── DELETE hard + cascade + audit-keep ───────────────────────────────────────


@requires_db
def test_delete_happy_cascades_content_keeps_audit():

    cid = _mk_conv("to delete")

    _raw("INSERT INTO messages (conv_id,ts,sender,content) VALUES (%s,now(),'user','hi')", (cid,))
    _raw("INSERT INTO cards (conv_id,type,data,ts) VALUES (%s,'metric','{}',now())", (cid,))
    _raw("INSERT INTO tasks (conv_id,role,title,status,queued_at) VALUES (%s,'credit','t','done',now())", (cid,))
    _raw(
        "INSERT INTO approvals (conv_id,action,payload,payload_hash,status,decided_by,decided_at) "
        "VALUES (%s,'disburse','{}','t15h1','approved','admin',now())",
        (cid,),
    )
    _raw(
        "INSERT INTO tool_calls (conv_id,actor,tool,input,output,ts) VALUES (%s,'main','calc','{}','{}',now())",
        (cid,),
    )
    try:
        r = client.delete(f"/api/conversations/{cid}", cookies=_admin())
        assert r.status_code == 200 and r.json()["deleted"] is True

        assert _raw("SELECT 1 FROM conversations WHERE id::text=%s", (cid,)) == []
        assert _raw("SELECT 1 FROM messages WHERE conv_id=%s", (cid,)) == []
        assert _raw("SELECT 1 FROM cards WHERE conv_id=%s", (cid,)) == []
        assert _raw("SELECT 1 FROM tasks WHERE conv_id=%s", (cid,)) == []

        assert len(_raw("SELECT 1 FROM approvals WHERE conv_id=%s", (cid,))) == 1
        assert len(_raw("SELECT 1 FROM tool_calls WHERE conv_id=%s", (cid,))) == 1
    finally:
        _cleanup(cid)
        _raw("DELETE FROM tool_calls WHERE conv_id=%s", (cid,))


@requires_db
def test_delete_blocked_when_pending_approval_409():
    cid = _mk_conv("has pending approval")
    _raw(
        "INSERT INTO approvals (conv_id,action,payload,payload_hash,status) "
        "VALUES (%s,'disburse','{}','t15pend','pending')",
        (cid,),
    )
    try:
        r = client.delete(f"/api/conversations/{cid}", cookies=_admin())
        assert r.status_code == 409
        assert r.json()["code"] == "has_pending_approval"

        assert len(_raw("SELECT 1 FROM conversations WHERE id::text=%s", (cid,))) == 1
    finally:
        _cleanup(cid)


@requires_db
def test_delete_blocked_when_running_409():
    cid = _mk_conv("running")
    registry.mark_busy(cid)
    try:
        r = client.delete(f"/api/conversations/{cid}", cookies=_admin())
        assert r.status_code == 409 and r.json()["code"] == "conv_running"
        assert len(_raw("SELECT 1 FROM conversations WHERE id::text=%s", (cid,))) == 1
    finally:
        registry.clear_busy(cid)
        _cleanup(cid)


@requires_db
def test_delete_nonexistent_404():
    import uuid

    r = client.delete(f"/api/conversations/{uuid.uuid4()}", cookies=_admin())
    assert r.status_code == 404
    assert r.json()["code"] == "not_found"


@requires_db
def test_delete_twice_second_404():

    cid = _mk_conv("delete twice")
    r1 = client.delete(f"/api/conversations/{cid}", cookies=_admin())
    assert r1.status_code == 200
    r2 = client.delete(f"/api/conversations/{cid}", cookies=_admin())
    assert r2.status_code == 404
