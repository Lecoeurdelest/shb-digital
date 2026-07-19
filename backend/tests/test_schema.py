"""Unit test schema_to_input — full JSON Schema, không shorthand (lab-joint §2)."""

from __future__ import annotations

from roles.credit.functions import SCHEMAS

from app.mount.schema import schema_to_input


def test_required_only_required_in_list():
    params = {
        "owner_id": {"type": "str", "required": True, "desc": "id"},
        "loan_amount_vnd": {"type": "float", "default": 0, "desc": "vnd"},
    }
    out = schema_to_input(params)
    assert out["required"] == ["owner_id"]
    # optional KHÔNG bị ép required (bug shorthand)
    assert "loan_amount_vnd" not in out["required"]


def test_type_mapping():
    params = {
        "a": {"type": "str"},
        "b": {"type": "int"},
        "c": {"type": "float"},
        "d": {"type": "bool"},
    }
    out = schema_to_input(params)
    props = out["properties"]
    assert props["a"]["type"] == "string"
    assert props["b"]["type"] == "integer"
    assert props["c"]["type"] == "number"
    assert props["d"]["type"] == "boolean"


def test_enum_string_values():
    params = {"loan_type": {"type": "str", "values": ["consumer", "secured"], "default": None}}
    out = schema_to_input(params)
    p = out["properties"]["loan_type"]
    assert p["enum"] == ["consumer", "secured"]
    assert p["type"] == "string"


def test_default_in_schema_not_only_desc():
    params = {"limit": {"type": "int", "default": 5, "max": 20}}
    out = schema_to_input(params)
    p = out["properties"]["limit"]
    assert p["default"] == 5
    assert p["maximum"] == 20  # JSON Schema key


def test_credit_assess_schema_valid():
    # credit_assess: 1 required (owner_id) + 5 optional (HOTFIX F2: +income_override_vnd — vòng lặp
    # hoà-giải lương-lệch, re-sync LAB D-58) — chứng minh không dính shorthand
    out = schema_to_input(SCHEMAS["credit_assess"]["params"])
    assert out["required"] == ["owner_id"]
    assert set(out["properties"]) == {
        "owner_id",
        "loan_amount_vnd",
        "collateral_id",
        "loan_type",
        "term_months",
        "income_override_vnd",
    }
    assert out["properties"]["loan_type"]["enum"] == ["consumer", "secured"]


def test_cust_search_schema():
    out = schema_to_input(SCHEMAS["cust_search"]["params"])
    assert out["required"] == ["q"]
    assert out["properties"]["limit"]["maximum"] == 20
