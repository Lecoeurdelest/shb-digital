"""S18 T18-1 — ngưỡng tầng-1 cấu hình, shadow=0 và fail-closed không poison money tx."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import psycopg2
import pytest

from app.db.config import DATABASE_URL
from app.orch import registry, store_approvals
from app.orch.gated import gated
from app.orch.verdict import auto_approve_threshold

from .conftest import requires_db

_MISSING = object()


@pytest.fixture
def threshold_setting():
    """Đổi key có hoàn tác; không để config test rò sang demo/test kế."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT value FROM assumptions WHERE key='auto_approve_threshold_vnd'")
        old = cur.fetchone()
    conn.close()

    def put(value: object = _MISSING) -> None:
        c = psycopg2.connect(DATABASE_URL)
        c.autocommit = True
        with c.cursor() as cur:
            cur.execute("DELETE FROM assumptions WHERE key='auto_approve_threshold_vnd'")
            if value is not _MISSING:
                cur.execute(
                    "INSERT INTO assumptions(key,value) VALUES('auto_approve_threshold_vnd',%s)",
                    (str(value),),
                )
        c.close()

    yield put
    put(old[0] if old else _MISSING)


def _seed_case(*, lane: str | None = None) -> tuple[str, str, str]:
    token = uuid4().hex[:12]
    conv_id, loan_id, owner_id = f"s18-th-{token}", f"LTH{token}", f"OTH{token}"
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO loans(loan_id,owner_id,status) VALUES(%s,%s,'active')",
            (loan_id, owner_id),
        )
        if lane:
            cur.execute(
                "INSERT INTO assessments(owner_id,lane,loan_amount_vnd,created_at) VALUES(%s,%s,%s,%s)",
                (owner_id, lane, 700_000_000, datetime.now(UTC).isoformat(timespec="microseconds")),
            )
    conn.close()
    return conv_id, loan_id, owner_id


def _cleanup(conv_id: str, loan_id: str, owner_id: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM shadow_reviews WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM assessments WHERE owner_id=%s", (owner_id,))
        cur.execute("DELETE FROM loans WHERE loan_id=%s", (loan_id,))
    conn.close()


def _payload(result: dict) -> dict:
    return json.loads(result["content"][0]["text"])


async def _run(conv_id: str, loan_id: str, amount: int) -> dict:
    registry.CTX_CONV.set(conv_id)
    registry.CTX_TASK.set("")
    return _payload(await gated("disburse", None)({"loan_id": loan_id, "amount": amount}))


def _approval_snapshot(conv_id: str) -> tuple[str, str | None, str]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status,system_lane,system_recommendation FROM approvals WHERE conv_id=%s",
                (conv_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


@requires_db
@pytest.mark.asyncio
async def test_threshold_zero_routes_50m_no_assessment_to_human(threshold_setting):
    threshold_setting(0)
    case = _seed_case()
    try:
        out = await _run(case[0], case[1], 50_000_000)
        assert out["code"] == "approval_required"
        assert _approval_snapshot(case[0]) == ("pending", None, "auto-eligible")

        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id::text FROM approvals WHERE conv_id=%s", (case[0],))
                approval_id = cur.fetchone()[0]
        finally:
            conn.close()
        assert await store_approvals.decide(approval_id, "approved", "admin", "shadow approve")

        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT system_recommendation,human_decision,match FROM shadow_reviews WHERE approval_id=%s",
                    (approval_id,),
                )
                assert cur.fetchone() == ("auto-eligible", "approved", True)
        finally:
            conn.close()
    finally:
        _cleanup(*case)


@requires_db
@pytest.mark.asyncio
async def test_threshold_zero_blocks_green_tier2_but_snapshots_auto_eligible(threshold_setting):
    threshold_setting(0)
    case = _seed_case(lane="green")
    try:
        out = await _run(case[0], case[1], 700_000_000)
        assert out["code"] == "approval_required"
        assert _approval_snapshot(case[0]) == ("pending", "green", "auto-eligible")
    finally:
        _cleanup(*case)


@requires_db
@pytest.mark.asyncio
async def test_threshold_missing_preserves_50m_auto(threshold_setting):
    threshold_setting()
    case = _seed_case()
    try:
        out = await _run(case[0], case[1], 50_000_000)
        assert out["auto_approved"] is True
        assert out["disbursed"] is True
    finally:
        _cleanup(*case)


@requires_db
@pytest.mark.asyncio
async def test_positive_config_drives_route_and_counterfactual_snapshot(threshold_setting):
    threshold_setting(40_000_000)
    case = _seed_case()
    try:
        out = await _run(case[0], case[1], 50_000_000)
        assert out["code"] == "approval_required"
        assert _approval_snapshot(case[0]) == ("pending", None, "human-review")
    finally:
        _cleanup(*case)


@requires_db
@pytest.mark.asyncio
async def test_malformed_threshold_still_creates_pending_not_gated_error(threshold_setting):
    threshold_setting("not-a-number")
    case = _seed_case()
    try:
        assert auto_approve_threshold() == 0
        out = await _run(case[0], case[1], 50_000_000)
        assert out["code"] == "approval_required"
        assert _approval_snapshot(case[0])[0] == "pending"
    finally:
        _cleanup(*case)


@requires_db
@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_threshold_is_invalid_zero(threshold_setting, raw):
    threshold_setting(raw)
    assert auto_approve_threshold() == 0


@requires_db
@pytest.mark.asyncio
async def test_threshold_read_error_isolated_and_pending_tx_remains_usable(monkeypatch):
    import app.orch.verdict as verdict

    case = _seed_case()
    monkeypatch.setattr(verdict, "DATABASE_URL", "postgresql://bad:bad@127.0.0.1:1/nope?connect_timeout=1")
    try:
        out = await _run(case[0], case[1], 50_000_000)
        assert out["code"] == "approval_required"
        assert _approval_snapshot(case[0])[0] == "pending"
    finally:
        _cleanup(*case)
