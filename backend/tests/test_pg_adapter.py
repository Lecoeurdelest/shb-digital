"""Unit test PGConnAdapter (D-27) — 3-mode row + placeholder rewrite. Không đụng logic tool."""

from __future__ import annotations

import pytest

from app.mount.pg_adapter import Row, _rewrite_placeholders

from .conftest import requires_db

# ── Row wrapper: quack-như-sqlite3.Row (3 mode) ─────────────────────────────


def test_row_index_access():
    r = Row(("Nguyễn Văn An", 30000000), ["full_name", "monthly_income"])
    assert r[0] == "Nguyễn Văn An"
    assert r[1] == 30000000


def test_row_mapping_access():
    r = Row(("Nguyễn Văn An", 30000000), ["full_name", "monthly_income"])
    assert r["full_name"] == "Nguyễn Văn An"
    assert r["monthly_income"] == 30000000


def test_row_dict_cast():
    r = Row(("C001", 42), ["id", "age"])
    assert dict(r) == {"id": "C001", "age": 42}


def test_row_missing_key_raises_keyerror():
    r = Row(("x",), ["a"])
    with pytest.raises(KeyError):
        _ = r["nonexistent"]


def test_row_len():
    r = Row((1, 2, 3), ["a", "b", "c"])
    assert len(r) == 3


# ── placeholder rewrite: ?→%s, bỏ qua literal ───────────────────────────────


def test_rewrite_simple():
    assert _rewrite_placeholders("SELECT * FROM t WHERE id=?") == "SELECT * FROM t WHERE id=%s"


def test_rewrite_multiple():
    got = _rewrite_placeholders("WHERE a=? AND b=?")
    assert got == "WHERE a=%s AND b=%s"


def test_rewrite_no_placeholder_unchanged():
    sql = "SELECT COALESCE(SUM(monthly_payment),0) FROM loans"
    assert _rewrite_placeholders(sql) == sql


def test_rewrite_question_mark_in_literal_preserved():
    # `?` bên trong string literal KHÔNG bị đổi (quote-aware)
    sql = "SELECT * FROM t WHERE note='có phải?' AND id=?"
    got = _rewrite_placeholders(sql)
    assert "'có phải?'" in got  # literal giữ nguyên
    assert got.endswith("id=%s")  # bind mới đổi


# ── Adapter.execute end-to-end qua PG thật (integration) ────────────────────


@requires_db
def test_adapter_execute_fetchone(pg_conn):
    from app.mount.pg_adapter import PGConnAdapter

    a = PGConnAdapter(pg_conn)
    row = a.execute("SELECT id, monthly_income FROM customers WHERE id=?", ("C001",)).fetchone()
    assert row is not None
    assert row[0] == "C001"  # index
    assert row["monthly_income"] == 30000000  # mapping
    assert dict(row) == {"id": "C001", "monthly_income": 30000000}  # dict cast
    a.close_cursors()


@requires_db
def test_adapter_execute_fetchall_and_sum(pg_conn):
    from app.mount.pg_adapter import PGConnAdapter

    a = PGConnAdapter(pg_conn)
    # SUM không alias → credit.py đọc bằng index [0]
    row = a.execute(
        "SELECT COALESCE(SUM(monthly_payment),0) FROM loans WHERE owner_id=? AND status='active'",
        ("C001",),
    ).fetchone()
    assert row[0] == 8088576
    a.close_cursors()


@requires_db
def test_adapter_close_cursors_idempotent(pg_conn):
    from app.mount.pg_adapter import PGConnAdapter

    a = PGConnAdapter(pg_conn)
    a.execute("SELECT 1", ()).fetchone()
    a.close_cursors()
    a.close_cursors()  # gọi 2 lần không nổ
