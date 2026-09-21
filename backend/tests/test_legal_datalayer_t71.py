from __future__ import annotations

import psycopg2

from app.db.config import DATABASE_URL

from .conftest import requires_db, requires_test_db


def _q1(sql: str, args: tuple = ()) -> object:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def _rows(sql: str, args: tuple = ()) -> list[tuple]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        conn.close()


@requires_db
def test_three_legal_tables_exist():

    for t in ("police_records", "employment_records", "assessments"):
        assert _q1("SELECT to_regclass(%s)", (f"public.{t}",)) is not None, (
            "Expected invariant was not satisfied at source line 35."
        )


@requires_db
def test_assessments_id_serial_autoincrement():

    default = _q1(
        "SELECT column_default FROM information_schema.columns WHERE table_name='assessments' AND column_name='id'"
    )
    assert default is not None and "nextval" in str(default), "Expected invariant was not satisfied at source line 44."


@requires_db
def test_identity_columns_exist():

    cust_cols = {
        r[0]
        for r in _rows(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='customers' AND column_name IN ('id_number','address')"
        )
    }
    assert cust_cols == {"id_number", "address"}, "Expected invariant was not satisfied at source line 57."
    biz_cols = {
        r[0]
        for r in _rows(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='businesses' AND column_name IN ('tax_code','address')"
        )
    }
    assert biz_cols == {"tax_code", "address"}, "Expected invariant was not satisfied at source line 65."


@requires_db
def test_identity_columns_seeded():

    assert _q1("SELECT count(*) FROM customers WHERE id_number IS NOT NULL") >= 1
    assert _q1("SELECT count(*) FROM customers WHERE address IS NOT NULL") >= 1
    assert _q1("SELECT count(*) FROM businesses WHERE tax_code IS NOT NULL") >= 1


@requires_db
def test_c013_identity_mismatch_trap_intact():

    row = _rows(
        "SELECT c.full_name, p.full_name, c.id_number, p.id_number "
        "FROM customers c JOIN police_records p ON c.id=p.owner_id WHERE c.id='C013'"
    )
    assert row, "Expected invariant was not satisfied at source line 83."
    crm_name, police_name, crm_id, police_id = row[0]
    assert crm_name != police_name, "Expected invariant was not satisfied at source line 85."
    assert crm_id == police_id, "Expected invariant was not satisfied at source line 86."


@requires_db
def test_six_legal_assumption_keys_values():

    got = {k: v for k, v in _rows("SELECT key, value FROM assumptions")}
    expected = {
        "auto_approve_max_vnd": "2000000000",
        "income_mismatch_max_pct": "10",
        "blocked_record_types": "financial_fraud,money_laundering",
        "cic_block_min_group": "3",
        "criminal_record_expiry_years": "7",
        "lane_policy_version": "v1",
    }
    for k, exp in expected.items():
        assert k in got, "Expected invariant was not satisfied at source line 102."
        assert got[k] == exp, "Expected invariant was not satisfied at source line 103."


@requires_db
def test_other_pack_string_keys_not_seeded():

    keys = {k for (k,) in _rows("SELECT key FROM assumptions")}
    for unmounted in ("legal_docs_source", "products_source", "recommend_by", "disburse_requires"):
        assert unmounted not in keys, "Expected invariant was not satisfied at source line 111."


@requires_db
def test_police_distribution_has_clean_and_pathology():

    dist = {
        status: n
        for status, n in _rows("SELECT criminal_status, count(*) FROM police_records GROUP BY criminal_status")
    }
    assert dist.get("clean", 0) >= 1, "Expected invariant was not satisfied at source line 121."
    pathology = dist.get("criminal_record", 0) + dist.get("under_investigation", 0)
    assert pathology >= 1, "Expected invariant was not satisfied at source line 123."


@requires_db
def test_employment_has_income_mismatch_case():

    # gap = declared(customers.monthly_income) vs verified(employment.verified_income_vnd)
    mismatched = _q1(
        "SELECT count(*) FROM employment_records e JOIN customers c ON e.owner_id=c.id "
        "WHERE e.verified_income_vnd IS NOT NULL AND e.verified_income_vnd > 0 "
        "AND abs(c.monthly_income - e.verified_income_vnd)::float / e.verified_income_vnd > 0.10"
    )
    assert mismatched >= 1, "Expected invariant was not satisfied at source line 135."


@requires_test_db
def test_assessments_seeded_empty():

    assert _q1("SELECT count(*) FROM assessments") == 0
