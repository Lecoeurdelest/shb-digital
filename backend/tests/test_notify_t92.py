"""[BACKEND] Test T9-2 — mail Gmail no-op-sạch + hook decide/receipt + GET /api/notifications.

- send_email: thiếu env → no-op (log + False) · mock smtplib → gửi đúng to/subject · lỗi → False nuốt.
- notify_conv_owner: lookup email owner đúng (khách có email) · bank/không-email → skip.
- hook fail-im: send_email nổ → decide/disburse KHÔNG vỡ (200/chạy tiếp).
- GET /notifications: ca mình derive đúng (duyệt/từ chối/giải ngân) · rỗng → [] · scope ca người khác.

Fire-and-forget test qua HELPER trực tiếp (không qua endpoint — tránh race task chưa chạy khi assert).
"""

from __future__ import annotations

import uuid

import psycopg2
import psycopg2.extras

import app.notify.email as email_mod
from app.db.config import DATABASE_URL
from app.notify.email import send_email

from .conftest import requires_db

# ── send_email no-op / mock / fail ───────────────────────────────────────────


def test_send_email_noop_missing_env(monkeypatch):
    """Thiếu SMTP env → no-op: return False, KHÔNG raise, KHÔNG gọi smtplib."""
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_APP_PASSWORD", raising=False)
    called = {"smtp": False}

    def _boom(*a, **k):
        called["smtp"] = True
        raise AssertionError("smtplib KHÔNG được gọi khi thiếu env")

    monkeypatch.setattr(email_mod.smtplib, "SMTP_SSL", _boom)
    assert send_email("x@y.com", "sub", "body") is False
    assert called["smtp"] is False


def test_send_email_mock_sends_correct(monkeypatch):
    """Đủ env + mock smtplib → gửi đúng to/subject/from, return True."""
    monkeypatch.setenv("SMTP_USER", "sender@gmail.com")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "app16charspass")
    monkeypatch.setenv("NOTIFY_FROM_NAME", "SHB Test")
    sent = {}

    class _FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, u, p):
            sent["login"] = (u, p)

        def send_message(self, msg):
            sent["to"] = msg["To"]
            sent["subject"] = msg["Subject"]
            sent["from"] = msg["From"]

    monkeypatch.setattr(email_mod.smtplib, "SMTP_SSL", _FakeSMTP)
    assert send_email("cust@x.com", "Khoản vay đã duyệt", "body") is True
    assert sent["to"] == "cust@x.com"
    assert sent["subject"] == "Khoản vay đã duyệt"
    assert "SHB Test" in sent["from"]


def test_send_email_error_swallowed(monkeypatch):
    """Lỗi gửi (auth sai/mạng chết) → log.warning + return False (KHÔNG raise xuyên lên flow)."""
    monkeypatch.setenv("SMTP_USER", "sender@gmail.com")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "app16charspass")

    def _boom(*a, **k):
        raise OSError("mạng chết")

    monkeypatch.setattr(email_mod.smtplib, "SMTP_SSL", _boom)
    assert send_email("x@y.com", "s", "b") is False  # nuốt, không raise


# ── HTML brand template (T9-2 addendum) ──────────────────────────────────────


def test_render_email_html_3_kinds():
    """render_email_html 3 kind: brand BANK Digital (D-61) + amount VN + table-based + KHÔNG remote img."""
    from app.notify.email import render_email_html

    d = {
        "greeting_name": "Nguyễn Văn An",
        "loan_id": "L108",
        "amount_vnd": 594_000_000,
        "decided_by": "auto-rule",
        "decided_at": "2026-07-18T20:00",
        "ref": "abc",
        "assessment_id": 42,
        "app_url": "http://localhost:5173",
    }
    for kind in ("approved", "rejected", "disbursed"):
        h = render_email_html(kind, d)
        assert "BANK" in h and "<table" in h  # brand (D-61) + table-based
        assert "594.000.000 ₫" in h  # amount VN chấm-phân-cách
        assert "Hệ thống — tự động" in h  # auto-rule → text phân cấp
        assert "#42" in h  # assessment ref (kể ma trận)
        assert "src=" not in h  # KHÔNG ảnh remote/external asset


def test_render_email_html_escapes_injection():
    """greeting_name có HTML → escape (chống injection D-60, values khách nhập)."""
    from app.notify.email import render_email_html

    h = render_email_html("approved", {"greeting_name": "<script>x</script>", "amount_vnd": 1, "app_url": "x"})
    assert "<script>x</script>" not in h  # escaped
    assert "&lt;script&gt;" in h


def test_send_email_multipart_when_html(monkeypatch):
    """html_body có → multipart/alternative (plain fallback + html). Client text-only vẫn đọc plain."""
    monkeypatch.setenv("SMTP_USER", "s@gmail.com")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "xxxx")
    captured = {}

    class _F:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, *a):
            pass

        def send_message(self, msg):
            captured["msg"] = msg

    monkeypatch.setattr(email_mod.smtplib, "SMTP_SSL", _F)
    send_email("c@x.com", "sub", "plain body", "<b>html</b>")
    m = captured["msg"]
    assert m.is_multipart()
    types = {p.get_content_type() for p in m.walk()}
    assert "text/plain" in types and "text/html" in types


# ── notify_conv_owner helper (lookup email owner) ────────────────────────────


def _mk_customer_conv(email: str | None) -> tuple[str, str]:
    """Tạo user customer (email) + conv của họ. Trả (username, conv_id)."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    u = "n92_" + uuid.uuid4().hex[:8]
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, pass_hash, role, owner_id, email) VALUES (%s,'x','customer','C001',%s)",
            (u, email),
        )
        cur.execute(
            "INSERT INTO conversations (user_id, title, status, created_at) "
            "VALUES (%s,'t','idle',now()) RETURNING id::text",
            (u,),
        )
        conv = cur.fetchone()[0]
    conn.close()
    return u, conv


def _rm(username: str, conv: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv,))
        cur.execute("DELETE FROM users WHERE username=%s", (username,))
    conn.close()


@requires_db
def test_notify_conv_owner_looks_up_customer_email():
    """notify_conv_owner: ca khách CÓ email → _conv_owner_email trả đúng email."""
    from app.notify.hooks import _conv_owner_email

    u, conv = _mk_customer_conv("khach@gmail.com")
    try:
        assert _conv_owner_email(conv) == "khach@gmail.com"
    finally:
        _rm(u, conv)


@requires_db
def test_notify_conv_owner_skips_no_email():
    """Ca khách KHÔNG email → None (skip im, không gửi)."""
    from app.notify.hooks import _conv_owner_email

    u, conv = _mk_customer_conv(None)
    try:
        assert _conv_owner_email(conv) is None
    finally:
        _rm(u, conv)


@requires_db
def test_notify_conv_owner_skips_bank_conv():
    """Ca creator = ngân hàng (admin) → None (không phải khách, không notify)."""
    from app.notify.hooks import _conv_owner_email

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO conversations (user_id, title, status, created_at) "
            "VALUES ('admin','t','idle',now()) RETURNING id::text"
        )
        conv = cur.fetchone()[0]
    conn.close()
    try:
        assert _conv_owner_email(conv) is None  # admin không role customer
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM conversations WHERE id::text=%s", (conv,))
        conn.close()


# ── hook fail-im: send_email nổ → flow duyệt KHÔNG vỡ ─────────────────────────


@requires_db
def test_decide_hook_mail_fail_does_not_break_decide(monkeypatch):
    """HOOK a: send_email raise → POST decide VẪN 200 (mail best-effort, không chặn duyệt)."""
    from fastapi.testclient import TestClient

    from app.main import app

    # mail nổ mọi lúc
    monkeypatch.setattr(email_mod, "send_email", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    client = TestClient(app)
    admin = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    # seed 1 approval pending để decide
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    import json as _j

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO conversations (user_id, title, status, created_at) "
            "VALUES ('admin','t','idle',now()) RETURNING id::text"
        )
        conv = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO approvals (conv_id, action, payload, payload_hash, status) "
            "VALUES (%s,'disburse',%s,'hookfail','pending') RETURNING id::text",
            (conv, _j.dumps({"amount": 100, "loan_id": "L001"})),
        )
        aid = cur.fetchone()[0]
    conn.close()
    try:
        r = client.post(f"/api/approvals/{aid}/decide", json={"decision": "approved"}, cookies=admin.cookies)
        assert r.status_code == 200  # decide KHÔNG vỡ dù mail nổ
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv,))
            cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv,))
        conn.close()


# ── GET /api/notifications derive ────────────────────────────────────────────


@requires_db
def test_notifications_empty_returns_list():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    u = "n92e_" + uuid.uuid4().hex[:6]
    r = client.post("/api/auth/register", json={"username": u, "password": "pass1"})
    try:
        n = client.get("/api/notifications", cookies=r.cookies)
        assert n.status_code == 200
        assert n.json() == []  # 0 sự kiện → [] không 404
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM users WHERE username=%s", (u,))
        conn.close()


@requires_db
def test_notifications_derive_events_and_scope():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    import json as _j

    u = "n92d_" + uuid.uuid4().hex[:6]
    r = client.post("/api/auth/register", json={"username": u, "password": "pass1"})
    conv = client.post("/api/conversations", json={"title": "vay"}, cookies=r.cookies).json()["id"]
    u2 = "n92o_" + uuid.uuid4().hex[:6]
    r2 = client.post("/api/auth/register", json={"username": u2, "password": "pass1"})
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO approvals (conv_id,action,payload,payload_hash,status,decided_by,decided_at,used_at,receipt) "
            "VALUES (%s,'disburse',%s,'n1','used','admin',now(),now(),%s)",
            (conv, _j.dumps({"amount": 500000000}), _j.dumps({"disbursed": True, "amount": 500000000})),
        )
        cur.execute(
            "INSERT INTO approvals (conv_id,action,payload,payload_hash,status,decided_by,decided_at) "
            "VALUES (%s,'disburse',%s,'n2','rejected','admin',now())",
            (conv, _j.dumps({"amount": 999})),
        )
    conn.close()
    try:
        n = client.get("/api/notifications", cookies=r.cookies).json()
        types = {e["type"] for e in n}
        assert "disbursed" in types and "approval_decided" in types
        # scope: u2 thấy 0 sự kiện của conv (không phải ca mình)
        n2 = client.get("/api/notifications", cookies=r2.cookies).json()
        assert all(e["conv_id"] != conv for e in n2)
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv,))
            cur.execute("DELETE FROM conversations WHERE id::text=%s", (conv,))
            cur.execute("DELETE FROM users WHERE username IN (%s,%s)", (u, u2))
        conn.close()
