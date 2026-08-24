"""Independent T20-5 adversarial mismatch API gate owned by tester-1."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg2
from fastapi.testclient import TestClient

from app.auth.security import make_token
from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_test_db

client = TestClient(app)


def _headers(tenant_id: str, role: str = "admin") -> dict[str, str]:
    token = make_token(user_id=str(uuid4()), username="t20", role=role, tenant_id=tenant_id)
    return {"Authorization": f"Bearer {token}"}


def _assert_error(response, status: int, code: str | None = None) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"code", "message", "hint", "retryable"}
    if code is not None:
        assert body["code"] == code


def _seed_scope() -> dict[str, str]:
    marker = uuid4().hex
    scope = {
        "tenant_a": str(uuid4()),
        "tenant_b": str(uuid4()),
        "conv_a": str(uuid4()),
        "conv_b": str(uuid4()),
    }
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants(id,slug,name) VALUES(%s,%s,'T20 tester A'),(%s,%s,'T20 tester B')",
            (scope["tenant_a"], f"t20-a-{marker}", scope["tenant_b"], f"t20-b-{marker}"),
        )
        cur.execute(
            "INSERT INTO conversations(id,tenant_id,user_id,title,status,created_at) "
            "VALUES(%s,%s,'tester-a','T20 A','idle',now()),(%s,%s,'tester-b','T20 B','idle',now())",
            (scope["conv_a"], scope["tenant_a"], scope["conv_b"], scope["tenant_b"]),
        )
    conn.close()
    return scope


def _seed_review(
    scope: dict[str, str],
    *,
    lane: str,
    recommendation: str,
    decision: str,
    match: bool,
    decided_at: datetime,
) -> str:
    approval_id, marker = str(uuid4()), uuid4().hex
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO approvals(id,tenant_id,conv_id,action,payload,payload_hash,status,"
            "idempotency_key,decided_at) VALUES(%s,%s,%s,'disburse','{}',%s,%s,%s,%s)",
            (
                approval_id,
                scope["tenant_a"],
                scope["conv_a"],
                marker,
                decision,
                f"t20-tester1:{marker}",
                decided_at,
            ),
        )
        cur.execute(
            "INSERT INTO shadow_reviews(approval_id,tenant_id,conv_id,system_lane,"
            "system_recommendation,human_decision,human_reason,decided_at,match) "
            "VALUES(%s,%s,%s,%s,%s,%s,'tester-1 reason',%s,%s)",
            (
                approval_id,
                scope["tenant_a"],
                scope["conv_a"],
                lane,
                recommendation,
                decision,
                decided_at,
                match,
            ),
        )
    conn.close()
    return approval_id


def _cleanup(scope: dict[str, str]) -> None:
    tenants = (scope["tenant_a"], scope["tenant_b"])
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM shadow_reviews WHERE tenant_id IN (%s,%s)", tenants)
        cur.execute("DELETE FROM approvals WHERE tenant_id IN (%s,%s)", tenants)
        cur.execute("DELETE FROM conversations WHERE tenant_id IN (%s,%s)", tenants)
        cur.execute("DELETE FROM tenants WHERE id IN (%s,%s)", tenants)
    conn.close()


@requires_test_db
def test_tester1_exact_three_mismatch_filters_auth_and_tenant():
    scope = _seed_scope()
    base = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)
    try:
        _seed_review(
            scope,
            lane="green",
            recommendation="auto-eligible",
            decision="approved",
            match=True,
            decided_at=base,
        )
        _seed_review(
            scope,
            lane="red",
            recommendation="reject-recommended",
            decision="rejected",
            match=True,
            decided_at=base + timedelta(hours=1),
        )
        mismatch_id = _seed_review(
            scope,
            lane="green",
            recommendation="auto-eligible",
            decision="rejected",
            match=False,
            decided_at=base + timedelta(hours=2),
        )
        headers_a = _headers(scope["tenant_a"])
        aggregate = client.get("/api/stats/shadow-match", headers=headers_a)
        assert aggregate.status_code == 200
        assert {k: aggregate.json()[k] for k in ("total", "comparable", "matched", "rate")} == {
            "total": 3,
            "comparable": 3,
            "matched": 2,
            "rate": 2 / 3,
        }

        page = client.get("/api/stats/shadow-match/mismatches", headers=headers_a)
        assert page.status_code == 200
        assert page.json()["next_cursor"] is None
        assert len(page.json()["items"]) == 1
        item = page.json()["items"][0]
        assert item["approval_id"] == mismatch_id
        assert set(item) == {
            "approval_id",
            "conv_id",
            "system_lane",
            "system_recommendation",
            "human_decision",
            "human_reason",
            "decided_at",
        }

        boundary = (base + timedelta(hours=2)).isoformat()
        inclusive = client.get(
            "/api/stats/shadow-match/mismatches",
            params={"from": boundary},
            headers=headers_a,
        ).json()
        exclusive = client.get(
            "/api/stats/shadow-match/mismatches",
            params={"to": boundary},
            headers=headers_a,
        ).json()
        assert len(inclusive["items"]) == 1
        assert exclusive["items"] == []
        assert len(client.get("/api/stats/shadow-match/mismatches?lane=green", headers=headers_a).json()["items"]) == 1
        assert client.get("/api/stats/shadow-match/mismatches?lane=red", headers=headers_a).json()["items"] == []
        assert client.get("/api/stats/shadow-match/mismatches", headers=_headers(scope["tenant_b"])).json() == {
            "items": [],
            "next_cursor": None,
        }

        _assert_error(TestClient(app).get("/api/stats/shadow-match/mismatches"), 401, "unauthorized")
        for role in ("user", "customer"):
            _assert_error(
                client.get("/api/stats/shadow-match/mismatches", headers=_headers(scope["tenant_a"], role)),
                403,
                "forbidden",
            )
        invalid_queries = (
            "from=2026-08-24T08:00:00",
            "from=not-a-date",
            "from=2026-08-24T09:00:00Z&to=2026-08-24T09:00:00Z",
            "lane=blue",
            "limit=0",
            "limit=201",
            "limit=1.0",
            "cursor=tampered",
        )
        for query in invalid_queries:
            response = client.get(f"/api/stats/shadow-match/mismatches?{query}", headers=headers_a)
            _assert_error(response, 400)
    finally:
        _cleanup(scope)


@requires_test_db
def test_tester1_keyset_same_timestamp_no_gap_and_cursor_context_bound():
    scope = _seed_scope()
    newest = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    try:
        same_time_ids = [
            _seed_review(
                scope,
                lane="green",
                recommendation="auto-eligible",
                decision="rejected",
                match=False,
                decided_at=newest,
            )
            for _ in range(2)
        ]
        older_id = _seed_review(
            scope,
            lane="red",
            recommendation="reject-recommended",
            decision="approved",
            match=False,
            decided_at=newest - timedelta(seconds=1),
        )
        headers_a = _headers(scope["tenant_a"])
        cursor = None
        seen: list[str] = []
        while True:
            suffix = f"&cursor={cursor}" if cursor else ""
            response = client.get(f"/api/stats/shadow-match/mismatches?limit=1{suffix}", headers=headers_a)
            assert response.status_code == 200, response.text
            seen.extend(item["approval_id"] for item in response.json()["items"])
            cursor = response.json()["next_cursor"]
            if cursor is None:
                break
        assert seen == [*sorted(same_time_ids, key=UUID, reverse=True), older_id]
        assert len(seen) == len(set(seen)) == 3

        first = client.get("/api/stats/shadow-match/mismatches?limit=1", headers=headers_a).json()
        bound_cursor = first["next_cursor"]
        assert bound_cursor
        _assert_error(
            client.get(
                f"/api/stats/shadow-match/mismatches?limit=1&lane=green&cursor={bound_cursor}",
                headers=headers_a,
            ),
            400,
            "invalid_cursor",
        )
        _assert_error(
            client.get(
                f"/api/stats/shadow-match/mismatches?limit=1&cursor={bound_cursor}",
                headers=_headers(scope["tenant_b"]),
            ),
            400,
            "invalid_cursor",
        )
    finally:
        _cleanup(scope)
