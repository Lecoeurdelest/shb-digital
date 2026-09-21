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
from mcp.types import ToolAnnotations

from app.mount.pg_adapter import PGConnAdapter, acquire, release
from app.mount.schema import schema_to_input
from app.prompting import get_prompt_service
from app.storage import connect_core
from app.tenancy import DEFAULT_TENANT_ID

REPO_ROOT = Path(__file__).resolve().parents[3]
ROLES_DIR = REPO_ROOT / "roles"


if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _text(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def _annotations(meta: dict[str, Any] | None) -> ToolAnnotations | None:

    return ToolAnnotations(**meta) if meta else None


def _sig_hint(schemas: dict[str, Any], name: str) -> str:
    params = schemas.get(name, {}).get("params", {})
    return ", ".join(
        f"{p}({m.get('type', 'str')}{', required' if m.get('required') else ''})" for p, m in params.items()
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

    unknown = set(args) - known
    if unknown:
        return {
            "code": "bad_param",
            "message": f"unknown parameter: {sorted(unknown)}",
            "hint": f"Valid parameters: {sig_hint}. Correct the name and call again.",
            "retryable": True,
        }
    pg_conn = acquire()
    adapter = PGConnAdapter(pg_conn)
    try:
        from app.orch import registry

        conv_id = registry.CTX_CONV.get()
        tenant_id = DEFAULT_TENANT_ID
        if conv_id:
            with pg_conn.cursor() as tenant_cur:
                tenant_cur.execute("SELECT tenant_id::text FROM conversations WHERE id::text=%s", (conv_id,))
                tenant_row = tenant_cur.fetchone()
                if tenant_row:
                    tenant_id = tenant_row[0]
        with pg_conn.cursor() as tenant_cur:
            tenant_cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))

        if apply_read_scope:
            from app.mount.read_scope import read_scope_refusal

            refusal = read_scope_refusal(pg_conn, registry.CTX_CONV.get(), name, args)
            if refusal is not None:
                pg_conn.rollback()
                return refusal

        result = fn(adapter, **args)
        pg_conn.commit()
    except psycopg2.Error as e:
        pg_conn.rollback()
        result = {
            "code": "db_error",
            "message": str(e),
            "hint": (
                "The database may not be seeded; check GET /api/health. Retry once, then tell main to stop this "
                "branch if it still fails."
            ),
            "retryable": True,
        }
    except (TypeError, ValueError) as e:
        pg_conn.rollback()
        result = {
            "code": "bad_type",
            "message": f"invalid or missing parameter: {e}",
            "hint": f"Valid parameters: {sig_hint}.",
            "retryable": False,
        }
    except Exception as e:
        pg_conn.rollback()
        result = {
            "code": "tool_error",
            "message": str(e)[:200],
            "hint": "Internal tool error; retry once, then report it to main if it recurs.",
            "retryable": True,
        }
    finally:
        adapter.close_cursors()
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

    from claude_agent_sdk import tool
    from roles._retrieval import functions as R

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
                        "message": "Interaction notes are internal bank data.",
                        "hint": (
                            "This tool is only for internal operational sessions and is unavailable for customer "
                            "queries."
                        ),
                        "retryable": False,
                    }
                )
            if _name == "notes_search":
                from app.retrieval.vector_notes import search_notes_from_vector_index

                indexed = search_notes_from_vector_index(args)
                if indexed is not None:
                    return _text(indexed)
            return _text(run_labpack_fn(_fn, _name, args, _known, _hint, apply_read_scope=False))

        tools.append(
            tool(
                name=name,
                description=spec.get("description", spec.get("m\u00f4 t\u1ea3", "")),
                input_schema=schema_to_input(spec["params"]),
                annotations=_annotations(R.ANNOTATIONS_RETRIEVAL.get(name)),
            )(_handler)
        )
    return tools


def _is_customer_conv() -> bool:

    import psycopg2

    from app.orch import registry

    conv_id = registry.CTX_CONV.get()
    if not conv_id:
        return False
    try:
        conn = connect_core()
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

    mod = importlib.import_module(f"roles.{role}.functions")
    skill_path = ROLES_DIR / role / "SKILL.md"
    skill = skill_path.read_text()

    present_path = ROLES_DIR / role / "SKILL.present.md"
    if present_path.exists():
        skill = skill + "\n\n" + present_path.read_text()
    skill = get_prompt_service().text(f"role.{role}.system", skill)

    from app.orch.gated import GATED_WHITELIST, gated

    sdk_tools = []
    for name, fn in mod.REGISTRY.items():
        read_handler = _make_handler(fn, name, mod.SCHEMAS)
        # Brake (T3-1, advisor #5): tools in GATED_WHITELIST use a gated handler with its own connection and transaction.

        handler = gated(name, read_handler) if name in GATED_WHITELIST else read_handler
        input_schema = schema_to_input(mod.SCHEMAS[name].get("params", {}))
        sdk_tools.append(
            tool(
                name=name,
                description=mod.SCHEMAS[name].get("description", mod.SCHEMAS[name].get("m\u00f4 t\u1ea3", "")),
                input_schema=input_schema,
                annotations=_annotations(mod.ANNOTATIONS.get(name)),
            )(handler)
        )

    server = create_sdk_mcp_server(f"banking_{role}", version="1.0.0", tools=sdk_tools)
    allowed = [f"mcp__banking_{role}__{n}" for n in mod.REGISTRY]
    return skill, server, allowed
