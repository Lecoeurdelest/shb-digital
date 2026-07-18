"""[BACKEND] Test T13-1 — GET /api/stats + GET /api/assessments (dashboard admin, read-only).

stats: shape · window filter (today vs 7d — seed 2 mốc, đếm đúng) · auto đếm riêng · delta kỳ-trước ·
DB rỗng zeros · window lạ 400 · authz 403. assessments: filter owner/cap/malformed-json/newest.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import psycopg2
import psycopg2.extras
from fastapi.testclient import TestClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db, requires_test_db

client = TestClient(app)


def _admin():
    return client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).cookies


def _mk_approval(conv_id: str, status: str, decided_by: str, decided_at: datetime, ph: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO approvals (conv_id, action, payload, payload_hash, status, decided_by, decided_at) "
            "VALUES (%s,'disburse','{}',%s,%s,%s,%s)",
            (conv_id, ph, status, decided_by, decided_at),
        )
    conn.close()


def _mk_assessment(owner_id: str, lane: str, created_at: str, criteria_json: str = "[]") -> int:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO assessments (owner_id, lane, loan_amount_vnd, criteria_json, created_at) "
                "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                (owner_id, lane, 100_000_000, criteria_json, created_at),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def _rm(conv_ids: tuple[str, ...] = (), owners: tuple[str, ...] = ()) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        for c in conv_ids:
            cur.execute("DELETE FROM approvals WHERE conv_id=%s", (c,))
        for o in owners:
            cur.execute("DELETE FROM assessments WHERE owner_id=%s", (o,))
    conn.close()


# ── stats shape + window + auto + delta (test-db riêng — seed rác approvals/assessments) ──


@requires_test_db
def test_stats_shape_and_window_filter():
    """Seed 2 approvals (today + yesterday) → today window đếm ĐÚNG 1; auto đếm riêng; delta chuẩn."""
    now = datetime.now(UTC)
    yst = now - timedelta(days=1)
    _mk_approval("st1", "approved", "admin", now, "sh1")
    _mk_approval("st2", "used", "auto-rule", now, "sh2")  # auto
    _mk_approval("st3", "rejected", "admin", yst, "sh3")  # HÔM QUA — không vào today
    try:
        r = client.get("/api/stats?window=today", cookies=_admin())
        assert r.status_code == 200
        b = r.json()
        # shape đủ 4 nhóm
        assert set(b) == {"window", "approvals", "assessments", "conversations", "delta"}
        assert set(b["approvals"]) == {"approved", "rejected", "pending", "auto"}
        # today: approved 2 (approved+used), rejected 0 (yesterday excluded), auto 1
        assert b["approvals"]["approved"] == 2
        assert b["approvals"]["rejected"] == 0  # rejected của HÔM QUA không vào today
        assert b["approvals"]["auto"] == 1  # auto-rule đếm riêng
        # delta: today 2 − yesterday 1 = +1
        assert b["delta"]["approvals_total"] == 1
    finally:
        _rm(conv_ids=("st1", "st2", "st3"))


@requires_test_db
def test_stats_7d_window_includes_yesterday():
    """window=7d → gồm cả hôm qua (khác today)."""
    now = datetime.now(UTC)
    yst = now - timedelta(days=1)
    _mk_approval("s7a", "approved", "admin", now, "s7h1")
    _mk_approval("s7b", "rejected", "admin", yst, "s7h2")
    try:
        b = client.get("/api/stats?window=7d", cookies=_admin()).json()
        assert b["window"] == "7d"
        assert b["approvals"]["approved"] >= 1 and b["approvals"]["rejected"] >= 1  # cả 2 mốc trong 7d
    finally:
        _rm(conv_ids=("s7a", "s7b"))


@requires_test_db
def test_stats_assessments_by_lane():
    """assessments đếm theo lane trong window."""
    iso = datetime.now(UTC).isoformat(timespec="seconds")
    _mk_assessment("STAT1", "green", iso)
    _mk_assessment("STAT1", "red", iso)
    try:
        b = client.get("/api/stats?window=today", cookies=_admin()).json()
        assert b["assessments"]["green"] >= 1
        assert b["assessments"]["red"] >= 1
    finally:
        _rm(owners=("STAT1",))


@requires_db
def test_stats_bad_window_400():
    r = client.get("/api/stats?window=lastyear", cookies=_admin())
    assert r.status_code == 400
    assert r.json()["code"] == "bad_window"


@requires_db
def test_stats_default_today():
    """Không truyền window → default today (không 400)."""
    r = client.get("/api/stats", cookies=_admin())
    assert r.status_code == 200
    assert r.json()["window"] == "today"


@requires_db
def test_stats_authz_403_customer():
    """customer → 403 (dashboard admin-only)."""
    import uuid

    u = "stc_" + uuid.uuid4().hex[:6]
    reg = client.post("/api/auth/register", json={"username": u, "password": "pass1"})
    try:
        r = client.get("/api/stats", cookies=reg.cookies)
        assert r.status_code == 403
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM users WHERE username=%s", (u,))
        conn.close()


@requires_db
def test_stats_no_500_shape_always():
    """Dù data thế nào → 200 + shape đủ (không 500). Số có thể ≥0."""
    b = client.get("/api/stats?window=today", cookies=_admin()).json()
    assert all(isinstance(b["approvals"][k], int) for k in ("approved", "rejected", "pending", "auto"))
    assert all(isinstance(b["assessments"][k], int) for k in ("green", "yellow", "red"))


# ── /api/assessments ─────────────────────────────────────────────────────────


@requires_test_db
def test_assessments_filter_owner_and_newest():
    """filter owner + newest-first (created_at DESC, id DESC)."""
    now = datetime.now(UTC)
    _mk_assessment("OWN1", "green", (now - timedelta(seconds=2)).isoformat(timespec="seconds"))
    newest = _mk_assessment("OWN1", "red", now.isoformat(timespec="seconds"))
    _mk_assessment("OWN2", "yellow", now.isoformat(timespec="seconds"))  # owner khác
    try:
        rows = client.get("/api/assessments?owner=OWN1", cookies=_admin()).json()
        assert all(r["owner_id"] == "OWN1" for r in rows)  # filter đúng
        assert rows[0]["id"] == newest  # newest first
    finally:
        _rm(owners=("OWN1", "OWN2"))


@requires_test_db
def test_assessments_malformed_json_still_returns():
    """criteria_json hỏng → criteria=[] nhưng row VẪN trả (panel không mất record)."""
    iso = datetime.now(UTC).isoformat(timespec="seconds")
    aid = _mk_assessment("BADJ", "green", iso, criteria_json="{not valid json")
    try:
        rows = client.get("/api/assessments?owner=BADJ", cookies=_admin()).json()
        assert len(rows) == 1
        assert rows[0]["id"] == aid
        assert rows[0]["criteria"] == []  # hỏng → [] không crash
    finally:
        _rm(owners=("BADJ",))


@requires_db
def test_assessments_cap_and_authz():
    """limit cap 100 (>100 → 400 4-field qua validation handler chung) · customer → 403."""
    # cap: limit 500 > 100 → 400 bad_request (validation handler map 422→400 4-field, như audit)
    r = client.get("/api/assessments?limit=500", cookies=_admin())
    assert r.status_code == 400
    assert r.json()["code"] == "bad_request"
    # authz
    import uuid

    u = "sta_" + uuid.uuid4().hex[:6]
    reg = client.post("/api/auth/register", json={"username": u, "password": "pass1"})
    try:
        assert client.get("/api/assessments", cookies=reg.cookies).status_code == 403
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM users WHERE username=%s", (u,))
        conn.close()
