"""Headless readiness checks for DB, migrations, providers, and MCP role mounts."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from mcp.types import ListToolsRequest

from app.runtime_security import runtime_mode
from app.storage import connect_core, get_registry

log = logging.getLogger("app.readiness")
_BACKEND_ROOT = Path(__file__).resolve().parents[1]


class ReadinessFailure(RuntimeError):
    """Expose failed check names without leaking configuration details over HTTP."""

    def __init__(self, checks: list[str]):
        self.checks = checks
        super().__init__(", ".join(checks))


def check_database() -> None:
    get_registry().healthcheck_required()


def _code_migration_heads() -> set[str]:
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "app" / "db" / "migrations"))
    return set(ScriptDirectory.from_config(config).get_heads())


def check_migration_head() -> None:
    code_heads = _code_migration_heads()
    conn = connect_core()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version_num FROM alembic_version")
            database_heads = {str(row[0]) for row in cur.fetchall()}
    finally:
        conn.close()
    if not code_heads or database_heads != code_heads:
        raise RuntimeError("database migration is not at the code head")


def check_provider_config() -> None:
    from app.orch.providers import providers

    providers.reload()
    enabled = {item["name"]: item for item in providers.public_view()}
    selected = providers.effective_default()
    item = enabled.get(selected)
    if item is None or not item.get("models"):
        raise RuntimeError("selected provider is disabled or has no models")
    providers.resolve_env(selected)  # missing key/config raises without performing external I/O


async def check_role_mounts() -> int:
    from app.mount.mount_role import mount_role
    from app.orch.sub_runner import discovered_roles

    roles = sorted(discovered_roles())
    if not roles:
        raise RuntimeError("no mountable role found")
    for role in roles:
        skill, server, allowed = mount_role(role)
        if not skill.strip() or server.get("name") != f"banking_{role}" or not allowed:
            raise RuntimeError(f"role mount is incomplete: {role}")
        handler = server["instance"].request_handlers[ListToolsRequest]
        result = await handler(ListToolsRequest())
        advertised = {tool.name for tool in result.root.tools}
        expected = {name.rsplit("__", 1)[-1] for name in allowed}
        if advertised != expected:
            raise RuntimeError(f"role tools/list drift: {role}")
    return len(roles)


async def readiness_snapshot() -> dict[str, Any]:
    """Run all checks; return only status/count over HTTP and log details server-side."""
    sync_checks = {
        "database": check_database,
        "migration_head": check_migration_head,
        "provider_config": check_provider_config,
    }
    failures: list[str] = []
    for name, check in sync_checks.items():
        try:
            await asyncio.to_thread(check)
        except Exception as exc:  # noqa: BLE001 — Aggregate failures without exposing details to clients.
            failures.append(name)
            log.error("readiness check failed check=%s exception=%s", name, type(exc).__name__)
    try:
        await check_role_mounts()
    except Exception as exc:  # noqa: BLE001
        failures.append("role_mounts")
        log.error("readiness check failed check=role_mounts exception=%s", type(exc).__name__)
    if failures:
        raise ReadinessFailure(failures)
    return {
        "ready": True,
        "profile": runtime_mode(),
        "checks": {
            "database": True,
            "migrations": True,
            "provider": True,
            "mcp_mounts": True,
        },
    }
