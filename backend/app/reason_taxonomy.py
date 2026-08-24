"""Strict, versioned reason-code taxonomy (S23 · D-82)."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

VERSION = 1
GROUPS = frozenset({"HS_THIEU", "CIC", "THU_NHAP", "PHAP_LY", "TSDB"})
MANDATORY_CODES = frozenset({"HS_THIEU_DINH_DANH_NOI_BO"})
_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TAXONOMY_PATH = _REPO_ROOT / "configs" / "reason-codes.yaml"


class ReasonTaxonomyError(ValueError):
    """Fail-closed taxonomy error that never echoes an untrusted document."""


@dataclass(frozen=True)
class ReasonCode:
    id: str
    group: str
    description: str

    def canonical(self) -> dict[str, str]:
        return {"description": self.description, "group": self.group, "id": self.id}


@dataclass(frozen=True)
class ReasonTaxonomy:
    version: int
    codes: tuple[ReasonCode, ...]
    checksum: str

    @property
    def allowed_ids(self) -> frozenset[str]:
        return frozenset(code.id for code in self.codes)

    def prompt_lines(self) -> str:
        return "\n".join(f"- `{code.id}` ({code.group}): {code.description}" for code in self.codes)

    def proof(self) -> dict[str, str | int]:
        return {"version": self.version, "checksum": self.checksum}


_active_taxonomy: ReasonTaxonomy | None = None


def _parse_code(raw: Any) -> ReasonCode:
    if not isinstance(raw, dict) or set(raw) != {"id", "group", "description"}:
        raise ReasonTaxonomyError("reason taxonomy code fields are invalid")
    code_id, group, description = raw["id"], raw["group"], raw["description"]
    if not isinstance(group, str) or group not in GROUPS:
        raise ReasonTaxonomyError("reason taxonomy group is not allowlisted")
    if (
        not isinstance(code_id, str)
        or code_id != code_id.strip()
        or _ID_RE.fullmatch(code_id) is None
        or not code_id.startswith(f"{group}_")
    ):
        raise ReasonTaxonomyError("reason taxonomy id is invalid")
    if not isinstance(description, str) or description != description.strip() or not description:
        raise ReasonTaxonomyError("reason taxonomy description is invalid")
    return ReasonCode(id=code_id, group=group, description=description)


def load_reason_taxonomy(path: Path | None = None) -> ReasonTaxonomy:
    """Parse and validate one artifact; checksum parsed/sorted canonical JSON, not YAML bytes."""
    taxonomy_path = path or Path(os.environ.get("SHB_REASON_TAXONOMY_CONFIG", DEFAULT_TAXONOMY_PATH))
    try:
        raw = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ReasonTaxonomyError("reason taxonomy cannot be loaded") from exc
    if not isinstance(raw, dict) or set(raw) != {"version", "codes"}:
        raise ReasonTaxonomyError("reason taxonomy root fields are invalid")
    version = raw["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != VERSION:
        raise ReasonTaxonomyError(f"reason taxonomy must use schema version {VERSION}")
    raw_codes = raw["codes"]
    if not isinstance(raw_codes, list) or not raw_codes:
        raise ReasonTaxonomyError("reason taxonomy codes must be a non-empty list")
    codes = tuple(sorted((_parse_code(item) for item in raw_codes), key=lambda code: code.id))
    ids = [code.id for code in codes]
    if len(ids) != len(set(ids)):
        raise ReasonTaxonomyError("reason taxonomy ids must be unique")
    if not MANDATORY_CODES.issubset(ids):
        raise ReasonTaxonomyError("reason taxonomy is missing a mandatory code")
    canonical = {"codes": [code.canonical() for code in codes], "version": version}
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    checksum = f"sha256:{hashlib.sha256(payload).hexdigest()}"
    return ReasonTaxonomy(version=version, codes=codes, checksum=checksum)


def activate_reason_taxonomy(path: Path | None = None) -> ReasonTaxonomy:
    """Startup seam: validate once and expose the exact artifact to prompt/write-time gates."""
    global _active_taxonomy
    taxonomy = load_reason_taxonomy(path)
    _active_taxonomy = taxonomy
    return taxonomy


def get_reason_taxonomy() -> ReasonTaxonomy:
    """Return the startup-loaded taxonomy; lazy default keeps isolated unit imports usable."""
    global _active_taxonomy
    if _active_taxonomy is None:
        _active_taxonomy = load_reason_taxonomy()
    return _active_taxonomy


def _reset_active_taxonomy_for_tests() -> None:
    global _active_taxonomy
    _active_taxonomy = None
