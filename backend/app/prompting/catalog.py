"""Versioned prompt resolution: database binding first, repository file fallback."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any

import psycopg2
import psycopg2.extras

from app.storage import connect_capability

log = logging.getLogger("prompt.catalog")
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPT_ROOT = BACKEND_ROOT / "prompts"


class PromptRenderError(ValueError):
    pass


@dataclass(frozen=True)
class PromptDefinition:
    key: str
    scope: str
    file: Path
    variables: tuple[str, ...]
    description: str | None = None


@dataclass(frozen=True)
class ActivePrompt:
    key: str
    content: str
    variables: tuple[str, ...]
    version: int
    checksum: str


def render_template(content: str, variables: tuple[str, ...], values: dict[str, Any]) -> str:
    missing = set(variables) - values.keys()
    if missing:
        raise PromptRenderError(f"missing prompt variables: {sorted(missing)}")
    try:
        return Template(content).substitute({key: str(values[key]) for key in variables})
    except (KeyError, ValueError) as exc:
        raise PromptRenderError("prompt contains an invalid or undeclared variable") from exc


class FilePromptCatalog:
    def __init__(self, root: Path = DEFAULT_PROMPT_ROOT) -> None:
        self.root = root
        self._definitions: dict[str, PromptDefinition] | None = None

    def definitions(self) -> dict[str, PromptDefinition]:
        if self._definitions is None:
            payload = json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))
            if payload.get("version") != 1 or not isinstance(payload.get("prompts"), dict):
                raise PromptRenderError("prompt catalog must use schema version 1")
            definitions: dict[str, PromptDefinition] = {}
            for key, raw in payload["prompts"].items():
                path = (self.root / raw["file"]).resolve()
                if self.root.resolve() not in path.parents:
                    raise PromptRenderError(f"prompt file escapes catalog root: {key}")
                definitions[key] = PromptDefinition(
                    key=key,
                    scope=str(raw["scope"]),
                    file=path,
                    variables=tuple(str(item) for item in raw.get("variables", [])),
                    description=raw.get("description"),
                )
            self._definitions = definitions
        return self._definitions

    def definition(self, key: str) -> PromptDefinition:
        try:
            return self.definitions()[key]
        except KeyError as exc:
            raise PromptRenderError(f"unknown file prompt: {key}") from exc

    def content(self, key: str) -> str:
        return self.definition(key).file.read_text(encoding="utf-8")

    def render(self, key: str, values: dict[str, Any] | None = None) -> str:
        definition = self.definition(key)
        return render_template(self.content(key), definition.variables, values or {})


class DatabasePromptCatalog:
    def __init__(self, environment: str | None = None) -> None:
        self.environment = environment or os.environ.get("SHB_PROMPT_ENV", "default")

    def active(self, key: str) -> ActivePrompt | None:
        conn = connect_capability("prompt_catalog")
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT pv.content,pd.variables,pv.version,pv.checksum "
                    "FROM prompt_bindings pb "
                    "JOIN prompt_versions pv ON pv.id=pb.version_id AND pv.prompt_key=pb.prompt_key "
                    "JOIN prompt_definitions pd ON pd.prompt_key=pb.prompt_key "
                    "WHERE pb.prompt_key=%s AND pb.environment IN (%s,'default') "
                    "ORDER BY (pb.environment=%s) DESC LIMIT 1",
                    (key, self.environment, self.environment),
                )
                row = cur.fetchone()
            conn.rollback()
        finally:
            conn.close()
        if row is None:
            return None
        return ActivePrompt(
            key=key,
            content=row["content"],
            variables=tuple(row["variables"] or []),
            version=int(row["version"]),
            checksum=row["checksum"],
        )


class PromptService:
    def __init__(
        self,
        files: FilePromptCatalog | None = None,
        database: DatabasePromptCatalog | None = None,
        ttl_seconds: float | None = None,
    ) -> None:
        self.files = files or FilePromptCatalog()
        self.database = database or DatabasePromptCatalog()
        self.ttl_seconds = (
            float(os.environ.get("SHB_PROMPT_CACHE_TTL_SECONDS", "60")) if ttl_seconds is None else ttl_seconds
        )
        self._cache: dict[str, tuple[float, ActivePrompt | None]] = {}
        self._lock = threading.Lock()
        self._database_warning_emitted = False

    def _active(self, key: str) -> ActivePrompt | None:
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached is not None and cached[0] > now:
            return cached[1]
        try:
            active = self.database.active(key)
            self._database_warning_emitted = False
        except psycopg2.Error as exc:
            active = None
            if not self._database_warning_emitted:
                log.warning("prompt DB unavailable; using repository defaults (%s)", type(exc).__name__)
                self._database_warning_emitted = True
        with self._lock:
            self._cache[key] = (now + max(self.ttl_seconds, 0), active)
        return active

    def render(self, key: str, values: dict[str, Any] | None = None) -> str:
        values = values or {}
        active = self._active(key)
        if active is not None:
            try:
                return render_template(active.content, active.variables, values)
            except PromptRenderError:
                log.exception("active prompt invalid key=%s version=%s; using file default", key, active.version)
        return self.files.render(key, values)

    def text(self, key: str, fallback: str) -> str:
        active = self._active(key)
        if active is None:
            return fallback
        if active.variables:
            log.error("text prompt key=%s declares variables; using file fallback", key)
            return fallback
        return active.content

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


_service: PromptService | None = None
_service_lock = threading.Lock()


def get_prompt_service() -> PromptService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = PromptService()
    return _service


def reset_prompt_service() -> None:
    global _service
    with _service_lock:
        _service = None
