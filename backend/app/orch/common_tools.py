from __future__ import annotations

import ast
import json
import operator
from datetime import UTC, datetime
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

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
        raise ValueError("only numeric values are accepted")
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("invalid expression (pure arithmetic only)")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def safe_eval(expression: str) -> dict[str, Any]:

    try:
        tree = ast.parse(expression, mode="eval")
        value = _eval_node(tree.body)
        return {"value": value, "expression": expression, "asOf": _now()}
    except (ValueError, SyntaxError, TypeError, ZeroDivisionError) as e:
        return {
            "code": "bad_expression",
            "message": f"expression '{expression}' could not be evaluated: {e}",
            "hint": "Use a pure arithmetic expression (+ - * / ** % ()) with numbers only.",
            "retryable": True,
        }


def _text(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


@tool(
    name="calc",
    description="Evaluate an arithmetic expression (the agent must not calculate mentally). Example: "
    "'30000000/8088576'. Pure arithmetic only: + - * / ** % and parentheses.",
    input_schema={
        "type": "object",
        "properties": {"expression": {"type": "string", "description": "arithmetic expression"}},
        "required": ["expression"],
    },
)
async def calc_tool(args: dict[str, Any]) -> dict[str, Any]:
    return _text(safe_eval(args.get("expression", "")))


PRESENT_TYPES = ["case_file", "metric", "checklist", "options", "timeline", "document"]


@tool(
    name="present",
    description="Present one STRUCTURED card on the canvas (for deliverables such as assessment verdicts and credit "
    "memos). Call it only for a result worth presenting, not for every message. type must be one of the six display "
    "types. Every number on the card must include 'source', the tool name that returned it; never invent numbers. "
    "The system generates the id; never provide one.",
    input_schema={
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": PRESENT_TYPES, "description": "card type"},
            "title": {"type": "string", "description": "card title"},
            "items": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "card content for the selected type (for example metric: [{name,value,threshold,pass,source}])"
                ),
            },
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "names of the source tools or roles used, without sensitive business data",
            },
        },
        "required": ["type", "title", "items"],
    },
)
async def present_tool(args: dict[str, Any]) -> dict[str, Any]:

    from app.orch import registry, store
    from app.sse.emit import emit

    card_type = args.get("type")
    title = args.get("title")
    items = args.get("items")

    if card_type not in PRESENT_TYPES or not isinstance(title, str) or not isinstance(items, list):
        return _text(
            {
                "code": "bad_card",
                "message": f"card requires {{type, title, items}}; type must be one of {PRESENT_TYPES}",
                "hint": "Correct the shape and call present again.",
                "retryable": False,
            }
        )

    if card_type == "document":
        from app.orch.credit_memo import CreditMemoValidationError, is_credit_memo, validate_credit_memo

        if is_credit_memo(args):
            try:
                args = validate_credit_memo(args)
            except CreditMemoValidationError as exc:
                return _text(
                    {
                        "code": "invalid_credit_memo",
                        "message": str(exc),
                        "hint": "Provide all six sections, reason_codes, and proof, then call present again.",
                        "retryable": True,
                    }
                )

    conv_id = registry.CTX_CONV.get()
    task_id = registry.CTX_TASK.get() or None

    _VO_OWNED = {"id", "conv_id", "task_id", "ts"}
    card_data = {k: v for k, v in args.items() if k not in _VO_OWNED}  # title/items/sources/...
    try:
        card_row = await store.insert_card(conv_id, task_id, card_type, card_data)
    except Exception as e:  # noqa: BLE001
        return _text(
            {
                "code": "card_persist_error",
                "message": str(e)[:200],
                "hint": "Retry once, then report it to main if the error recurs.",
                "retryable": True,
            }
        )

    try:
        emit(conv_id, "card", {"card": card_row})
    except Exception:  # noqa: BLE001
        pass

    return _text(
        {
            "rendered": True,
            "hint": f"card {card_type} is on the canvas; continue working, then respond with text when finished.",
        }
    )


FORM_FIELDS = [
    {"name": "full_name", "label": "Full name", "type": "text", "required": True},
    {"name": "id_number", "label": "National ID number", "type": "text", "required": True},
    {"name": "address", "label": "Permanent address", "type": "text", "required": True},
    {"name": "occupation", "label": "Occupation", "type": "text", "required": True},
    {"name": "monthly_income", "label": "Monthly income (VND)", "type": "number", "required": True},
    {"name": "loan_purpose", "label": "Loan purpose", "type": "text", "required": True},
]
FORM_REQUIRED = [f["name"] for f in FORM_FIELDS if f["required"]]


@tool(
    name="present_form",
    description=(
        "Show the NEW customer application FORM on the canvas when told that the customer has no existing case. "
        "The server defines the fields (full name, national ID, address, occupation, income, and loan purpose); do "
        "not ask for each field in chat. After the customer completes the form, the system creates the case and "
        "resumes the session."
    ),
    input_schema={"type": "object", "properties": {}},
)
async def present_form_tool(args: dict[str, Any]) -> dict[str, Any]:

    from app import consent
    from app.orch import registry, store
    from app.sse.emit import emit

    conv_id = registry.CTX_CONV.get()
    task_id = registry.CTX_TASK.get() or None
    try:
        wording = consent.load_wording()
    except consent.ConsentWordingError:
        return _text(
            {
                "code": "consent_wording_unavailable",
                "message": "The pre-pilot consent wording is not ready.",
                "hint": "Ask an administrator to review the wording artifact before opening the form.",
                "retryable": False,
            }
        )
    card_data = {
        "type": "form",
        "title": "Loan application — customer information",
        "fields": FORM_FIELDS,
        "status": "pending",
        "consent": wording.snapshot(),
    }
    try:
        card_row = await store.insert_card(conv_id, task_id, "form", card_data)
    except Exception as e:  # noqa: BLE001
        return _text({"code": "card_persist_error", "message": str(e)[:200], "hint": "Retry once.", "retryable": True})
    try:
        emit(conv_id, "card", {"card": card_row})
    except Exception:  # noqa: BLE001
        pass
    return _text(
        {
            "rendered": True,
            "hint": (
                "The application form is on the canvas. End the turn; the system resumes after the customer submits it."
            ),
        }
    )


# T12-1 scope; notes_search owner scope is T12-2. Convert the LAB schema to input_schema through schema_to_input.
_COMMON_RETRIEVAL = ["wiki_lookup", "wiki_search", "wiki_related_docs", "notes_search"]


def _build_retrieval_tools() -> list:

    from app.mount.mount_role import build_common_retrieval_tools

    return build_common_retrieval_tools(_COMMON_RETRIEVAL)


COMMON_SERVER = create_sdk_mcp_server(
    name="common",
    version="1.0.0",
    tools=[calc_tool, present_tool, present_form_tool, *_build_retrieval_tools()],
)
COMMON_ALLOWED = [
    "mcp__common__calc",
    "mcp__common__present",
    "mcp__common__present_form",
    *(f"mcp__common__{n}" for n in _COMMON_RETRIEVAL),
]
