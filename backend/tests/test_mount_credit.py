"""Integration test mount_role(credit) — envelope 4-field + ground-truth C001 qua mount.

Gate T1-1 Verification #2 (dscr==3.709) + #3 (bad_param). Handler async → asyncio_mode=auto.
"""

from __future__ import annotations

import json

from roles.credit.functions import REGISTRY, SCHEMAS

from app.mount.mount_role import _make_handler, mount_role

from .conftest import requires_db


def _payload(envelope: dict) -> dict:
    """Bóc dict nghiệp vụ khỏi MCP content envelope."""
    return json.loads(envelope["content"][0]["text"])


# ── mount_role structural (không cần DB) ────────────────────────────────────


def test_mount_role_returns_triple():
    skill, server, allowed = mount_role("credit")
    assert isinstance(skill, str) and skill.startswith("# SKILL")
    assert allowed == [
        "mcp__banking_credit__cust_search",
        "mcp__banking_credit__cust_get",
        "mcp__banking_credit__credit_assess",
        "mcp__banking_credit__credit_cic_get",
    ]
    assert server is not None


# ── Verification #3: bad_param — fn KHÔNG chạy ──────────────────────────────


async def test_bad_param_blocks_before_fn():
    h = _make_handler(REGISTRY["credit_assess"], "credit_assess", SCHEMAS)
    out = _payload(await h({"owner": "C001"}))  # 'owner' sai (đúng: owner_id)
    assert out["code"] == "bad_param"
    assert "owner" in out["message"]
    assert out["retryable"] is True
    # hint liệt kê params hợp lệ để agent tự sửa
    assert "owner_id" in out["hint"]


async def test_bad_param_lists_valid_params():
    h = _make_handler(REGISTRY["cust_search"], "cust_search", SCHEMAS)
    out = _payload(await h({"query": "An"}))  # 'query' sai (đúng: q)
    assert out["code"] == "bad_param"


# ── Verification #2: credit_assess(C001) qua mount handler → dscr==3.709 ─────


@requires_db
async def test_credit_assess_c001_dscr_via_mount():
    h = _make_handler(REGISTRY["credit_assess"], "credit_assess", SCHEMAS)
    out = _payload(await h({"owner_id": "C001"}))
    assert out["found"] is True
    assert out["item"]["metrics"]["dscr"] == 3.709
    assert out["item"]["metrics"]["monthlyPaymentTotalVnd"] == 8088576
    assert out["item"]["verdict"] == "info_only"  # loan_amount=0


@requires_db
async def test_credit_assess_direct_registry_c001():
    """Verification #2 form: REGISTRY['credit_assess'](PGConnAdapter(conn), owner_id='C001')."""
    import psycopg2

    from app.db.config import DATABASE_URL
    from app.mount.pg_adapter import PGConnAdapter

    conn = psycopg2.connect(DATABASE_URL)
    try:
        out = REGISTRY["credit_assess"](PGConnAdapter(conn), owner_id="C001")
        assert out["found"] is True
        assert out["item"]["metrics"]["dscr"] == 3.709
    finally:
        conn.close()


# ── bad_type: param sai kiểu → bad_type 4-field, không traceback ────────────


@requires_db
async def test_bad_type_envelope():
    h = _make_handler(REGISTRY["credit_assess"], "credit_assess", SCHEMAS)
    out = _payload(await h({"owner_id": "C001", "loan_amount_vnd": "abc"}))
    assert out["code"] == "bad_type"
    assert out["retryable"] is False


# ── envelope shape: mọi tool trả MCP content envelope ───────────────────────


@requires_db
async def test_all_credit_tools_return_envelope():
    for name in REGISTRY:
        h = _make_handler(REGISTRY[name], name, SCHEMAS)
        # gọi với 1 param hợp lệ tối thiểu để không dừng ở bad_param
        args = (
            {"owner_id": "C001"}
            if name in ("credit_assess", "credit_cic_get")
            else {"q": "An"}
            if name == "cust_search"
            else {"id": "C001"}
        )
        env = await h(args)
        assert "content" in env
        assert env["content"][0]["type"] == "text"
        payload = json.loads(env["content"][0]["text"])
        assert isinstance(payload, dict)
