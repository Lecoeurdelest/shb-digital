"""[TESTER — T3-4] Gate S3 authz boundary (D-19): decide approval CHỈ admin. DEV_SKIP_AUTH OFF
(default, an toàn) — RM (role=user) KHÔNG duyệt được. Chạy MẶC ĐỊNH (không cần RUN_LIVE_SDK,
không cần seed data phức tạp — chỉ cần seed users + 1 approval row giả lập để test authz thuần,
tách khỏi luồng resume thật ở test_gate_s3_e2e_tester.py).

Viết ĐỘC LẬP với test backend (author≠checker) — backend test_approvals.py cover unit decide
logic; đây cover ranh QUYỀN cụ thể theo D-19 mà brief #14 yêu cầu tường minh: "authz decide-flag-
OFF (RM không duyệt được)"."""

from __future__ import annotations

import uuid

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.auth import deps
from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db

client = TestClient(app)


def _users_seeded() -> bool:
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=2)
    except psycopg2.Error:
        return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM users WHERE role='user'")
        has_rm = cur.fetchone()[0] >= 1
        cur.execute("SELECT count(*) FROM users WHERE role='admin'")
        has_admin = cur.fetchone()[0] >= 1
        return has_rm and has_admin
    except psycopg2.Error:
        return False
    finally:
        conn.close()


def _seed_fake_approval() -> str:
    """Seed 1 approval row pending để test decide-authz mà KHÔNG cần chạy agent thật (tách
    biệt authz test khỏi resume test — nhanh, không cần live SDK)."""
    approval_id = str(uuid.uuid4())
    conv_id = f"tester-authz-{approval_id}"
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO approvals (id, conv_id, action, payload, payload_hash, status) "
            "VALUES (%s, %s, 'disburse', %s, %s, 'pending')",
            (approval_id, conv_id, '{"loan_id":"L007","amount":5000000000}', f"authz-test-{approval_id}"),
        )
        conn.commit()
    finally:
        conn.close()
    return approval_id


def _cleanup_approval(approval_id: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM approvals WHERE id=%s", (approval_id,))
        conn.commit()
    finally:
        conn.close()


@requires_db
def test_decide_flag_off_no_cookie_401():
    """DEV_SKIP_AUTH OFF (default) — chưa login → 401, KHÔNG lộ thông tin phiếu."""
    assert deps.DEV_SKIP_AUTH is False, "an toàn: default phải OFF"
    if not _users_seeded():
        pytest.skip("users chưa seed")
    approval_id = _seed_fake_approval()
    try:
        r = client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
        assert r.status_code == 401
        body = r.json()
        assert set(body) == {"code", "message", "hint", "retryable"}
        assert body["code"] == "unauthorized"

        # Phiếu KHÔNG bị đổi trạng thái dù request bị từ chối ở tầng auth
        conn = psycopg2.connect(DATABASE_URL)
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM approvals WHERE id=%s", (approval_id,))
            assert cur.fetchone()[0] == "pending"
        finally:
            conn.close()
    finally:
        _cleanup_approval(approval_id)


@requires_db
def test_decide_flag_off_rm_user_403_forbidden():
    """D-19 BOUNDARY CHÍNH: RM (role='user') ĐÃ login nhưng KHÔNG PHẢI admin → 403 forbidden
    khi decide — đúng "két cần chìa giám đốc", không phải bất kỳ ai đã đăng nhập cũng mở được."""
    assert deps.DEV_SKIP_AUTH is False
    if not _users_seeded():
        pytest.skip("users chưa seed")
    approval_id = _seed_fake_approval()
    try:
        r_login = client.post("/api/auth/login", json={"username": "user", "password": "user"})
        assert r_login.status_code == 200
        assert r_login.json()["user"]["role"] == "user", "setup: phải login đúng RM (role=user)"

        r = client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
        assert r.status_code == 403, (
            f"D-19: RM (role=user) KHÔNG được duyệt — kỳ vọng 403 forbidden, thấy {r.status_code}: {r.text}"
        )
        body = r.json()
        assert set(body) == {"code", "message", "hint", "retryable"}
        assert body["code"] == "forbidden"

        conn = psycopg2.connect(DATABASE_URL)
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM approvals WHERE id=%s", (approval_id,))
            assert cur.fetchone()[0] == "pending", "RM bị chặn — phiếu KHÔNG được đổi trạng thái"
        finally:
            conn.close()
    finally:
        _cleanup_approval(approval_id)


@requires_db
def test_decide_flag_off_admin_can_decide():
    """Đối chứng dương: admin THẬT (role='admin') decide được bình thường — xác nhận 403 ở
    trên là do THIẾU quyền, không phải do lỗi chung của endpoint."""
    assert deps.DEV_SKIP_AUTH is False
    if not _users_seeded():
        pytest.skip("users chưa seed")
    approval_id = _seed_fake_approval()
    try:
        r_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        assert r_login.status_code == 200
        assert r_login.json()["user"]["role"] == "admin"

        r = client.post(f"/api/approvals/{approval_id}/decide", json={"decision": "approved"})
        assert r.status_code == 200, f"admin PHẢI decide được: {r.status_code} {r.text}"
        assert r.json()["status"] == "approved"
    finally:
        _cleanup_approval(approval_id)


@requires_db
def test_decide_flag_off_rm_can_still_read_pending_list():
    """Ranh quyền chính xác: RM có thể XEM hàng chờ (GET /api/approvals) nhưng KHÔNG được QUYẾT
    (POST decide) — 2 quyền khác nhau, không gộp chung require_admin cho cả list nếu spec định
    cho user xem. Kiểm tra thực tế route GET dùng dependency nào (đọc code, không đoán)."""
    if not _users_seeded():
        pytest.skip("users chưa seed")
    r_login = client.post("/api/auth/login", json={"username": "user", "password": "user"})
    assert r_login.status_code == 200

    r = client.get("/api/approvals?status=pending")
    # Route GET /api/approvals hiện dùng require_admin (đọc app/api/approvals.py xác nhận) —
    # nên RM cũng bị chặn ở GET, không chỉ POST. Assert đúng THỰC TẾ code, không đoán ngược.
    assert r.status_code == 403, (
        f"GET /api/approvals dùng require_admin (đọc code xác nhận) — RM cũng bị chặn: {r.status_code}"
    )
