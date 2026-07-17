"""Tool CHUNG mọi role (server `common`): calc (+ present stub S1). lab-joint §5.

calc — tầng-0: agent CẤM nhẩm. Biểu thức số học thuần (không eval code). present = S3 (canvas);
S1 mount stub trả 'ok' để skill nào lỡ gọi không nổ (rẻ). Namespace `common` (spec §5) —
allowed_tools khớp string tuyệt đối.
"""

from __future__ import annotations

import ast
import json
import operator
from datetime import UTC, datetime
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

# ── calc: eval biểu thức số học AN TOÀN (AST, không eval code) ───────────────
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("chỉ chấp nhận số")
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("biểu thức không hợp lệ (chỉ số học thuần)")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def safe_eval(expression: str) -> dict[str, Any]:
    """Eval biểu thức số học thuần. Trả {value, expression, asOf} hoặc error 4-field."""
    try:
        tree = ast.parse(expression, mode="eval")
        value = _eval_node(tree.body)
        return {"value": value, "expression": expression, "asOf": _now()}
    except (ValueError, SyntaxError, TypeError, ZeroDivisionError) as e:
        return {
            "code": "bad_expression",
            "message": f"biểu thức '{expression}' không tính được: {e}",
            "hint": "Dùng biểu thức số học thuần (+ - * / ** % ()), chỉ số.",
            "retryable": True,
        }


def _text(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


@tool(
    name="calc",
    description="Tính biểu thức số học (agent CẤM nhẩm mọi phép tính). Vd '30000000/8088576'. "
    "Chỉ số học thuần: + - * / ** % và ngoặc.",
    input_schema={
        "type": "object",
        "properties": {"expression": {"type": "string", "description": "biểu thức số học"}},
        "required": ["expression"],
    },
)
async def calc_tool(args: dict[str, Any]) -> dict[str, Any]:
    return _text(safe_eval(args.get("expression", "")))


@tool(
    name="present",
    description="[S1 STUB] Trình 1 card có cấu trúc ra canvas. S1 chưa render canvas — trả ok. "
    "Card thật (7 loại) ở sprint sau.",
    input_schema={
        "type": "object",
        "properties": {
            "type": {"type": "string", "description": "loại card"},
            "title": {"type": "string"},
            "items": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["type", "title"],
    },
)
async def present_tool(args: dict[str, Any]) -> dict[str, Any]:
    return _text({"ok": True, "isStub": True, "hint": "[STUB S1] card đã ghi nhận — canvas render ở sprint sau."})


COMMON_SERVER = create_sdk_mcp_server(name="common", version="1.0.0", tools=[calc_tool, present_tool])
COMMON_ALLOWED = ["mcp__common__calc", "mcp__common__present"]
