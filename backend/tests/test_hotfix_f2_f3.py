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
    assert "disburse" in GATED_WHITELIST


def test_f3_disburse_registry_schema_present():

    from roles.operations import functions as O

    assert "disburse" in O.REGISTRY and "disburse" in O.SCHEMAS
    p = O.SCHEMAS["disburse"]["params"]
    assert "loan_id" in p and "amount" in p


# ── F2: credit income_override_vnd ───────────────────────────────────────────


def test_f2_credit_assess_has_income_override_param():

    from roles.credit import functions as C

    assert "income_override_vnd" in inspect.signature(C.credit_assess).parameters  # signature
    isch = schema_to_input(C.SCHEMAS["credit_assess"]["params"])
    props = isch.get("properties", isch)
    assert "income_override_vnd" in props


@requires_db
def test_f2_income_override_shifts_income_and_dscr():

    from roles.credit import functions as C

    pg = acquire()
    ad = PGConnAdapter(pg)
    try:
        base = C.credit_assess(ad, owner_id="C001", loan_amount_vnd=500_000_000)["item"]
        over = C.credit_assess(ad, owner_id="C001", loan_amount_vnd=500_000_000, income_override_vnd=999_000_000)[
            "item"
        ]
        pg.commit()
        assert over["inputs"]["monthlyIncomeVnd"] == 999_000_000.0
        assert "OVERRIDE" in over["inputs"]["incomeSource"]
        assert base["inputs"]["monthlyIncomeVnd"] != 999_000_000.0
        assert over["metrics"]["dscr"] != base["metrics"]["dscr"]
    finally:
        ad.close_cursors()
        release(pg)


def test_f2_credit_section_byte_identical_lab():

    from pathlib import Path

    import pytest

    repo = Path(__file__).resolve().parents[2]
    if not (repo.parent / "shb-digital-experts").exists():
        pytest.skip("Required test prerequisite is unavailable.")
    lab = (
        repo.parent / "shb-digital-experts" / "missions" / "shb-132" / "tools" / "functions" / "credit.py"
    ).read_text()
    vo = (repo / "roles" / "credit" / "functions.py").read_text().splitlines(keepends=True)

    s = next(i for i, ln in enumerate(vo) if ln.startswith("def _annuity"))
    e = next(i for i, ln in enumerate(vo) if "customers.py (COPY" in ln)
    while e > 0 and not vo[e - 1].strip().startswith("# ═"):
        e -= 1
    vo_section = "".join(vo[s : e - 1]).rstrip()
    lab_section = "".join(lab.splitlines(keepends=True)[14:]).rstrip()
    assert vo_section == lab_section, "Expected invariant was not satisfied at source line 88."
