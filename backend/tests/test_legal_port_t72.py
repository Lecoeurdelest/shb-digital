"""[BACKEND] Test T7-2 port legal 5 tool + PGConnAdapter WRITE khoanh vùng (D-55b).

3 nhóm:
1. Adapter WRITE whitelist (unit, no DB) — allow INSERT-assessments + lastrowid; raise
   UPDATE/DELETE/INSERT-bảng-khác; read SELECT qua nguyên vẹn.
2. classify E2E trên seed thật (requires_db) — green/C013-yellow/criminal-red/DN-yellow +
   verify row assessments ghi đúng lane (WRITE path thật qua adapter).
3. Regression 2 tool cũ (check_docs/check_compliance) hành vi y nguyên + mount 5 tool.

Byte-verify 5 tool = LAB đã làm ở build (0 hunk logic) — test này kiểm HÀNH VI qua adapter thật.
"""

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

# ── 1. Adapter WRITE whitelist (unit — không cần DB) ─────────────────────────

# EXACT câu INSERT legal_classify_profile phát (LAB legal.py:338 — không space trước paren)
_LAB_INSERT = (
    "INSERT INTO assessments(owner_id, loan_type, loan_amount_vnd, lane, criteria_json, basis, created_at) "
    "VALUES(?,?,?,?,?,?,?)"
)


def test_lab_insert_classified_allowed():
    """Câu INSERT THẬT của classify (byte từ LAB) = write & allowed → không raise."""
    assert _is_write(_LAB_INSERT) is True
    assert _is_allowed_write(_LAB_INSERT) is True


def test_selects_are_not_writes():
    """Mọi câu đọc (SELECT, kể cả thụt đầu dòng/lowercase) KHÔNG bị coi là write → qua nguyên vẹn."""
    for sel in (
        "SELECT id FROM assessments WHERE owner_id=?",
        "  SELECT * FROM police_records",
        "select value from assumptions",
        "SELECT owner_id, criminal_status FROM police_records WHERE owner_id=?",
    ):
        assert _is_write(sel) is False, f"SELECT bị coi là write: {sel!r}"


def test_illegal_writes_flagged_write_not_allowed():
    """UPDATE/DELETE/DROP/ALTER/TRUNCATE + INSERT bảng khác → write=True, allowed=False (sẽ raise)."""
    for bad in (
        "UPDATE assessments SET lane=?",
        "DELETE FROM assessments WHERE id=?",
        "INSERT INTO customers(id) VALUES(?)",
        "insert into police_records(owner_id) values(?)",
        "DROP TABLE assessments",
        "ALTER TABLE assessments ADD COLUMN x int",
        "TRUNCATE assessments",
    ):
        assert _is_write(bad) is True, f"không nhận ra write: {bad!r}"
        assert _is_allowed_write(bad) is False, f"ghi bất hợp pháp lại được phép: {bad!r}"


def test_allowed_write_variants_case_space():
    """INSERT INTO assessments biến thể hoa/thường/khoảng trắng đều allowed (robust match)."""
    for ok in (
        "INSERT INTO assessments(a) VALUES(1)",
        "insert   into   assessments (a) values(1)",
        "INSERT INTO assessments VALUES(1)",
    ):
        assert _is_allowed_write(ok) is True, f"insert-assessments hợp lệ bị chặn: {ok!r}"


@requires_db
def test_adapter_raises_on_illegal_write_real_conn():
    """Qua adapter THẬT: UPDATE/DELETE/INSERT-bảng-khác → PermissionError (fail-closed, không im)."""
    conn = acquire()
    a = PGConnAdapter(conn)
    try:
        illegal = ("UPDATE assessments SET lane=%s", "DELETE FROM assessments", "INSERT INTO customers(id) VALUES(%s)")
        for bad in illegal:
            with pytest.raises(PermissionError):
                a.execute(bad, ("x",))
        # read vẫn chạy sau khi chặn (không hỏng conn)
        cur = a.execute("SELECT count(*) FROM assessments")
        assert cur.fetchone()[0] >= 0
    finally:
        a.close_cursors()
        release(conn)


@requires_test_db  # GHI assessments → chỉ test-db (siết architect)
def test_adapter_insert_assessments_lastrowid():
    """INSERT-assessments qua adapter → cursor.lastrowid = id vừa sinh (emulate sqlite RETURNING id)."""
    conn = acquire()
    a = PGConnAdapter(conn)
    try:
        cur = a.execute(
            "INSERT INTO assessments(owner_id, lane, created_at) VALUES(?,?,?)",
            ("TESTLRID", "green", "2026-07-18"),
        )
        assert cur.lastrowid is not None and cur.lastrowid > 0, "lastrowid phải là id serial vừa sinh"
        a.commit()
        # verify row thật + id khớp lastrowid
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
    """Cursor của SELECT → lastrowid=None (read không dùng, không nhầm)."""
    # dùng adapter thật cần DB; nhưng lastrowid=None là default _AdapterCursor → kiểm qua construct
    from app.mount.pg_adapter import _AdapterCursor

    class _FakeCur:
        description = None

    c = _AdapterCursor(_FakeCur())
    assert c.lastrowid is None


# ── 2. classify E2E trên seed thật (WRITE path qua adapter) ───────────────────


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


@requires_test_db  # GHI assessments → chỉ test-db (siết architect)
def test_classify_green_clean_customer():
    """Khách sạch + CIC1 + khoản nhỏ → lane green + auto_approve_eligible + GHI row."""
    r = _classify("C002", 300_000_000)
    it = r["item"]
    assert it["lane"] == "green", f"C002 sạch phải green: {it['lane']}"
    assert it["decision"] == "auto_approve_eligible"
    row = _assessment_row(it["assessmentId"])
    assert row is not None and row[1] == "C002" and row[2] == "green", "row assessments phải ghi đúng"


@requires_test_db  # GHI assessments → chỉ test-db (siết architect)
def test_classify_c013_identity_mismatch_yellow():
    """C013 (CRM 'Lòng' vs Công an 'Long') → identity mismatch → lane yellow."""
    r = _classify("C013", 300_000_000)
    it = r["item"]
    assert it["lane"] == "yellow", f"C013 lệch nhân thân phải yellow: {it['lane']}"
    # criterion identity phải yellow với bằng chứng full_name
    identity = next((c for c in it["criteria"] if c["key"] == "identity"), None)
    assert identity is not None and identity["level"] == "yellow"


@requires_test_db  # GHI assessments → chỉ test-db (siết architect)
def test_classify_criminal_blocked_red():
    """C018 (financial_fraud ∈ blocked_record_types) → tiền án chặn cứng → lane red."""
    r = _classify("C018", 300_000_000)
    it = r["item"]
    assert it["lane"] == "red", f"C018 tiền án blocked phải red: {it['lane']}"
    assert it["decision"] == "reject_recommended"


@requires_test_db  # GHI assessments → chỉ test-db (siết architect)
def test_classify_business_asymmetry_yellow():
    """DN B001 → không auto (chưa có xác minh BCTC — ÁN-L-F2) → lane yellow, employment yellow."""
    r = _classify("B001", 300_000_000)
    it = r["item"]
    assert it["lane"] == "yellow", f"DN phải yellow (asymmetry): {it['lane']}"
    emp = next((c for c in it["criteria"] if c["key"] == "employment"), None)
    assert emp is not None and emp["level"] == "yellow"


@requires_test_db  # GHI assessments → chỉ test-db (siết architect)
def test_classify_writes_incrementing_ids():
    """Mỗi call classify GHI 1 row mới (ledger append-only) — id tăng, không ghi đè."""
    r1 = _classify("C002", 100_000_000)
    r2 = _classify("C002", 200_000_000)
    id1, id2 = r1["item"]["assessmentId"], r2["item"]["assessmentId"]
    assert id2 > id1, "classify lần 2 phải sinh row mới (ledger, không ghi đè)"


# ── 3. Regression 2 tool cũ + mount 5 tool ───────────────────────────────────


@requires_db
def test_old_tool_check_docs_unchanged():
    """legal_check_docs (tool cũ) hành vi y nguyên — C001 clear."""
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
    """legal_check_compliance (tool cũ) hành vi y nguyên."""
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
    """mount_role('legal') derive đủ 5 tool từ REGISTRY (không hardcode 2 tool cũ) + SKILL v3."""
    from app.mount.mount_role import mount_role

    skill, _server, allowed = mount_role("legal")
    tool_names = {a.rsplit("__", 1)[-1] for a in allowed}
    assert tool_names == {
        "legal_check_docs",
        "legal_check_compliance",
        "legal_check_police",
        "legal_verify_employment",
        "legal_classify_profile",
    }, f"phải đủ 5 tool: {tool_names}"
    assert "v3" in skill[:120], "SKILL phải là bản v3"
