"""schema_to_input — SCHEMAS params -> full JSON Schema (lab-joint §2, BẢN DUY NHẤT).
KHÔNG dùng shorthand {tên: kiểu} của SDK: dạng đó ép MỌI param thành required."""

from __future__ import annotations

from typing import Any

_JSON = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "enum": "string",
    "list[str]": "array",
}


def schema_to_input(params: dict[str, Any]) -> dict[str, Any]:
    """FULL JSON Schema — required/enum/default nằm TRONG schema."""
    props: dict[str, Any] = {}
    required: list[str] = []
    for pname, meta in params.items():
        t = meta.get("type", "str")
        p: dict[str, Any] = {"type": _JSON.get(t, "string")}
        if t == "list[str]":
            p["items"] = {"type": "string"}
            if meta.get("values"):
                p["items"]["enum"] = meta["values"]
        elif meta.get("values"):
            p["enum"] = meta["values"]
            if all(isinstance(v, bool) for v in meta["values"]):
                p["type"] = "boolean"
            elif all(isinstance(v, int) for v in meta["values"]):
                p["type"] = "integer"
            elif all(isinstance(v, (int, float)) for v in meta["values"]):
                p["type"] = "number"
            else:
                p["type"] = "string"
        if meta.get("default") is not None:
            p["default"] = meta["default"]
        if meta.get("max") is not None:
            p["maximum"] = meta["max"]
        desc = meta.get("desc", "")
        if meta.get("default") is not None:
            desc = f"{desc} (default {meta['default']})".strip()
        if not meta.get("required"):
            desc = f"{desc} — optional, bỏ trống được".strip(" —")
        if desc:
            p["description"] = desc
        props[pname] = p
        if meta.get("required"):
            required.append(pname)
    return {"type": "object", "properties": props, "required": required}
