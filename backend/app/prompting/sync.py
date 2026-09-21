"""Idempotently register repository prompts as immutable DB versions."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from typing import Any

import psycopg2.extras

from app.prompting.catalog import BACKEND_ROOT, FilePromptCatalog
from app.storage import connect_capability

REPO_ROOT = BACKEND_ROOT.parent


_SYNC_LOCK_KEY = int(hashlib.sha256(b"bank-digital:prompt-sync:v1").hexdigest()[:15], 16)


@dataclass(frozen=True)
class PromptSeed:
    key: str
    scope: str
    content: str
    variables: tuple[str, ...]
    description: str | None
    default_file: str


def repository_prompts() -> list[PromptSeed]:
    files = FilePromptCatalog()
    seeds = [
        PromptSeed(
            key=definition.key,
            scope=definition.scope,
            content=definition.file.read_text(encoding="utf-8"),
            variables=definition.variables,
            description=definition.description,
            default_file=str(definition.file.relative_to(REPO_ROOT)),
        )
        for definition in files.definitions().values()
    ]
    roles_root = REPO_ROOT / "roles"
    for role_dir in sorted(path for path in roles_root.iterdir() if path.is_dir() and not path.name.startswith("_")):
        skill_path = role_dir / "SKILL.md"
        if not skill_path.exists():
            continue
        content = skill_path.read_text(encoding="utf-8")
        present_path = role_dir / "SKILL.present.md"
        if present_path.exists():
            content += "\n\n" + present_path.read_text(encoding="utf-8")
        seeds.append(
            PromptSeed(
                key=f"role.{role_dir.name}.system",
                scope="role",
                content=content,
                variables=(),
                description=f"System prompt for role {role_dir.name}",
                default_file=str(skill_path.relative_to(REPO_ROOT)),
            )
        )
    return seeds


def _sync_one(cur: Any, seed: PromptSeed, environment: str, activate: bool, actor: str) -> tuple[bool, bool]:
    checksum = hashlib.sha256(seed.content.encode("utf-8")).hexdigest()
    cur.execute(
        "INSERT INTO prompt_definitions(prompt_key,scope,description,variables,default_file) "
        "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(prompt_key) DO UPDATE SET "
        "scope=EXCLUDED.scope,description=EXCLUDED.description,variables=EXCLUDED.variables,"
        "default_file=EXCLUDED.default_file,updated_at=now()",
        (seed.key, seed.scope, seed.description, json.dumps(seed.variables), seed.default_file),
    )
    cur.execute(
        "SELECT id,version FROM prompt_versions WHERE prompt_key=%s AND checksum=%s",
        (seed.key, checksum),
    )
    row = cur.fetchone()
    created = row is None
    if row is None:
        cur.execute(
            "SELECT COALESCE(max(version),0)+1 AS next_version FROM prompt_versions WHERE prompt_key=%s",
            (seed.key,),
        )
        version = cur.fetchone()["next_version"]
        cur.execute(
            "INSERT INTO prompt_versions(prompt_key,version,content,checksum,created_by) "
            "VALUES(%s,%s,%s,%s,%s) RETURNING id,version",
            (seed.key, version, seed.content, checksum, actor),
        )
        row = cur.fetchone()
    cur.execute(
        "SELECT version_id FROM prompt_bindings WHERE prompt_key=%s AND environment=%s",
        (seed.key, environment),
    )
    binding = cur.fetchone()
    should_bind = activate or binding is None
    if should_bind:
        cur.execute(
            "INSERT INTO prompt_bindings(prompt_key,environment,version_id,activated_by) "
            "VALUES(%s,%s,%s,%s) ON CONFLICT(prompt_key,environment) DO UPDATE SET "
            "version_id=EXCLUDED.version_id,activated_by=EXCLUDED.activated_by,activated_at=now()",
            (seed.key, environment, row["id"], actor),
        )
    return created, should_bind


def sync_repository_prompts(
    *, environment: str = "default", activate: bool = False, actor: str = "repository-sync"
) -> dict[str, int]:
    conn = connect_capability("prompt_catalog")
    counts = {"definitions": 0, "versions_created": 0, "bindings_updated": 0}
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (_SYNC_LOCK_KEY,))
            for seed in repository_prompts():
                created, bound = _sync_one(cur, seed, environment, activate, actor)
                counts["definitions"] += 1
                counts["versions_created"] += int(created)
                counts["bindings_updated"] += int(bound)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", default="default")
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--actor", default="repository-sync")
    args = parser.parse_args()
    print(json.dumps(sync_repository_prompts(environment=args.environment, activate=args.activate, actor=args.actor)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
