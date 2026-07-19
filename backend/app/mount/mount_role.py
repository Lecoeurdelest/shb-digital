"""mount_role(role) — điểm ghép DUY NHẤT giữa vỏ và LAB (lab-joint §2, adapt sang PG D-21).

Đọc `roles/<role>/functions.py` (REGISTRY + SCHEMAS + ANNOTATIONS) + `SKILL.md` → wrap
từng fn (acquire PGConnAdapter + envelope lỗi 4-field) → build MCP server in-process +
derive `allowed_tools`. Viết MỘT LẦN — swap tool/thêm tool KHÔNG đổi hàm này (N1).

S1 scope: KHÔNG có gated wrapper (disburse = S4), KHÔNG audit ContextVar (T1-1 skip —
xem task deviation), KHÔNG present tool (S3). Chỉ mount thô + envelope.
"""

from __future__ import annotations

import importlib
import inspect
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psycopg2
from claude_agent_sdk import create_sdk_mcp_server, tool
from claude_agent_sdk.types import McpSdkServerConfig

from app.mount.pg_adapter import PGConnAdapter, acquire, release
from app.mount.schema import schema_to_input

# repo root = 3 cấp lên từ backend/app/mount/ ; roles/ nằm tại repo root (D-08/D-26 layout)
REPO_ROOT = Path(__file__).resolve().parents[3]
ROLES_DIR = REPO_ROOT / "roles"

# repo root LÊN sys.path để `import roles.<role>.functions` chạy dù cwd nào (uvicorn từ backend/
# KHÔNG có repo root trên path — pytest có nhờ pyproject pythonpath, prod thì không). Idempotent.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _text(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def _sig_hint(schemas: dict[str, Any], name: str) -> str:
    params = schemas.get(name, {}).get("params", {})
    return ", ".join(
        f"{p}({m.get('type', 'str')}{', bắt buộc' if m.get('required') else ''})" for p, m in params.items()
    )


def run_labpack_fn(
    fn: Callable[..., dict[str, Any]],
    name: str,
    args: dict[str, Any],
    known: set[str],
    sig_hint: str,
    *,
    apply_read_scope: bool,
) -> dict[str, Any]:
    """SEAM CHUNG chạy 1 hàm labpack LAB (fn(conn,**kw)) qua PGConnAdapter — dùng bởi CẢ mount_role
    (role toolpack) LẪN common retrieval mount (T12-1). Vòng đời: chặn param-lạ → acquire → adapter
    (?→%s) → [read-scope nếu apply] → fn → commit → 4-field mọi lỗi (agent KHÔNG thấy traceback) →
    release. Bảng chưa seed → psycopg2.Error → db_error 4-field (KHÔNG 500). Trả payload dict THÔ
    (caller tự _text) — 1 nguồn logic, KHÔNG copy-paste (§6)."""
    unknown = set(args) - known
    if unknown:
        return {
            "code": "bad_param",
            "message": f"param không tồn tại: {sorted(unknown)}",
            "hint": f"Params hợp lệ: {sig_hint}. Sửa tên rồi gọi lại.",
            "retryable": True,
        }
    pg_conn = acquire()
    adapter = PGConnAdapter(pg_conn)
    try:
        # READ-SCOPE guard (FIX E — CHẶN S9): ca KHÁCH chỉ tra hồ sơ CỦA MÌNH. Choke point VỎ TRƯỚC
        # fn LAB (N1). CHỈ role toolpack (customer-profile tool). Common retrieval (wiki/notes) KHÔNG
        # qua read_scope (T12-1 scope OUT; notes_search owner-scope là việc T12-2 — ghi note báo cáo).
        if apply_read_scope:
            from app.mount.read_scope import read_scope_refusal
            from app.orch import registry

            refusal = read_scope_refusal(pg_conn, registry.CTX_CONV.get(), name, args)
            if refusal is not None:
                pg_conn.rollback()  # chưa gọi fn — rollback sạch (finally vẫn release)
                return refusal

        result = fn(adapter, **args)
        pg_conn.commit()  # read-only trong S1 nhưng commit sạch transaction (tránh idle-in-tx)
    except psycopg2.Error as e:
        pg_conn.rollback()
        result = {
            "code": "db_error",
            "message": str(e),
            "hint": "DB có thể chưa seed — kiểm GET /api/health. Thử lại 1 lần — vẫn lỗi thì báo main dừng nhánh này.",
            "retryable": True,
        }
    except (TypeError, ValueError) as e:
        pg_conn.rollback()
        result = {
            "code": "bad_type",
            "message": f"tham số sai/thiếu: {e}",
            "hint": f"Params hợp lệ: {sig_hint}.",
            "retryable": False,
        }
    except Exception as e:  # cửa cuối — agent KHÔNG BAO GIỜ thấy traceback
        pg_conn.rollback()
        result = {
            "code": "tool_error",
            "message": str(e)[:200],
            "hint": "Lỗi nội bộ tool — thử lại 1 lần; lặp thì báo main.",
            "retryable": True,
        }
    finally:
        adapter.close_cursors()  # dọn cursor mồ côi trước khi trả conn về pool
        release(pg_conn)
    return result


def _make_handler(
    fn: Callable[..., dict[str, Any]], name: str, schemas: dict[str, Any]
) -> Callable[[dict[str, Any]], Any]:
    known = set(inspect.signature(fn).parameters) - {"conn"}
    sig_hint = _sig_hint(schemas, name)

    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        return _text(run_labpack_fn(fn, name, args, known, sig_hint, apply_read_scope=True))

    return handler


def build_common_retrieval_tools(names: list[str]) -> list:
    """T12-1 (§7): build SDK tool cho retrieval mount vào COMMON server (wiki_*/notes_search).

    Ở ĐÂY (mount_role) vì module-level đã insert REPO_ROOT vào sys.path → `import roles.*` an toàn
    dù caller (common_tools) ở cwd=backend/. read_scope OFF (common không choke customer-profile —
    T12-1 scope; notes_search owner-scope = T12-2). Seam adapter dùng chung run_labpack_fn (§6)."""
    from claude_agent_sdk import tool
    from roles._retrieval import functions as R  # REPO_ROOT đã trên path (module-level insert trên)

    # D-68: notes_search (sổ tay RM = NỘI BỘ) → ca KHÁCH REFUSE HOÀN TOÀN (không owner-scope, refuse
    # thẳng — khớp luật disclosure). wiki_* (kiến thức quy trình, không PII) → mở mọi ca.
    _NOTES_INTERNAL = {"notes_search"}

    tools = []
    for name in names:
        fn = R.REGISTRY_RETRIEVAL[name]
        known = set(inspect.signature(fn).parameters) - {"conn"}
        sig_hint = _sig_hint(R.SCHEMAS_RETRIEVAL, name)
        spec = R.SCHEMAS_RETRIEVAL[name]
        internal = name in _NOTES_INTERNAL

        async def _handler(args: dict[str, Any], _fn=fn, _name=name, _known=known, _hint=sig_hint, _internal=internal):
            if _internal and _is_customer_conv():
                return _text(
                    {
                        "code": "internal_only",
                        "message": "Sổ tay tương tác là dữ liệu nội bộ ngân hàng.",
                        "hint": "Công cụ này chỉ dùng trong phiên nghiệp vụ nội bộ, không phục vụ tra cứu của khách.",
                        "retryable": False,
                    }
                )
            return _text(run_labpack_fn(_fn, _name, args, _known, _hint, apply_read_scope=False))

        tools.append(tool(name=name, description=spec["mô tả"], input_schema=schema_to_input(spec["params"]))(_handler))
    return tools


def _is_customer_conv() -> bool:
    """D-68: ca hiện tại (CTX_CONV) do KHÁCH (users.role='customer') tạo? — dùng cho notes_search
    refuse. Best-effort: không resolve/DB lỗi → False (mở, KHÔNG fail-closed vì đây là guard nội-bộ-
    vs-khách, không phải leak hồ sơ khách khác — read_scope role-path lo phần đó). conv_id từ CTX."""
    import psycopg2

    from app.db.config import DATABASE_URL
    from app.orch import registry

    conv_id = registry.CTX_CONV.get()
    if not conv_id:
        return False
    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT u.role FROM conversations c JOIN users u ON c.user_id=u.username WHERE c.id::text=%s",
                    (conv_id,),
                )
                row = cur.fetchone()
                return bool(row and row[0] == "customer")
        finally:
            conn.close()
    except psycopg2.Error:
        return False


def mount_role(role: str) -> tuple[str, McpSdkServerConfig, list[str]]:
    """Trả (skill_text, mcp_server, allowed_tools). `allowed_tools` đúng dạng
    `mcp__banking_<role>__<tool>` — derive từ REGISTRY, không gõ tay."""
    mod = importlib.import_module(f"roles.{role}.functions")
    skill_path = ROLES_DIR / role / "SKILL.md"
    skill = skill_path.read_text()
    # D-36: append PROVISIONAL present-skill (vỏ viết, file CẠNH — KHÔNG sửa SKILL.md gốc LAB).
    # LAB drop skill thật có present → xoá SKILL.present.md, mount tự bỏ append. N1 giữ (file tách).
    present_path = ROLES_DIR / role / "SKILL.present.md"
    if present_path.exists():
        skill = skill + "\n\n" + present_path.read_text()

    from app.orch.gated import GATED_WHITELIST, gated

    sdk_tools = []
    for name, fn in mod.REGISTRY.items():
        read_handler = _make_handler(fn, name, mod.SCHEMAS)
        # PHANH (T3-1, advisor #5): tool trong GATED_WHITELIST → gated handler (own conn/tx, thread
        # SAME conn vào inner). Read tool giữ handler per-call (mount §2). CHỈ gated whitelist thread-tx.
        handler = gated(name, read_handler) if name in GATED_WHITELIST else read_handler
        input_schema = schema_to_input(mod.SCHEMAS[name].get("params", {}))
        sdk_tools.append(tool(name=name, description=mod.SCHEMAS[name]["mô tả"], input_schema=input_schema)(handler))

    server = create_sdk_mcp_server(f"banking_{role}", version="1.0.0", tools=sdk_tools)
    allowed = [f"mcp__banking_{role}__{n}" for n in mod.REGISTRY]
    return skill, server, allowed
