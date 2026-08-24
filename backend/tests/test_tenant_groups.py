"""D-79 tenant isolation and conversation-group observable contract."""

from __future__ import annotations

from uuid import uuid4

import psycopg2
from fastapi.testclient import TestClient

from app.auth.security import make_token
from app.db.config import DATABASE_URL
from app.main import app
from app.tenancy import DEFAULT_TENANT_ID

from .conftest import requires_test_db

client = TestClient(app)


def _admin_headers(tenant_id: str, username: str) -> dict[str, str]:
    token = make_token(user_id=str(uuid4()), username=username, role="admin", tenant_id=tenant_id)
    return {"Authorization": f"Bearer {token}"}


@requires_test_db
def test_group_crud_assign_and_delete_ungroups_conversation():
    headers = _admin_headers(DEFAULT_TENANT_ID, "tenant-group-admin")
    name = f"Doanh nghiệp {uuid4().hex[:8]}"

    created = client.post("/api/conversation-groups", json={"name": f"  {name}  "}, headers=headers)
    assert created.status_code == 201
    group = created.json()
    assert group["name"] == name

    duplicate = client.post("/api/conversation-groups", json={"name": name.upper()}, headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "group_name_conflict"

    conv_response = client.post(
        "/api/conversations",
        json={"title": "Phiên trong nhóm", "group_id": group["id"]},
        headers=headers,
    )
    assert conv_response.status_code == 201
    conv = conv_response.json()
    assert conv["tenant_id"] == DEFAULT_TENANT_ID
    assert conv["group_id"] == group["id"]
    assert group["id"] in {row["id"] for row in client.get("/api/conversation-groups", headers=headers).json()}

    deleted = client.delete(f"/api/conversation-groups/{group['id']}", headers=headers)
    assert deleted.status_code == 200
    state = client.get(f"/api/conversations/{conv['id']}", headers=headers).json()
    assert state["conversation"]["group_id"] is None

    assert client.delete(f"/api/conversations/{conv['id']}", headers=headers).status_code == 200


@requires_test_db
def test_admin_endpoints_hide_other_tenant_conversation_and_ledgers():
    tenant_b = str(uuid4())
    headers_a = _admin_headers(DEFAULT_TENANT_ID, "admin-a")
    headers_b = _admin_headers(tenant_b, "admin-b")
    marker = uuid4().hex

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tenants(id,slug,name) VALUES(%s,%s,%s)", (tenant_b, f"tenant-{marker}", "Tenant B"))
    conn.close()

    group_b: dict = {}
    conv_b: dict = {}
    conv_a: dict = {}
    try:
        group_b = client.post(
            "/api/conversation-groups", json={"name": f"Nhóm B {marker[:6]}"}, headers=headers_b
        ).json()
        conv_b = client.post(
            "/api/conversations",
            json={"title": "Tenant B only", "group_id": group_b["id"]},
            headers=headers_b,
        ).json()
        conv_a = client.post("/api/conversations", json={"title": "Tenant A"}, headers=headers_a).json()

        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO approvals(tenant_id,conv_id,action,payload,payload_hash,status,idempotency_key) "
                "VALUES(%s,%s,'disburse','{}',%s,'pending',%s) RETURNING id::text",
                (tenant_b, conv_b["id"], marker, f"tenant-test:{marker}"),
            )
            approval_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO tool_calls(tenant_id,conv_id,actor,tool,input) VALUES(%s,%s,'main',%s,'{}')",
                (tenant_b, conv_b["id"], f"tenant_tool_{marker}"),
            )
            cur.execute(
                "INSERT INTO assessments(tenant_id,owner_id,lane,created_at) VALUES(%s,%s,'green',now()::text)",
                (tenant_b, f"OWNER-{marker}"),
            )
        conn.close()

        ids_a = {row["id"] for row in client.get("/api/conversations", headers=headers_a).json()}
        ids_b = {row["id"] for row in client.get("/api/conversations", headers=headers_b).json()}
        assert conv_b["id"] not in ids_a
        assert conv_b["id"] in ids_b
        assert client.get(f"/api/conversations/{conv_b['id']}", headers=headers_a).status_code == 404

        cross_group = client.patch(
            f"/api/conversations/{conv_a['id']}",
            json={"group_id": group_b["id"]},
            headers=headers_a,
        )
        assert cross_group.status_code == 404
        assert cross_group.json()["code"] == "group_not_found"

        assert client.get(f"/api/approvals/{approval_id}", headers=headers_a).status_code == 404
        assert client.get(f"/api/approvals/{approval_id}", headers=headers_b).status_code == 200
        assert client.get(f"/api/audit?tool=tenant_tool_{marker}", headers=headers_a).json() == []
        assert len(client.get(f"/api/audit?tool=tenant_tool_{marker}", headers=headers_b).json()) == 1
        assert client.get(f"/api/assessments?owner=OWNER-{marker}", headers=headers_a).json() == []
        assert len(client.get(f"/api/assessments?owner=OWNER-{marker}", headers=headers_b).json()) == 1
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DELETE FROM shadow_reviews WHERE tenant_id=%s", (tenant_b,))
            cur.execute("DELETE FROM approvals WHERE tenant_id=%s", (tenant_b,))
            cur.execute("DELETE FROM tool_calls WHERE tenant_id=%s", (tenant_b,))
            cur.execute("DELETE FROM assessments WHERE tenant_id=%s", (tenant_b,))
            cur.execute("DELETE FROM conversations WHERE tenant_id=%s", (tenant_b,))
            cur.execute("DELETE FROM conversation_groups WHERE tenant_id=%s", (tenant_b,))
            cur.execute("DELETE FROM tenants WHERE id=%s", (tenant_b,))
        conn.close()
        if conv_a.get("id"):
            client.delete(f"/api/conversations/{conv_a['id']}", headers=headers_a)
