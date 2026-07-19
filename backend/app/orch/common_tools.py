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


# 6 loại HIỂN THỊ (canvas-present §1). "approval" NGOÀI enum — N2 rào CỨNG ở SDK schema:
# sub/main gọi present type=approval bị SDK reject TRƯỚC handler. Card approval CHỈ 1 cửa sinh:
# wrapper phanh (S4). Không có đường "agent tự chế card phanh giả".
PRESENT_TYPES = ["case_file", "metric", "checklist", "options", "timeline", "document"]


@tool(
    name="present",
    description="Trình 1 card CÓ CẤU TRÚC lên canvas (sản phẩm công việc: verdict thẩm định, tờ "
    "trình...). Gọi khi có kết quả đáng trình — KHÔNG cho mỗi câu nói. type ∈ 6 loại hiển thị. "
    "Mọi số trên card kèm 'source' = tên tool đã trả số đó (không bịa số). id do hệ thống sinh — "
    "KHÔNG tự bơm id.",
    input_schema={
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": PRESENT_TYPES, "description": "loại card"},
            "title": {"type": "string", "description": "tiêu đề card"},
            "items": {
                "type": "array",
                "items": {"type": "object"},
                "description": "nội dung card theo type (vd metric: [{name,value,threshold,pass,source}])",
            },
        },
        "required": ["type", "title", "items"],
    },
)
async def present_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Render a card on the canvas — validate shape, persist, emit SSE (shell-owned id).

    present THẬT (canvas-present §1): validate shape → persist cards → SSE card → rendered.
    id VỎ-inject (§15 — model không bơm id). conv/task từ ContextVar (set trước mỗi call)."""
    from app.orch import registry, store
    from app.sse.emit import emit

    card_type = args.get("type")
    title = args.get("title")
    items = args.get("items")
    # Shape tối thiểu (N3 — vỏ mù nội dung items). enum đã chặn ở SDK, nhưng validate lại defensive.
    if card_type not in PRESENT_TYPES or not isinstance(title, str) or not isinstance(items, list):
        return _text(
            {
                "code": "bad_card",
                "message": f"card cần {{type, title, items}}; type ∈ {PRESENT_TYPES}",
                "hint": "Sửa shape rồi gọi lại present.",
                "retryable": False,  # retry y nguyên vô ích — phải sửa shape
            }
        )

    conv_id = registry.CTX_CONV.get()
    task_id = registry.CTX_TASK.get() or None  # main gọi ngoài sub → None → card task_id null

    # Persist TRƯỚC (§4 — card không ghi DB là card ma). id VỎ sinh lúc insert (§15).
    # LỚP 1 phòng thủ (N5/§15): LỌC field VỎ-OWNED khỏi data — model KHÔNG được bơm id/conv_id/
    # task_id/ts (chỉ có thể BỊA). Card content (title/items/sources/recommended/total_days/flags...)
    # tự do (N3 — vỏ mù nội dung); nhưng id là của vỏ, agent bơm 'id' vào args sẽ bị bỏ.
    # RANH (S3+ builder đọc): CHỈ chặn field VỎ-QUẢN cụ thể, KHÔNG dùng additionalProperties:false ở
    # input_schema — vì nó sẽ chặn CẢ field nội dung top-level N3-hợp-lệ (sources/recommended/...) mà
    # skill bơm theo card type (canvas-present §3). 2 lớp lọc cứng {id,conv_id,task_id,ts} thoả CẢ
    # N5/§15 (id vỏ-inject) VÀ N3 (nội dung tự do) — additionalProperties:false phá N3.
    _VO_OWNED = {"id", "conv_id", "task_id", "ts"}
    card_data = {k: v for k, v in args.items() if k not in _VO_OWNED}  # title/items/sources/...
    try:
        card_row = await store.insert_card(conv_id, task_id, card_type, card_data)
    except Exception as e:  # noqa: BLE001 — DB lỗi → error 4-field, không stacktrace tới agent
        return _text(
            {
                "code": "card_persist_error",
                "message": str(e)[:200],
                "hint": "Thử lại 1 lần; lặp thì báo main.",
                "retryable": True,
            }
        )

    # SSE SAU persist (streaming-sse §5). Fire-and-forget: SSE lỗi KHÔNG fail present.
    try:
        emit(conv_id, "card", {"card": card_row})
    except Exception:  # noqa: BLE001
        pass

    return _text(
        {
            "rendered": True,
            "hint": f"card {card_type} đã lên canvas — tiếp tục việc, xong hết thì trả lời text.",
        }
    )


# ── present_form (T9-1 D-57) — form intake hồ sơ khách MỚI ───────────────────
# Fields ĐỊNH NGHĨA SERVER-SIDE (N5/§15 — model KHÔNG tự chế fields, chỉ GỌI tool). MAIN gọi khi
# ca customer owner_id=NULL (chưa hồ sơ). Card type 'form' → FE render panel phải WIDE (T9-3).
# 6 field theo dispatch T9-1 (KHÁC plan sprint_9 — dispatch thắng, ghi note báo architect).
FORM_FIELDS = [
    {"name": "full_name", "label": "Họ và tên", "type": "text", "required": True},
    {"name": "id_number", "label": "Số CMND/CCCD", "type": "text", "required": True},
    {"name": "address", "label": "Địa chỉ thường trú", "type": "text", "required": True},
    {"name": "occupation", "label": "Nghề nghiệp", "type": "text", "required": True},
    {"name": "monthly_income", "label": "Thu nhập hàng tháng (VND)", "type": "number", "required": True},
    {"name": "loan_purpose", "label": "Mục đích vay", "type": "text", "required": True},
]
FORM_REQUIRED = [f["name"] for f in FORM_FIELDS if f["required"]]


@tool(
    name="present_form",
    description=(
        "Hiện FORM thu thập hồ sơ khách MỚI (chưa có hồ sơ) lên canvas — dùng khi được báo khách "
        "CHƯA có hồ sơ. Fields do server định sẵn (họ tên, CMND, địa chỉ, nghề, thu nhập, mục đích "
        "vay) — KHÔNG tự hỏi từng câu trong chat. Khách điền form → hệ thống tạo hồ sơ + gọi lại bạn."
    ),
    input_schema={"type": "object", "properties": {}},  # không nhận field từ model (server-side)
)
async def present_form_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Present the customer intake form card (fields server-defined, model cannot alter them).

    present_form THẬT: persist card type 'form' (fields server-side + status='pending') → SSE.
    id/conv/task VỎ-inject (§15). Model KHÔNG bơm fields — chống model tự chế shape hồ sơ."""
    from app.orch import registry, store
    from app.sse.emit import emit

    conv_id = registry.CTX_CONV.get()
    task_id = registry.CTX_TASK.get() or None
    card_data = {
        "type": "form",
        "title": "Hồ sơ vay — thông tin khách hàng",
        "fields": FORM_FIELDS,
        "status": "pending",
    }
    try:
        card_row = await store.insert_card(conv_id, task_id, "form", card_data)
    except Exception as e:  # noqa: BLE001
        return _text(
            {"code": "card_persist_error", "message": str(e)[:200], "hint": "Thử lại 1 lần.", "retryable": True}
        )
    try:
        emit(conv_id, "card", {"card": card_row})
    except Exception:  # noqa: BLE001
        pass
    return _text(
        {
            "rendered": True,
            "hint": "Form hồ sơ đã lên canvas. KẾT THÚC LƯỢT — khách điền xong hệ thống tự gọi lại bạn.",
        }
    )


# ── T12-1: retrieval toolpack CHUNG (§7) — wiki_*/notes_search vào common server (mọi role) ──
# legal_related_exposure KHÔNG ở đây (mount vào toolpack legal — roles/legal REGISTRY). Các fn LAB
# byte-identical (roles/_retrieval/functions.py) chạy qua SEAM CHUNG run_labpack_fn (mount_role) —
# PGConnAdapter + 4-field mọi lỗi (bảng chưa seed → db_error, KHÔNG 500). read_scope OFF cho common
# (T12-1 scope; notes_search owner-scope = T12-2). schema LAB → input_schema qua schema_to_input.
_COMMON_RETRIEVAL = ["wiki_lookup", "wiki_search", "wiki_related_docs", "notes_search"]


def _build_retrieval_tools() -> list:
    """Wrap 4 fn retrieval (common) thành SDK tool — delegate `mount_role.build_common_retrieval_tools`
    (logic build NẰM Ở mount_role: module đó insert REPO_ROOT vào sys.path lúc load nên `import roles.*`
    chạy dù uvicorn cwd=backend/). Đặt ở đó, KHÔNG ở đây, để tránh phụ thuộc THỨ TỰ import mà ruff-isort
    sắp lại → ModuleNotFoundError 'roles' lúc boot. Seam adapter chung run_labpack_fn (§6, không dup)."""
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
