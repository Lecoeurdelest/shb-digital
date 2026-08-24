"""Versioned, secret-free source configuration for D-77 case intake."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class CaseIntakeConfigError(ValueError):
    """Safe configuration error; never contains a credential value."""


@dataclass(frozen=True)
class SourceConfig:
    name: str
    enabled: bool
    modes: frozenset[str]
    accepted_schema_versions: frozenset[int]
    allowed_event_types: frozenset[str]
    workflow_profile: str
    auto_start: str
    allowed_products: frozenset[str]
    max_payload_bytes: int
    api_key_env: str

    def api_key(self) -> str | None:
        value = os.environ.get(self.api_key_env)
        return value if value else None


@dataclass(frozen=True)
class CaseIntakeConfig:
    version: int
    sources: dict[str, SourceConfig]


_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = _REPO_ROOT / "configs" / "case-intake.yaml"
_EVENT_TYPES = {
    "case.snapshot_upserted",
    "case.preassessment_requested",
    "case.cancelled",
}


def _string_set(raw: Any, field: str) -> frozenset[str]:
    if not isinstance(raw, list) or any(not isinstance(item, str) or not item.strip() for item in raw):
        raise CaseIntakeConfigError(f"{field} must be a list of non-empty strings")
    return frozenset(item.strip() for item in raw)


def _source(name: str, raw: Any) -> SourceConfig:
    if not isinstance(raw, dict):
        raise CaseIntakeConfigError(f"source {name!r} must be an object")
    modes = _string_set(raw.get("modes", []), f"source {name!r} modes")
    events = _string_set(raw.get("allowed_event_types", []), f"source {name!r} allowed_event_types")
    products = _string_set(raw.get("allowed_products", []), f"source {name!r} allowed_products")
    versions = raw.get("accepted_schema_versions", [])
    if not isinstance(versions, list) or any(not isinstance(item, int) or item < 1 for item in versions):
        raise CaseIntakeConfigError(f"source {name!r} accepted_schema_versions must contain positive integers")
    unknown_events = events - _EVENT_TYPES
    if unknown_events:
        raise CaseIntakeConfigError(f"source {name!r} contains unsupported event types")
    if modes != {"api"}:
        raise CaseIntakeConfigError(f"source {name!r} P0 mode must be api")
    profile = raw.get("workflow_profile")
    auto_start = raw.get("auto_start")
    if profile != "preassessment_only" or auto_start not in {"off", "shadow"}:
        raise CaseIntakeConfigError(f"source {name!r} has an unsafe workflow profile or rollout mode")
    max_bytes = raw.get("max_payload_bytes")
    if not isinstance(max_bytes, int) or not 1024 <= max_bytes <= 1_048_576:
        raise CaseIntakeConfigError(f"source {name!r} max_payload_bytes is outside the safe P0 range")
    api_key_env = raw.get("api_key_env")
    if not isinstance(api_key_env, str) or not api_key_env.startswith("SHB_") or not api_key_env.endswith("_API_KEY"):
        raise CaseIntakeConfigError(f"source {name!r} api_key_env is invalid")
    return SourceConfig(
        name=name,
        enabled=raw.get("enabled") is True,
        modes=modes,
        accepted_schema_versions=frozenset(versions),
        allowed_event_types=events,
        workflow_profile=profile,
        auto_start=auto_start,
        allowed_products=products,
        max_payload_bytes=max_bytes,
        api_key_env=api_key_env,
    )


def load_case_intake_config(path: Path | None = None) -> CaseIntakeConfig:
    config_path = path or Path(os.environ.get("SHB_CASE_INTAKE_CONFIG", DEFAULT_CONFIG_PATH))
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CaseIntakeConfigError("case intake configuration cannot be loaded") from exc
    if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("sources"), dict):
        raise CaseIntakeConfigError("case intake configuration must use schema version 1")
    sources: dict[str, SourceConfig] = {}
    for name, value in raw["sources"].items():
        if not isinstance(name, str) or not name.strip() or name != name.strip().lower():
            raise CaseIntakeConfigError("case intake source names must be lowercase non-empty strings")
        sources[name] = _source(name, value)
    return CaseIntakeConfig(version=1, sources=sources)
