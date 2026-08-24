"""S18 T18-2 — pending-time snapshot, atomic ledger và match-rate contract."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.db.config import DATABASE_URL
from app.main import app
from app.orch import store_approvals, store_shadow
from app.orch.gated import _gated_txn

from .conftest import requires_db, requires_test_db

client = TestClient(app)


def _admin_cookie():
    return client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).cookies


def _seed_case(action: str, lane: str | None) -> dict[str, str]:
    token = uuid4().hex[:12]
    case = {"action": action, "conv": f"s18-rv-{token}", "owner": f"ORV{token}"}
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        if action == "disburse":
            case["ref"] = f"LRV{token}"
            cur.execute(
                "INSERT INTO loans(loan_id,owner_id,status) VALUES(%s,%s,'active')",
                (case["ref"], case["owner"]),
            )
        else:
            case["ref"] = f"ARV{token}"
            cur.execute(
                "INSERT INTO applications(id,owner_id,status) VALUES(%s,%s,'pending')",
                (case["ref"], case["owner"]),
            )
        if lane is not None:
            cur.execute(
                "INSERT INTO assessments(owner_id,lane,loan_amount_vnd,created_at) VALUES(%s,%s,%s,%s)",
                (case["owner"], lane, 700_000_000, datetime.now(UTC).isoformat(timespec="microseconds")),
            )
    conn.close()
    return case


def _pending(case: dict[str, str]) -> str:
    if case["action"] == "disburse":
        args = {"loan_id": case["ref"], "amount": 700_000_000}
    else:
        args = {"application_id": case["ref"], "amount_vnd": 700_000_000}
    result = _gated_txn(case["action"], case["conv"], None, args, threshold_vnd=0)
    assert result.payload["code"] == "approval_required"
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id::text FROM approvals WHERE conv_id=%s", (case["conv"],))
            return cur.fetchone()[0]
    finally:
        conn.close()


def _review(approval_id: str) -> tuple:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT system_lane,system_recommendation,human_decision,human_reason,match "
                "FROM shadow_reviews WHERE approval_id=%s",
                (approval_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def _cleanup(case: dict[str, str]) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM shadow_reviews WHERE conv_id=%s", (case["conv"],))
        cur.execute("DELETE FROM cards WHERE conv_id=%s", (case["conv"],))
        cur.execute("DELETE FROM approvals WHERE conv_id=%s", (case["conv"],))
        cur.execute("DELETE FROM assessments WHERE owner_id=%s", (case["owner"],))
        if case["action"] == "disburse":
            cur.execute("DELETE FROM loans WHERE loan_id=%s", (case["ref"],))
        else:
            cur.execute("DELETE FROM applications WHERE id=%s", (case["ref"],))
    conn.close()


def _clear_reviews() -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    conn.cursor().execute("DELETE FROM shadow_reviews")
    conn.close()


@requires_test_db
@pytest.mark.asyncio
async def test_green_red_neutral_both_owner_paths_and_exact_stats():
    _clear_reviews()
    green = _seed_case("disburse", "green")
    red = _seed_case("ops_disburse", "red")
    neutral = _seed_case("disburse", None)
    cases = (green, red, neutral)
    try:
        green_id, red_id, neutral_id = (_pending(case) for case in cases)

        # Assessment/config đổi sau pending không được viết lại snapshot green ban đầu.
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO assessments(owner_id,lane,loan_amount_vnd,created_at) VALUES(%s,'red',%s,%s)",
                (
                    green["owner"],
                    700_000_000,
                    (datetime.now(UTC) + timedelta(seconds=10)).isoformat(timespec="microseconds"),
                ),
            )
        conn.close()

        assert await store_approvals.decide(green_id, "rejected", "admin", "green rejected")
        assert await store_approvals.decide(red_id, "rejected", "admin", "red rejected")
        assert await store_approvals.decide(neutral_id, "approved", "admin", None)

        assert _review(green_id) == ("green", "auto-eligible", "rejected", "green rejected", False)
        assert _review(red_id) == ("red", "reject-recommended", "rejected", "red rejected", True)
        assert _review(neutral_id) == (None, "human-review", "approved", None, None)

        response = client.get("/api/stats/shadow-match", cookies=_admin_cookie())
        assert response.status_code == 200
        body = response.json()
        assert {k: body[k] for k in ("total", "comparable", "matched", "rate")} == {
            "total": 3,
            "comparable": 2,
            "matched": 1,
            "rate": 0.5,
        }
        assert body["by_lane"] == [
            {"lane": "green", "total": 1, "comparable": 1, "matched": 0, "rate": 0.0},
            {"lane": "red", "total": 1, "comparable": 1, "matched": 1, "rate": 1.0},
            {"lane": None, "total": 1, "comparable": 0, "matched": 0, "rate": 0.0},
        ]
        assert len(body["by_day"]) == 1
        assert {k: body["by_day"][0][k] for k in ("total", "comparable", "matched", "rate")} == {
            "total": 3,
            "comparable": 2,
            "matched": 1,
            "rate": 0.5,
        }
    finally:
        for case in cases:
            _cleanup(case)


@requires_test_db
def test_shadow_stats_empty_exact_shape_and_auth():
    _clear_reviews()
    expected = {"total": 0, "comparable": 0, "matched": 0, "rate": 0.0, "by_lane": [], "by_day": []}
    assert client.get("/api/stats/shadow-match", cookies=_admin_cookie()).json() == expected
    assert TestClient(app).get("/api/stats/shadow-match").status_code == 401

    username = "srv_" + uuid4().hex[:8]
    registered = client.post("/api/auth/register", json={"username": username, "password": "pass1"})
    try:
        assert client.get("/api/stats/shadow-match", cookies=registered.cookies).status_code == 403
    finally:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM users WHERE username=%s", (username,))
        conn.close()


@requires_db
@pytest.mark.asyncio
async def test_decide_twice_creates_one_shadow_review():
    case = _seed_case("disburse", "red")
    try:
        approval_id = _pending(case)
        assert await store_approvals.decide(approval_id, "rejected", "admin", None)
        assert await store_approvals.decide(approval_id, "rejected", "admin2", None) is None
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM shadow_reviews WHERE approval_id=%s", (approval_id,))
            assert cur.fetchone()[0] == 1
        conn.close()
    finally:
        _cleanup(case)


@requires_db
@pytest.mark.asyncio
async def test_shadow_insert_failure_rolls_back_decision_and_card(monkeypatch):
    case = _seed_case("disburse", "green")
    try:
        approval_id = _pending(case)

        def fail_insert(cur, row):
            raise RuntimeError("forced shadow insert failure")

        monkeypatch.setattr(store_shadow, "insert_review", fail_insert)
        with pytest.raises(RuntimeError, match="forced shadow"):
            await store_approvals.decide(approval_id, "approved", "admin", None)

        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM approvals WHERE id=%s", (approval_id,))
            assert cur.fetchone()[0] == "pending"
            cur.execute(
                "SELECT data->>'status' FROM cards WHERE conv_id=%s AND data->>'approval_id'=%s",
                (case["conv"], approval_id),
            )
            assert cur.fetchone()[0] == "pending"
            cur.execute("SELECT count(*) FROM shadow_reviews WHERE approval_id=%s", (approval_id,))
            assert cur.fetchone()[0] == 0
        conn.close()
    finally:
        _cleanup(case)
