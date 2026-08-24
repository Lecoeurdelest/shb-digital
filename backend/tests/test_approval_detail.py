"""S19 admin approval detail: mọi status, enrichment dùng chung và bề mặt lỗi kín."""

from __future__ import annotations

import json
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db


def _insert_approval(status: str) -> tuple[str, str]:
    conv = f"s19-detail-{uuid4()}"
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO approvals "
                "(conv_id, action, payload, payload_hash, status, decided_by, decided_at, reason, "
                "used_at, receipt) VALUES (%s,'disburse',%s,%s,%s,%s,"
                "CASE WHEN %s='pending' THEN NULL ELSE now() END,%s,"
                "CASE WHEN %s='used' THEN now() ELSE NULL END,%s) RETURNING id",
                (
                    conv,
                    json.dumps({"loan_id": "L001", "amount": 500_000_000}),
                    uuid4().hex[:16],
                    status,
                    None if status == "pending" else "admin",
                    status,
                    None if status == "pending" else "reviewed",
                    status,
                    json.dumps({"ok": True}) if status == "used" else None,
                ),
            )
            return str(cur.fetchone()[0]), conv
    finally:
        conn.close()


def _cleanup(conv: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM shadow_reviews WHERE conv_id=%s", (conv,))
            cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv,))
    finally:
        conn.close()


def _login(username: str, password: str):
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.cookies


@requires_db
@pytest.mark.parametrize("status", ["pending", "approved", "rejected", "used", "exec_failed"])
def test_admin_get_approval_across_statuses_with_display(status: str):
    approval_id, conv = _insert_approval(status)
    try:
        response = TestClient(app).get(f"/api/approvals/{approval_id}", cookies=_login("admin", "admin"))
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == approval_id
        assert body["status"] == status
        display = body["display"]
        assert set(display) == {"customer_name", "owner_id", "loan_id", "amount_vnd", "lane"}
        assert display["customer_name"] == "Nguyễn Văn An"
        assert display["owner_id"] == "C001"
        assert display["loan_id"] == "L001"
        assert display["amount_vnd"] == 500_000_000
        assert set(body) == {
            "id",
            "conv_id",
            "task_id",
            "action",
            "payload",
            "payload_hash",
            "status",
            "decided_by",
            "decided_at",
            "reason",
            "used_at",
            "receipt",
            "exec_attempts",
            "display",
        }
    finally:
        _cleanup(conv)


@requires_db
def test_get_approval_unknown_and_malformed_are_exact_404():
    cookies = _login("admin", "admin")
    for approval_id in (str(uuid4()), "not-a-uuid"):
        response = TestClient(app).get(f"/api/approvals/{approval_id}", cookies=cookies)
        assert response.status_code == 404
        assert response.json() == {
            "code": "not_found",
            "message": f"Không có phiếu '{approval_id}'.",
            "hint": "Kiểm lại id hoặc liên kết.",
            "retryable": False,
        }


def test_get_approval_requires_auth_before_lookup():
    response = TestClient(app).get("/api/approvals/not-a-uuid")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


@requires_db
@pytest.mark.parametrize(("username", "password"), [("user", "user"), ("c001", "c001")])
def test_get_approval_forbidden_for_non_admin(username: str, password: str):
    response = TestClient(app).get("/api/approvals/not-a-uuid", cookies=_login(username, password))
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
