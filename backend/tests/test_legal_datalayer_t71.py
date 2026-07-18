"""[BACKEND] Test T7-1 data-layer legal 3-trụ: 3 bảng tồn tại + 6 assumption key đúng value +
4 cột identity ADDITIVE + seed phân bố (≥1 clean, ≥1 tiền án, ≥1 income mismatch) + assessments
rỗng (sổ runtime). Đếm từ DB THẬT — không tin seed report, query lại.

D-58: seed nạp được 2 assumption key CHỮ (blocked_record_types, lane_policy_version) sau khi
credit._assumptions re-sync LAB graceful-skip. Trap C013 (CRM 'Lòng' vs Công an 'Long') = bằng
chứng 4 cột identity + police_records nạp đúng, đối chiếu nhân thân chạy được.
"""

from __future__ import annotations

import psycopg2

from app.db.config import DATABASE_URL

from .conftest import requires_db


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


# ── 3 bảng tồn tại ───────────────────────────────────────────────────────────


@requires_db
def test_three_legal_tables_exist():
    """police_records + employment_records + assessments có mặt (migration a1f7c2e93b04)."""
    for t in ("police_records", "employment_records", "assessments"):
        assert _q1("SELECT to_regclass(%s)", (f"public.{t}",)) is not None, f"bảng {t} thiếu"


@requires_db
def test_assessments_id_serial_autoincrement():
    """assessments.id serial (INSERT không id → sinh tự động, KHỚP sqlite cur.lastrowid cho T7-2 WRITE)."""
    default = _q1(
        "SELECT column_default FROM information_schema.columns "
        "WHERE table_name='assessments' AND column_name='id'"
    )
    assert default is not None and "nextval" in str(default), f"id không phải serial: {default}"


# ── 4 cột identity ADDITIVE (trụ ①công an đối chiếu nhân thân) ────────────────


@requires_db
def test_identity_columns_exist():
    """customers.id_number/address + businesses.tax_code/address — legal _owner_identity cần."""
    cust_cols = {
        r[0]
        for r in _rows(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='customers' AND column_name IN ('id_number','address')"
        )
    }
    assert cust_cols == {"id_number", "address"}, f"customers thiếu cột identity: {cust_cols}"
    biz_cols = {
        r[0]
        for r in _rows(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='businesses' AND column_name IN ('tax_code','address')"
        )
    }
    assert biz_cols == {"tax_code", "address"}, f"businesses thiếu cột identity: {biz_cols}"


@requires_db
def test_identity_columns_seeded():
    """id_number/address/tax_code nạp từ LAB (không rỗng) — nếu rỗng, đối chiếu công an vô nghĩa."""
    assert _q1("SELECT count(*) FROM customers WHERE id_number IS NOT NULL") >= 1
    assert _q1("SELECT count(*) FROM customers WHERE address IS NOT NULL") >= 1
    assert _q1("SELECT count(*) FROM businesses WHERE tax_code IS NOT NULL") >= 1


@requires_db
def test_c013_identity_mismatch_trap_intact():
    """Trap SEED-REPORT §7.1: CRM 'Đỗ Đức Lòng' ≠ Công an 'Đỗ Đức Long' (lệch full_name, cùng id_number).

    Bằng chứng end-to-end: 4 cột identity + police_records nạp đúng → đối chiếu nhân thân bắt được lệch.
    """
    row = _rows(
        "SELECT c.full_name, p.full_name, c.id_number, p.id_number "
        "FROM customers c JOIN police_records p ON c.id=p.owner_id WHERE c.id='C013'"
    )
    assert row, "C013 không có bản ghi police — trap chết"
    crm_name, police_name, crm_id, police_id = row[0]
    assert crm_name != police_name, f"trap tên phải LỆCH: CRM={crm_name} police={police_name}"
    assert crm_id == police_id, f"id_number phải KHỚP (chỉ lệch tên): {crm_id} vs {police_id}"


# ── 6 assumption key legal đúng value (đếm từ DB, không nhớ) ──────────────────


@requires_db
def test_six_legal_assumption_keys_values():
    """6 key phong bì đúng value chính xác — gồm 2 key CHỮ nạp được sau D-58."""
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
        assert k in got, f"thiếu assumption key '{k}'"
        assert got[k] == exp, f"'{k}' = {got[k]!r}, kỳ vọng {exp!r}"


@requires_db
def test_other_pack_string_keys_not_seeded():
    """Scope T7-1 gọn: 4 key chữ của pack chưa mount (products/ops) KHÔNG nạp (giữ filter phần đó)."""
    keys = {k for (k,) in _rows("SELECT key FROM assumptions")}
    for unmounted in ("legal_docs_source", "products_source", "recommend_by", "disburse_requires"):
        assert unmounted not in keys, f"'{unmounted}' (pack chưa mount) không nên seed ở T7-1"


# ── seed phân bố pathology (demo cần ca lệch — đếm từ DB thật) ────────────────


@requires_db
def test_police_distribution_has_clean_and_pathology():
    """≥1 ca clean + ≥1 ca tiền án/điều tra (pathology chủ đích — demo cần ca đỏ/vàng)."""
    dist = {
        status: n
        for status, n in _rows("SELECT criminal_status, count(*) FROM police_records GROUP BY criminal_status")
    }
    assert dist.get("clean", 0) >= 1, f"cần ≥1 ca clean: {dist}"
    pathology = dist.get("criminal_record", 0) + dist.get("under_investigation", 0)
    assert pathology >= 1, f"cần ≥1 ca tiền án/điều tra (demo): {dist}"


@requires_db
def test_employment_has_income_mismatch_case():
    """≥1 ca lương xác minh ≠ kê khai (SEED-REPORT §7.2 — trap income mismatch, demo cần)."""
    # gap = declared(customers.monthly_income) vs verified(employment.verified_income_vnd)
    mismatched = _q1(
        "SELECT count(*) FROM employment_records e JOIN customers c ON e.owner_id=c.id "
        "WHERE e.verified_income_vnd IS NOT NULL AND e.verified_income_vnd > 0 "
        "AND abs(c.monthly_income - e.verified_income_vnd)::float / e.verified_income_vnd > 0.10"
    )
    assert mismatched >= 1, "cần ≥1 ca income mismatch >10% (trap SEED-REPORT §7.2)"


@requires_db
def test_assessments_seeded_empty():
    """assessments = sổ GHI runtime → seed RỖNG (legal_classify_profile ghi lúc chạy, T7-2)."""
    assert _q1("SELECT count(*) FROM assessments") == 0
