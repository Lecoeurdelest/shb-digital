"""[TESTER — T3-4, cập nhật S8/T8-1] Gate S3 authz boundary — decide approval CHỈ admin (NGÂN
HÀNG). Lịch sử semantics: D-19 (admin-only) → D-54 (mọi user) → D-56 (ĐẢO LẠI admin-only, 2
PERSONA: app = cửa khách, duyệt = việc ngân hàng). File này khớp D-56 HIỆN HÀNH. DEV_SKIP_AUTH
OFF (default, an toàn) — RM (role='user', tài khoản NGÂN HÀNG nhưng KHÔNG phải admin) KHÔNG duyệt
được. Chạy MẶC ĐỊNH (không cần RUN_LIVE_SDK, không cần seed data phức tạp — chỉ cần seed users +
1 approval row giả lập để test authz thuần, tách khỏi luồng resume thật ở
test_gate_s3_e2e_tester.py).

Viết ĐỘC LẬP với test backend (author≠checker) — backend test_approvals.py cover unit decide
logic; đây cover ranh QUYỀN cụ thể theo D-56 mà brief #14 yêu cầu tường minh."""

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
def test_decide_flag_off_rm_user_denied_d56():
    """[SỬA theo D-56, 18/7 — tester, ĐẢO LẠI D-54] D-56 đảo D-54: 2 PERSONA — app là cửa KHÁCH,
    duyệt là việc NGÂN HÀNG. Đọc app/api/approvals.py dòng 21/36/46 xác nhận POST decide (và GET
    list) đã quay lại `require_admin` (không phải suy đoán/tin lời khai backend) — "Duyệt phiếu
    = việc NGÂN HÀNG → require_admin" (comment code dòng 4).

    RM (role='user') ĐÃ login nhưng KHÔNG PHẢI admin → 403 forbidden 4-field. Tên test giữ hậu tố
    `_d56` để truy vết lịch sử đổi semantics 2 lần (D-19 admin-only → D-54 mọi user → D-56 quay
    lại admin-only), không phải bug sót lại."""
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
            f"D-56: RM (role=user) KHÔNG được duyệt — chỉ admin (require_admin) — "
            f"kỳ vọng 403, thấy {r.status_code}: {r.text}"
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
def test_decide_flag_off_rm_denied_pending_list_d56():
    """[SỬA theo D-56, 18/7 — tester, ĐẢO LẠI D-54] Đọc app/api/approvals.py dòng 21+36 xác nhận
    GET /api/approvals đã quay lại `require_admin` — nhất quán với POST decide (D-56: Tower là
    màn NGÂN HÀNG, khách không xem được hàng chờ duyệt của ngân hàng). RM (role='user') → 403
    forbidden 4-field."""
    if not _users_seeded():
        pytest.skip("users chưa seed")
    r_login = client.post("/api/auth/login", json={"username": "user", "password": "user"})
    assert r_login.status_code == 200

    r = client.get("/api/approvals?status=pending")
    assert r.status_code == 403, (
        f"D-56: GET /api/approvals dùng require_admin (đọc code xác nhận) — RM PHẢI bị chặn: {r.status_code} {r.text}"
    )
    body = r.json()
    assert set(body) == {"code", "message", "hint", "retryable"}
    assert body["code"] == "forbidden"
