"""[BACKEND] HOTFIX F2 (credit income_override re-sync) + F3 (disburse re-mount) — bench-builder S17.

F3: T12-3 làm MẤT tool `disburse` (loans-based, demo-path) khỏi mount operations → MAIN brief chết.
F2: credit VỎ là bản LAB CŨ thiếu income_override_vnd → hoà-giải T12-4 chết.
"""

from __future__ import annotations

import inspect

from app.mount.pg_adapter import PGConnAdapter, acquire, release
from app.mount.schema import schema_to_input

from .conftest import requires_db

# ── F3: disburse re-mount ────────────────────────────────────────────────────


def test_f3_operations_mounts_disburse_gated():
    """F3: mount operations = 4 tool (3 ops + disburse). disburse ∈ GATED_WHITELIST → gated-wrap."""
    from app.mount.mount_role import mount_role
    from app.orch.gated import GATED_WHITELIST

    _, _, allowed = mount_role("operations")
    names = {a.rsplit("__", 1)[-1] for a in allowed}
    assert names == {"ops_app_get", "ops_plan", "ops_disburse", "disburse"}
    assert "disburse" in GATED_WHITELIST  # → mount_role áp gated() wrapper


def test_f3_disburse_registry_schema_present():
    """disburse có trong REGISTRY + SCHEMAS operations (mount thấy tên+schema)."""
    from roles.operations import functions as O

    assert "disburse" in O.REGISTRY and "disburse" in O.SCHEMAS
    p = O.SCHEMAS["disburse"]["params"]
    assert "loan_id" in p and "amount" in p  # schema loans-based (KHÁC ops_disburse application_id)


# ── F2: credit income_override_vnd ───────────────────────────────────────────


def test_f2_credit_assess_has_income_override_param():
    """F2: signature + SCHEMA đều có income_override_vnd (schema là điều kiện model biết param tồn tại)."""
    from roles.credit import functions as C

    assert "income_override_vnd" in inspect.signature(C.credit_assess).parameters  # signature
    isch = schema_to_input(C.SCHEMAS["credit_assess"]["params"])
    props = isch.get("properties", isch)
    assert "income_override_vnd" in props  # input_schema → model được báo param (advisor: chống F2-cosmetic)


@requires_db
def test_f2_income_override_shifts_income_and_dscr():
    """F2 BAR (advisor): override chảy END-TO-END — monthly_income = X + DSCR ĐỔI vs no-override.
    KHÔNG chỉ fn-accept: income thật đổi + verdict shift (chứng minh vòng lặp hoà-giải sống)."""
    from roles.credit import functions as C

    pg = acquire()
    ad = PGConnAdapter(pg)
    try:
        base = C.credit_assess(ad, owner_id="C001", loan_amount_vnd=500_000_000)["item"]
        over = C.credit_assess(ad, owner_id="C001", loan_amount_vnd=500_000_000, income_override_vnd=999_000_000)[
            "item"
        ]
        pg.commit()
        assert over["inputs"]["monthlyIncomeVnd"] == 999_000_000.0  # override áp
        assert "OVERRIDE" in over["inputs"]["incomeSource"]  # nguồn ghi rõ (Legal xác minh)
        assert base["inputs"]["monthlyIncomeVnd"] != 999_000_000.0  # base dùng lương kê khai
        assert over["metrics"]["dscr"] != base["metrics"]["dscr"]  # DSCR shift → override chảy tới verdict
    finally:
        ad.close_cursors()
        release(pg)


def test_f2_credit_section_byte_identical_lab():
    """D-58: đoạn credit.py (từ LAB) trong VỎ byte-identical (0 hunk logic) — re-sync đúng nghi thức.
    Skip khi LAB sibling không có (CI runner) — cùng tiền lệ test_products_ops_port skipif."""
    from pathlib import Path

    import pytest

    repo = Path(__file__).resolve().parents[2]
    if not (repo.parent / "shb-digital-experts").exists():
        pytest.skip("LAB sibling repo không có trên máy này (CI)")
    lab = (
        repo.parent / "shb-digital-experts" / "missions" / "shb-132" / "tools" / "functions" / "credit.py"
    ).read_text()
    vo = (repo / "roles" / "credit" / "functions.py").read_text().splitlines(keepends=True)
    # đoạn credit.py VỎ = từ 'def _annuity' tới trước header customers
    s = next(i for i, ln in enumerate(vo) if ln.startswith("def _annuity"))
    e = next(i for i, ln in enumerate(vo) if "customers.py (COPY" in ln)
    while e > 0 and not vo[e - 1].strip().startswith("# ═"):
        e -= 1
    vo_section = "".join(vo[s : e - 1]).rstrip()
    lab_section = "".join(lab.splitlines(keepends=True)[14:]).rstrip()  # LAB từ _annuity (idx 14) tới EOF
    assert vo_section == lab_section, "credit.py section KHÔNG byte-identical vs LAB (re-sync sai)"
