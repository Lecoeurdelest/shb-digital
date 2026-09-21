"""Versioned prompt administration; secrets and execution guards stay outside this service."""

from __future__ import annotations

import hashlib
import os
from typing import Any

from app.errors import ApiError
from app.prompting import get_prompt_service
from app.storage import connect_capability


def _environment() -> str:
    return os.environ.get("SHB_PROMPT_ENV", "default").strip() or "default"


def snapshot() -> dict[str, Any]:
    from app.orch.providers import providers

    environment = _environment()
    conn = connect_capability("prompt_catalog")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT pd.prompt_key,pd.scope,pd.description,pd.variables,pv.version,pv.content,
                pb.activated_by,pb.activated_at FROM prompt_definitions pd
                LEFT JOIN prompt_bindings pb ON pb.prompt_key=pd.prompt_key AND pb.environment=%s
                LEFT JOIN prompt_versions pv ON pv.id=pb.version_id ORDER BY pd.scope,pd.prompt_key""",
                (environment,),
            )
            prompts = [
                {
                    "key": key,
                    "scope": scope,
                    "description": description,
                    "variables": variables or [],
                    "active": {
                        "version": version,
                        "content": content,
                        "activated_by": actor,
                        "activated_at": activated_at,
                    }
                    if version is not None
                    else None,
                }
                for key, scope, description, variables, version, content, actor, activated_at in cur.fetchall()
            ]
        conn.rollback()
    finally:
        conn.close()
    providers.reload()
    return {"environment": environment, "providers": providers.public_view(), "prompts": prompts}


def save_prompt(key: str, content: str, activate: bool, actor: str) -> dict[str, Any]:
    content = content.strip()
    if not content or len(content) > 30_000:
        raise ApiError(400, "invalid_prompt", "The prompt content is invalid.", "Enter 1 to 30,000 characters.", False)
    environment, checksum = _environment(), hashlib.sha256(content.encode()).hexdigest()
    conn = connect_capability("prompt_catalog")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (key,))
            cur.execute("SELECT 1 FROM prompt_definitions WHERE prompt_key=%s", (key,))
            if cur.fetchone() is None:
                raise ApiError(
                    404,
                    "prompt_not_found",
                    "The agent configuration was not found.",
                    "Reload the prompt list.",
                    False,
                )
            cur.execute("SELECT id,version FROM prompt_versions WHERE prompt_key=%s AND checksum=%s", (key, checksum))
            row = cur.fetchone()
            if row is None:
                cur.execute("SELECT COALESCE(MAX(version),0)+1 FROM prompt_versions WHERE prompt_key=%s", (key,))
                version = int(cur.fetchone()[0])
                cur.execute(
                    "INSERT INTO prompt_versions (prompt_key,version,content,checksum,created_by) "
                    "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                    (key, version, content, checksum, actor),
                )
                version_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO agent_config_events (prompt_key,environment,version,action,actor) "
                    "VALUES (%s,%s,%s,'version_created',%s)",
                    (key, environment, version, actor),
                )
            else:
                version_id, version = row
            if activate:
                cur.execute(
                    """INSERT INTO prompt_bindings (prompt_key,environment,version_id,activated_by,activated_at)
                VALUES (%s,%s,%s,%s,now()) ON CONFLICT (prompt_key,environment) DO UPDATE
                SET version_id=EXCLUDED.version_id,activated_by=EXCLUDED.activated_by,
                activated_at=EXCLUDED.activated_at""",
                    (key, environment, version_id, actor),
                )
                cur.execute(
                    "INSERT INTO agent_config_events (prompt_key,environment,version,action,actor) "
                    "VALUES (%s,%s,%s,'activated',%s)",
                    (key, environment, version, actor),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    get_prompt_service().clear()
    return snapshot()
