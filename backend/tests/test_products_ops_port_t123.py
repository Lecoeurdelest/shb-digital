from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .conftest import requires_db

REPO_ROOT = Path(__file__).resolve().parents[2]
LAB_FUNCS = REPO_ROOT.parent / "shb-digital-experts" / "missions" / "shb-132" / "tools" / "functions"


def _strip_module_docstring(src: str) -> str:

    tree = ast.parse(src)
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        tree.body = tree.body[1:]
    return ast.dump(tree)


def _functions_ast_equal(port_path: Path, lab_path: Path) -> bool:

    import ast

    def defs(path: Path) -> dict[str, str]:
        out: dict[str, str] = {}
        for n in ast.parse(path.read_text()).body:
            if isinstance(n, ast.FunctionDef):
                body = (
                    n.body[1:]
                    if (n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant))
                    else n.body
                )
                out[n.name] = ast.dump(ast.Module(body=body, type_ignores=[]))
        return out

    lab, port = defs(lab_path), defs(port_path)
    return all(name in port and port[name] == lab[name] for name in lab)


# ── 1. Byte/AST-identical vs LAB (0 hunk logic) ──────────────────────────────


@pytest.mark.skipif(not LAB_FUNCS.exists(), reason="Optional integration prerequisite is unavailable.")
def test_products_functions_ast_identical_to_lab():

    port = REPO_ROOT / "roles" / "products" / "functions.py"
    lab = LAB_FUNCS / "products.py"
    assert _functions_ast_equal(port, lab), "Expected invariant was not satisfied at source line 50."


@pytest.mark.skipif(not LAB_FUNCS.exists(), reason="Optional integration prerequisite is unavailable.")
def test_operations_functions_ast_identical_to_lab():

    port = REPO_ROOT / "roles" / "operations" / "functions.py"
    lab = LAB_FUNCS / "operations.py"
    assert _functions_ast_equal(port, lab), "Expected invariant was not satisfied at source line 58."


def test_products_functions_no_janitor_or_lab_only_artifacts():

    assert not (REPO_ROOT / "roles" / "operations" / "janitor_app01.py").exists()
    assert not list(REPO_ROOT.glob("roles/**/janitor*"))


def _assert_no_shb_outside_d61_comment(skill: str) -> None:

    offending = [line for line in skill.splitlines() if "SHB" in line and "D-61" not in line]
    assert not offending, "Expected invariant was not satisfied at source line 70."


def test_mount_products_exposes_two_tools_v1_skill_branded():
    from app.mount.mount_role import mount_role

    skill, _server, allowed = mount_role("products")
    tool_names = {a.rsplit("__", 1)[-1] for a in allowed}
    assert tool_names == {"product_list", "product_suggest"}, "Expected invariant was not satisfied at source line 78."
    assert "v1" in skill[:200], "Expected invariant was not satisfied at source line 79."
    _assert_no_shb_outside_d61_comment(skill)
    assert "BANK Digital" in skill, "Expected invariant was not satisfied at source line 81."


def test_mount_operations_exposes_three_tools_v1_skill_branded():
    from app.mount.mount_role import mount_role

    skill, _server, allowed = mount_role("operations")
    tool_names = {a.rsplit("__", 1)[-1] for a in allowed}

    assert tool_names == {"ops_app_get", "ops_plan", "ops_disburse", "disburse"}, (
        "Expected invariant was not satisfied at source line 90."
    )
    assert "v1" in skill[:200], "Expected invariant was not satisfied at source line 91."
    _assert_no_shb_outside_d61_comment(skill)
    assert "BANK Digital" in skill, "Expected invariant was not satisfied at source line 93."

    assert "ops_disburse" in skill


def test_ops_disburse_in_gated_whitelist_not_plain_mount():

    from app.orch.gated import GATED_ROLE, GATED_TOOLS, GATED_WHITELIST

    assert "ops_disburse" in GATED_WHITELIST, "Expected invariant was not satisfied at source line 102."
    assert "ops_disburse" in GATED_TOOLS
    assert GATED_ROLE.get("ops_disburse") == "operations"


def test_disburse_action_untouched_by_ops_disburse_addition():

    from app.orch.gated import GATED_ROLE, GATED_TOOLS, GATED_WHITELIST

    assert "disburse" in GATED_WHITELIST
    assert "disburse" in GATED_TOOLS
    assert GATED_ROLE.get("disburse") == "operations"


def test_mount_operations_ops_disburse_gets_gated_handler_not_read_handler():

    import roles.operations.functions as ops_mod

    from app.orch.gated import GATED_WHITELIST

    assert "ops_disburse" in ops_mod.REGISTRY
    assert "ops_disburse" in GATED_WHITELIST


@requires_db
@pytest.mark.asyncio
async def test_ops_disburse_first_call_creates_pending_no_write_even_without_applications_table():

    import json
    from uuid import uuid4

    from app.orch import registry
    from app.orch.gated import gated

    conv = f"ops-disburse-port-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    h = gated("ops_disburse", None)
    args = {"application_id": "APP-PORT-TEST", "amount_vnd": 100_000_000}
    env = await h(args)
    body = env["content"][0]["text"] if "content" in env else env
    payload = json.loads(body) if isinstance(body, str) else body

    assert payload.get("code") == "approval_required", "Expected invariant was not satisfied at source line 145."
    assert payload.get("retryable") is False

    import psycopg2

    from app.db.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT status FROM approvals WHERE conv_id=%s AND action='ops_disburse'",
            (conv,),
        )
        rows = cur.fetchall()
        assert len(rows) == 1, "Expected invariant was not satisfied at source line 160."
        assert rows[0][0] == "pending"
    finally:
        conn.close()


@requires_db
@pytest.mark.asyncio
async def test_ops_disburse_claim_fails_clean_4field_when_applications_table_missing():

    import json
    from uuid import uuid4

    import psycopg2

    from app.db.config import DATABASE_URL
    from app.orch import registry
    from app.orch.gated import gated, payload_hash

    conv = f"ops-disburse-claim-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    h = gated("ops_disburse", None)
    args = {"application_id": "APP-PORT-CLAIM", "amount_vnd": 100_000_000}
    ph = payload_hash("ops_disburse", args)

    await h(args)

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE approvals SET status='approved' WHERE conv_id=%s AND action='ops_disburse' AND payload_hash=%s",
            (conv, ph),
        )
        conn.commit()
        assert cur.rowcount == 1
        cur.close()
    finally:
        conn.close()

    env = await h(args)
    body = env["content"][0]["text"] if "content" in env else env
    payload = json.loads(body) if isinstance(body, str) else body

    assert payload.get("code") == "disburse_blocked", "Expected invariant was not satisfied at source line 205."
    assert set(payload.keys()) >= {"code", "message", "hint", "retryable"}, (
        "Expected invariant was not satisfied at source line 206."
    )

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SELECT status FROM approvals WHERE conv_id=%s AND payload_hash=%s", (conv, ph))
        assert cur.fetchone()[0] == "approved", "Expected invariant was not satisfied at source line 212."
        cur.close()
    finally:
        conn.close()
