from __future__ import annotations

from datetime import UTC

import psycopg2

from app.db.config import DATABASE_URL
from app.orch.verdict import AUTO_APPROVE_THRESHOLD, disburse_decision, latest_verdict

from .conftest import requires_db, requires_test_db

# ── helpers ──────────────────────────────────────────────────────────────────


def _now_iso() -> str:

    from datetime import datetime

    return datetime.now(UTC).isoformat(timespec="seconds")


def _seed_assessment(owner_id: str, lane: str) -> int:

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO assessments(owner_id, lane, loan_amount_vnd, created_at) VALUES(%s,%s,%s,%s) RETURNING id",
                (owner_id, lane, 300_000_000, _now_iso()),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def _rm_assessments(owner_id: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM assessments WHERE owner_id=%s", (owner_id,))
    conn.close()


def _owner_of(loan_id: str) -> str:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT owner_id FROM loans WHERE loan_id=%s", (loan_id,))
            return cur.fetchone()[0]
    finally:
        conn.close()


class _FakeConn:
    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *a):
            self._done = True

        def fetchone(self):
            return ("2000000000",)  # auto_approve_max_vnd = 2e9

    def cursor(self, *a, **k):
        return self._Cur()


def test_tier1_no_verdict_auto():

    d, reason = disburse_decision(_FakeConn(), {"loan_id": "NOEXIST_LOAN_T73", "amount": 300_000_000})
    assert d == "auto"
    assert "threshold" in reason


def test_tier3_above_max_always_human():

    d, reason = disburse_decision(_FakeConn(), {"loan_id": "NOEXIST_LOAN_T73", "amount": 2_000_000_001})
    assert d == "human"
    assert reason is None


def test_tier2_no_verdict_human():

    d, _ = disburse_decision(_FakeConn(), {"loan_id": "NOEXIST_LOAN_T73", "amount": 700_000_000})
    assert d == "human"


def test_amount_missing_human():

    assert disburse_decision(_FakeConn(), {"loan_id": "X"})[0] == "human"
    assert disburse_decision(_FakeConn(), {"loan_id": "X", "amount": "abc"})[0] == "human"


def test_boundary_500tr_is_tier2():

    d, _ = disburse_decision(_FakeConn(), {"loan_id": "NOEXIST_LOAN_T73", "amount": AUTO_APPROVE_THRESHOLD})
    assert d == "human"


def test_boundary_2e9_is_tier2_not_tier3():

    d, _ = disburse_decision(_FakeConn(), {"loan_id": "NOEXIST_LOAN_T73", "amount": 2_000_000_000})
    assert d == "human"


def test_boundary_2e9_plus_1_is_tier3():

    d, r = disburse_decision(_FakeConn(), {"loan_id": "NOEXIST_LOAN_T73", "amount": 2_000_000_001})
    assert d == "human" and r is None


@requires_test_db
def test_tier2_green_verdict_auto_reason_id():

    owner = _owner_of("L007")
    aid = _seed_assessment(owner, "green")
    try:
        d, reason = disburse_decision(_FakeConn(), {"loan_id": "L007", "amount": 700_000_000})
        assert d == "auto"
        assert f"#{aid}" in reason and "GREEN" in reason
    finally:
        _rm_assessments(owner)


@requires_test_db
def test_tier2_green_but_above_max_human():

    owner = _owner_of("L007")
    _seed_assessment(owner, "green")
    try:
        d, _ = disburse_decision(_FakeConn(), {"loan_id": "L007", "amount": 3_000_000_000})
        assert d == "human"
    finally:
        _rm_assessments(owner)


@requires_test_db
def test_tier1_red_verdict_blocks_auto():

    owner = _owner_of("L006")
    _seed_assessment(owner, "red")
    try:
        d, _ = disburse_decision(_FakeConn(), {"loan_id": "L006", "amount": 300_000_000})
        assert d == "human"
    finally:
        _rm_assessments(owner)


@requires_test_db
def test_tier1_yellow_verdict_does_not_block_auto():

    owner = _owner_of("L006")
    _seed_assessment(owner, "yellow")
    try:
        d, reason = disburse_decision(_FakeConn(), {"loan_id": "L006", "amount": 300_000_000})
        assert d == "auto", "Expected invariant was not satisfied at source line 161."
        assert "threshold" in reason
    finally:
        _rm_assessments(owner)


@requires_test_db
def test_tier2_yellow_verdict_human():

    owner = _owner_of("L007")
    _seed_assessment(owner, "yellow")
    try:
        d, _ = disburse_decision(_FakeConn(), {"loan_id": "L007", "amount": 700_000_000})
        assert d == "human"
    finally:
        _rm_assessments(owner)


@requires_test_db
def test_latest_verdict_picks_newest():

    owner = _owner_of("L007")
    _seed_assessment(owner, "red")
    newest = _seed_assessment(owner, "green")
    try:
        v = latest_verdict("L007")
        assert v is not None and v["id"] == newest and v["lane"] == "green"
    finally:
        _rm_assessments(owner)


@requires_db
def test_latest_verdict_no_loan_none():

    assert latest_verdict("NOEXIST_LOAN_ZZZ") is None


def test_latest_verdict_db_error_returns_none(monkeypatch):

    import app.orch.verdict as v

    monkeypatch.setattr(v, "DATABASE_URL", "postgresql://bad:bad@localhost:1/nope")
    assert v.latest_verdict("L007") is None


def test_disburse_decision_db_error_tier1_still_auto(monkeypatch):

    import app.orch.verdict as v

    monkeypatch.setattr(v, "DATABASE_URL", "postgresql://bad:bad@localhost:1/nope")
    d, _ = v.disburse_decision(_FakeConn(), {"loan_id": "L006", "amount": 300_000_000})
    assert d == "auto"


# ── 4. Rider — reset_demo wipe conversation dirs ─────────────────────────────


@requires_test_db
def test_reset_demo_wipes_conversation_dirs():

    from app.orch.main_session import CONV_ROOT

    CONV_ROOT.mkdir(parents=True, exist_ok=True)
    d = CONV_ROOT / "t73-rider-fake"
    d.mkdir(exist_ok=True)
    (d / "neo.txt").write_text("x")
    from app.db.reset_demo import reset_demo

    r = reset_demo(DATABASE_URL)
    assert r["_conversation_dirs_wiped"] >= 1
    assert CONV_ROOT.exists()
    assert not d.exists()
