"""S20 T20-1 — mismatch API filters, auth/tenant and stable keyset pagination."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg2
import psycopg2.extras
import pytest
from fastapi.testclient import TestClient

from app.auth.security import make_token
from app.config import AUTH_COOKIE
from app.db.config import DATABASE_URL
from app.main import app
from app.orch import store_shadow
from app.tenancy import DEFAULT_TENANT_ID

from .conftest import requires_db, requires_test_db

client = TestClient(app)


def test_cursor_codec_binds_tenant_filters_and_rejects_tamper_without_db():
    from_at = datetime(2026, 8, 24, tzinfo=UTC)
    to_at = from_at + timedelta(days=1)
    approval_id = str(uuid4())
    cursor = store_shadow._encode_cursor(
        tenant_id=DEFAULT_TENANT_ID,
        from_at=from_at,
        to_at=to_at,
        lane="green",
        decided_at=from_at + timedelta(hours=2),
        approval_id=approval_id,
    )
    assert store_shadow._decode_cursor(
        cursor,
        tenant_id=DEFAULT_TENANT_ID,
        from_at=from_at,
        to_at=to_at,
        lane="green",
    ) == (from_at + timedelta(hours=2), approval_id)
    for bad in (
        cursor[:-1] + ("A" if cursor[-1] != "A" else "B"),
        "🔥",
        ".",
        "a" * 4097,
    ):
        with pytest.raises(store_shadow.ShadowCursorError):
            store_shadow._decode_cursor(
                bad,
                tenant_id=DEFAULT_TENANT_ID,
                from_at=from_at,
                to_at=to_at,
                lane="green",
            )
    with pytest.raises(store_shadow.ShadowCursorError):
        store_shadow._decode_cursor(
            cursor,
            tenant_id=str(uuid4()),
            from_at=from_at,
            to_at=to_at,
            lane="green",
        )
    with pytest.raises(store_shadow.ShadowCursorError):
        store_shadow._decode_cursor(
            cursor,
            tenant_id=DEFAULT_TENANT_ID,
            from_at=from_at,
            to_at=to_at,
            lane="red",
        )


def _cookie(username: str) -> dict[str, str]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id::text,role,tenant_id::text FROM users WHERE username=%s", (username,))
            user_id, role, tenant_id = cur.fetchone()
    finally:
        conn.close()
    return {AUTH_COOKIE: make_token(user_id=user_id, username=username, role=role, tenant_id=tenant_id)}


def _make_user(role: str, tenant_id: str = DEFAULT_TENANT_ID) -> tuple[str, dict[str, str]]:
    username = f"s20_{role}_{uuid4().hex[:10]}"
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users(tenant_id,username,pass_hash,role) VALUES(%s,%s,'x',%s)",
                (tenant_id, username, role),
            )
    finally:
        conn.close()
    return username, _cookie(username)


def _make_tenant_admin() -> tuple[str, str, dict[str, str]]:
    tenant_id = str(uuid4())
    slug = f"s20-{uuid4().hex[:12]}"
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenants(id,slug,name) VALUES(%s,%s,'S20 tenant')", (tenant_id, slug))
    finally:
        conn.close()
    username, cookie = _make_user("admin", tenant_id)
    return tenant_id, username, cookie


def _seed_review(
    *,
    tenant_id: str,
    username: str,
    decided_at: datetime,
    lane: str,
    recommendation: str,
    human_decision: str,
    match: bool,
    reason: str | None = None,
) -> dict[str, str]:
    conv_id, approval_id = str(uuid4()), str(uuid4())
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations(id,tenant_id,user_id,title,status,created_at) "
                "VALUES(%s,%s,%s,'S20 mismatch','idle',%s)",
                (conv_id, tenant_id, username, decided_at),
            )
            cur.execute(
                "INSERT INTO approvals(id,tenant_id,conv_id,action,payload,payload_hash,status,decided_by,"
                "decided_at,reason,system_lane,system_recommendation,idempotency_key,created_at) "
                "VALUES(%s,%s,%s,'disburse',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    approval_id,
                    tenant_id,
                    conv_id,
                    psycopg2.extras.Json({}),
                    uuid4().hex,
                    human_decision,
                    username,
                    decided_at,
                    reason,
                    lane,
                    recommendation,
                    uuid4().hex,
                    decided_at,
                ),
            )
            cur.execute(
                "INSERT INTO shadow_reviews(tenant_id,approval_id,conv_id,system_lane,system_recommendation,"
                "human_decision,human_reason,decided_at,match) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    tenant_id,
                    approval_id,
                    conv_id,
                    lane,
                    recommendation,
                    human_decision,
                    reason,
                    decided_at,
                    match,
                ),
            )
    finally:
        conn.close()
    return {"conv_id": conv_id, "approval_id": approval_id}


def _cleanup(rows: list[dict[str, str]], *, users: tuple[str, ...] = (), tenant_id: str | None = None) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute("DELETE FROM shadow_reviews WHERE approval_id=%s", (row["approval_id"],))
                cur.execute("DELETE FROM approvals WHERE id=%s", (row["approval_id"],))
                cur.execute("DELETE FROM conversations WHERE id=%s", (row["conv_id"],))
            for username in users:
                cur.execute("DELETE FROM users WHERE username=%s", (username,))
            if tenant_id is not None:
                cur.execute("DELETE FROM tenants WHERE id=%s", (tenant_id,))
    finally:
        conn.close()


@requires_test_db
def test_three_comparable_aggregate_two_matches_and_one_mismatch_exact_shape():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    conn.cursor().execute("DELETE FROM shadow_reviews")
    conn.close()
    base = datetime(2026, 8, 24, 8, tzinfo=UTC)
    rows = [
        _seed_review(
            tenant_id=DEFAULT_TENANT_ID,
            username="admin",
            decided_at=base,
            lane="green",
            recommendation="auto-eligible",
            human_decision="approved",
            match=True,
        ),
        _seed_review(
            tenant_id=DEFAULT_TENANT_ID,
            username="admin",
            decided_at=base + timedelta(minutes=1),
            lane="red",
            recommendation="reject-recommended",
            human_decision="rejected",
            match=True,
        ),
        _seed_review(
            tenant_id=DEFAULT_TENANT_ID,
            username="admin",
            decided_at=base + timedelta(minutes=2),
            lane="green",
            recommendation="auto-eligible",
            human_decision="rejected",
            match=False,
            reason="calibration signal",
        ),
    ]
    try:
        aggregate = client.get("/api/stats/shadow-match", cookies=_cookie("admin"))
        assert aggregate.status_code == 200
        assert {key: aggregate.json()[key] for key in ("total", "comparable", "matched", "rate")} == {
            "total": 3,
            "comparable": 3,
            "matched": 2,
            "rate": 2 / 3,
        }
        response = client.get("/api/stats/shadow-match/mismatches", cookies=_cookie("admin"))
        assert response.status_code == 200
        assert response.json()["next_cursor"] is None
        assert response.json()["items"] == [
            {
                "approval_id": rows[2]["approval_id"],
                "conv_id": rows[2]["conv_id"],
                "system_lane": "green",
                "system_recommendation": "auto-eligible",
                "human_decision": "rejected",
                "human_reason": "calibration signal",
                "decided_at": (base + timedelta(minutes=2)).isoformat(),
            }
        ]
    finally:
        _cleanup(rows)


@requires_db
def test_filters_are_utc_half_open_lane_bounded_and_empty_page():
    base = datetime(2041, 1, 2, 3, tzinfo=UTC)
    rows = [
        _seed_review(
            tenant_id=DEFAULT_TENANT_ID,
            username="admin",
            decided_at=base + timedelta(hours=offset),
            lane=lane,
            recommendation="auto-eligible" if lane == "green" else "reject-recommended",
            human_decision="rejected" if lane == "green" else "approved",
            match=False,
        )
        for offset, lane in ((0, "green"), (1, "red"), (2, "green"))
    ]
    cookie = _cookie("admin")
    try:
        response = client.get(
            "/api/stats/shadow-match/mismatches",
            cookies=cookie,
            params={"from": base.isoformat(), "to": (base + timedelta(hours=2)).isoformat()},
        )
        assert [item["approval_id"] for item in response.json()["items"]] == [
            rows[1]["approval_id"],
            rows[0]["approval_id"],
        ]
        lane = client.get(
            "/api/stats/shadow-match/mismatches",
            cookies=cookie,
            params={"from": base.isoformat(), "to": (base + timedelta(hours=3)).isoformat(), "lane": "green"},
        )
        assert [item["approval_id"] for item in lane.json()["items"]] == [
            rows[2]["approval_id"],
            rows[0]["approval_id"],
        ]
        empty = client.get(
            "/api/stats/shadow-match/mismatches",
            cookies=cookie,
            params={"from": (base + timedelta(days=1)).isoformat()},
        )
        assert empty.json() == {"items": [], "next_cursor": None}
    finally:
        _cleanup(rows)


@requires_db
def test_same_timestamp_keyset_has_no_duplicate_or_gap_and_cursor_binds_filter_tenant():
    at = datetime(2042, 2, 2, 2, tzinfo=UTC)
    rows = [
        _seed_review(
            tenant_id=DEFAULT_TENANT_ID,
            username="admin",
            decided_at=at,
            lane="green",
            recommendation="auto-eligible",
            human_decision="rejected",
            match=False,
        )
        for _ in range(3)
    ]
    tenant_b, admin_b, cookie_b = _make_tenant_admin()
    cookie = _cookie("admin")
    seen: list[str] = []
    cursor = None
    try:
        while True:
            params = {"limit": "1"}
            if cursor is not None:
                params["cursor"] = cursor
            response = client.get("/api/stats/shadow-match/mismatches", cookies=cookie, params=params)
            assert response.status_code == 200
            seen.extend(item["approval_id"] for item in response.json()["items"])
            cursor = response.json()["next_cursor"]
            if cursor is None:
                break
            changed = client.get(
                "/api/stats/shadow-match/mismatches",
                cookies=cookie,
                params={"limit": "1", "cursor": cursor, "lane": "green"},
            )
            assert changed.status_code == 400 and changed.json()["code"] == "invalid_cursor"
            cross_tenant = client.get(
                "/api/stats/shadow-match/mismatches",
                cookies=cookie_b,
                params={"limit": "1", "cursor": cursor},
            )
            assert cross_tenant.status_code == 400 and cross_tenant.json()["code"] == "invalid_cursor"
        expected = sorted((row["approval_id"] for row in rows), key=UUID, reverse=True)
        assert seen == expected
        assert len(seen) == len(set(seen)) == 3
        assert client.get("/api/stats/shadow-match/mismatches", cookies=cookie_b).json() == {
            "items": [],
            "next_cursor": None,
        }
    finally:
        _cleanup(rows, users=(admin_b,), tenant_id=tenant_b)


@requires_db
@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({"from": "2026-08-24T00:00:00"}, "bad_shadow_filter"),
        ({"to": "not-a-time"}, "bad_shadow_filter"),
        (
            {"from": "2026-08-24T01:00:00Z", "to": "2026-08-24T01:00:00+00:00"},
            "bad_shadow_filter",
        ),
        ({"lane": "blue"}, "bad_shadow_filter"),
        ({"limit": "0"}, "bad_shadow_filter"),
        ({"limit": "201"}, "bad_shadow_filter"),
        ({"limit": "1.5"}, "bad_shadow_filter"),
        ({"cursor": "."}, "invalid_cursor"),
        ({"cursor": "🔥"}, "invalid_cursor"),
        ({"cursor": "a" * 4097}, "invalid_cursor"),
    ],
)
def test_invalid_filters_and_cursor_are_four_field_400(params, code):
    response = client.get("/api/stats/shadow-match/mismatches", cookies=_cookie("admin"), params=params)
    assert response.status_code == 400
    assert set(response.json()) == {"code", "message", "hint", "retryable"}
    assert response.json()["code"] == code


@requires_db
def test_mismatch_auth_roles_are_401_403_before_read():
    user_name, user_cookie = _make_user("user")
    customer_name, customer_cookie = _make_user("customer")
    try:
        anonymous = client.get("/api/stats/shadow-match/mismatches")
        assert anonymous.status_code == 401 and set(anonymous.json()) == {"code", "message", "hint", "retryable"}
        for cookie in (user_cookie, customer_cookie):
            response = client.get("/api/stats/shadow-match/mismatches", cookies=cookie)
            assert response.status_code == 403
            assert set(response.json()) == {"code", "message", "hint", "retryable"}
    finally:
        _cleanup([], users=(user_name, customer_name))
