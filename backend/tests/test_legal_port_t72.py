from __future__ import annotations

import psycopg2
import pytest

from app.db.config import DATABASE_URL
from app.mount.pg_adapter import (
    PGConnAdapter,
    _is_allowed_write,
    _is_write,
    acquire,
    release,
)

from .conftest import requires_db, requires_test_db

_LAB_INSERT = (
    "INSERT INTO assessments(owner_id, loan_type, loan_amount_vnd, lane, criteria_json, basis, created_at) "
    "VALUES(?,?,?,?,?,?,?)"
)


def test_lab_insert_classified_allowed():

    assert _is_write(_LAB_INSERT) is True
    assert _is_allowed_write(_LAB_INSERT) is True


def test_selects_are_not_writes():

    for sel in (
        "SELECT id FROM assessments WHERE owner_id=?",
        "  SELECT * FROM police_records",
        "select value from assumptions",
        "SELECT owner_id, criminal_status FROM police_records WHERE owner_id=?",
    ):
        assert _is_write(sel) is False, "Expected invariant was not satisfied at source line 37."


def test_illegal_writes_flagged_write_not_allowed():

    for bad in (
        "UPDATE assessments SET lane=?",
        "DELETE FROM assessments WHERE id=?",
        "INSERT INTO customers(id) VALUES(?)",
        "insert into police_records(owner_id) values(?)",
        "DROP TABLE assessments",
        "ALTER TABLE assessments ADD COLUMN x int",
        "TRUNCATE assessments",
    ):
        assert _is_write(bad) is True, "Expected invariant was not satisfied at source line 51."
        assert _is_allowed_write(bad) is False, "Expected invariant was not satisfied at source line 52."


def test_allowed_write_variants_case_space():

    for ok in (
        "INSERT INTO assessments(a) VALUES(1)",
        "insert   into   assessments (a) values(1)",
        "INSERT INTO assessments VALUES(1)",
    ):
        assert _is_allowed_write(ok) is True, "Expected invariant was not satisfied at source line 62."


@requires_db
def test_adapter_raises_on_illegal_write_real_conn():

    conn = acquire()
    a = PGConnAdapter(conn)
    try:
        illegal = ("UPDATE assessments SET lane=%s", "DELETE FROM assessments", "INSERT INTO customers(id) VALUES(%s)")
        for bad in illegal:
            with pytest.raises(PermissionError):
                a.execute(bad, ("x",))

        cur = a.execute("SELECT count(*) FROM assessments")
        assert cur.fetchone()[0] >= 0
    finally:
        a.close_cursors()
        release(conn)


@requires_test_db
def test_adapter_insert_assessments_lastrowid():

    conn = acquire()
    a = PGConnAdapter(conn)
    try:
        cur = a.execute(
            "INSERT INTO assessments(owner_id, lane, created_at) VALUES(?,?,?)",
            ("TESTLRID", "green", "2026-07-18"),
        )
        assert cur.lastrowid is not None and cur.lastrowid > 0, (
            "Expected invariant was not satisfied at source line 93."
        )
        a.commit()

        got = a.execute("SELECT id, owner_id FROM assessments WHERE owner_id=?", ("TESTLRID",)).fetchone()
        assert got[0] == cur.lastrowid
    finally:
        a.close_cursors()
        release(conn)
        # cleanup
        c2 = psycopg2.connect(DATABASE_URL)
        c2.autocommit = True
        c2.cursor().execute("DELETE FROM assessments WHERE owner_id='TESTLRID'")
        c2.close()


def test_read_cursor_lastrowid_none():

    from app.mount.pg_adapter import _AdapterCursor

    class _FakeCur:
        description = None

    c = _AdapterCursor(_FakeCur())
    assert c.lastrowid is None


def _classify(owner_id: str, amount: float) -> dict:
    from roles.legal.functions import REGISTRY

    conn = acquire()
    a = PGConnAdapter(conn)
    try:
        return REGISTRY["legal_classify_profile"](a, owner_id=owner_id, loan_amount_vnd=amount)
    finally:
        a.close_cursors()
        release(conn)


def _assessment_row(assessment_id: int) -> tuple | None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, owner_id, lane FROM assessments WHERE id=%s", (assessment_id,))
            return cur.fetchone()
    finally:
        conn.close()


@requires_test_db
def test_classify_green_clean_customer():

    r = _classify("C002", 300_000_000)
    it = r["item"]
    assert it["lane"] == "green", "Expected invariant was not satisfied at source line 146."
    assert it["decision"] == "auto_approve_eligible"
    row = _assessment_row(it["assessmentId"])
    assert row is not None and row[1] == "C002" and row[2] == "green", (
        "Expected invariant was not satisfied at source line 149."
    )


@requires_test_db
def test_classify_c013_identity_mismatch_yellow():

    r = _classify("C013", 300_000_000)
    it = r["item"]
    assert it["lane"] == "yellow", "Expected invariant was not satisfied at source line 157."

    identity = next((c for c in it["criteria"] if c["key"] == "identity"), None)
    assert identity is not None and identity["level"] == "yellow"


@requires_test_db
def test_classify_criminal_blocked_red():

    r = _classify("C018", 300_000_000)
    it = r["item"]
    assert it["lane"] == "red", "Expected invariant was not satisfied at source line 168."
    assert it["decision"] == "reject_recommended"


@requires_test_db
def test_classify_business_asymmetry_yellow():

    r = _classify("B001", 300_000_000)
    it = r["item"]
    assert it["lane"] == "yellow", "Expected invariant was not satisfied at source line 177."
    emp = next((c for c in it["criteria"] if c["key"] == "employment"), None)
    assert emp is not None and emp["level"] == "yellow"


@requires_test_db
def test_classify_writes_incrementing_ids():

    r1 = _classify("C002", 100_000_000)
    r2 = _classify("C002", 200_000_000)
    id1, id2 = r1["item"]["assessmentId"], r2["item"]["assessmentId"]
    assert id2 > id1, "Expected invariant was not satisfied at source line 188."


@requires_db
def test_old_tool_check_docs_unchanged():

    from roles.legal.functions import REGISTRY

    conn = acquire()
    a = PGConnAdapter(conn)
    try:
        r = REGISTRY["legal_check_docs"](a, owner_id="C001", loan_type="consumer")
        assert r["found"] is True
        assert r["item"]["verdict"] in ("clear", "needs_docs", "blocked")
    finally:
        a.close_cursors()
        release(conn)


@requires_db
def test_old_tool_check_compliance_unchanged():

    from roles.legal.functions import REGISTRY

    conn = acquire()
    a = PGConnAdapter(conn)
    try:
        r = REGISTRY["legal_check_compliance"](a, owner_id="C001", purpose_code="business_expansion")
        assert r["found"] is True
        assert "verdict" in r["item"]
    finally:
        a.close_cursors()
        release(conn)


def test_mount_legal_exposes_five_tools():

    from app.mount.mount_role import mount_role

    skill, _server, allowed = mount_role("legal")
    tool_names = {a.rsplit("__", 1)[-1] for a in allowed}
    assert tool_names == {
        "legal_check_docs",
        "legal_check_compliance",
        "legal_check_police",
        "legal_verify_employment",
        "legal_classify_profile",
        "legal_related_exposure",
    }, "Expected invariant was not satisfied at source line 229."
    assert "v3" in skill[:120], "Expected invariant was not satisfied at source line 237."
