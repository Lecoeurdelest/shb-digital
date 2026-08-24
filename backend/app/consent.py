"""Server-owned consent wording + append-only insert seam (S20 · D-80).

Wording is a reviewed GitOps artifact. The parser is deliberately strict and hashes the exact
UTF-8 bytes shown in ``content_markdown``; request clients never choose its version or checksum.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PURPOSE = "pre_pilot_shadow_preassessment"
_REVIEW_STATUSES = {"draft", "pending_bank_approval", "approved"}
_VERSION_RE = re.compile(r"^v[1-9][0-9]*$")
_CHECKSUM_RE = re.compile(r"^[0-9a-f]{64}$")
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORDING_PATH = _REPO_ROOT / "configs" / "consent" / "pre-pilot.vi.md"


class ConsentWordingError(ValueError):
    """Fail-closed wording/config error without echoing sensitive or untrusted content."""


@dataclass(frozen=True)
class ConsentWording:
    version: str
    purpose: str
    review_status: str
    approved_for_real_data: bool
    content_markdown: str
    checksum: str

    def snapshot(self) -> dict[str, Any]:
        return {
            "required": True,
            "purpose": self.purpose,
            "wording_version": self.version,
            "wording_checksum": self.checksum,
            "content_markdown": self.content_markdown,
        }


def load_wording(path: Path | None = None) -> ConsentWording:
    wording_path = path or DEFAULT_WORDING_PATH
    try:
        raw = wording_path.read_bytes()
    except OSError as exc:
        raise ConsentWordingError("consent wording cannot be loaded") from exc
    if not raw.startswith(b"---\n"):
        raise ConsentWordingError("consent wording metadata header is missing")
    closing = raw.find(b"\n---\n", 4)
    if closing < 0:
        raise ConsentWordingError("consent wording metadata header is not closed")
    metadata_bytes = raw[4:closing]
    content_bytes = raw[closing + 5 :]
    try:
        metadata = yaml.safe_load(metadata_bytes.decode("utf-8"))
        content = content_bytes.decode("utf-8")
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ConsentWordingError("consent wording is not valid UTF-8/YAML") from exc
    required_keys = {"version", "purpose", "review_status", "approved_for_real_data"}
    if not isinstance(metadata, dict) or set(metadata) != required_keys:
        raise ConsentWordingError("consent wording metadata keys are invalid")
    version = metadata["version"]
    purpose = metadata["purpose"]
    review_status = metadata["review_status"]
    approved_for_real_data = metadata["approved_for_real_data"]
    if not isinstance(version, str) or _VERSION_RE.fullmatch(version) is None:
        raise ConsentWordingError("consent wording version is invalid")
    if purpose != PURPOSE:
        raise ConsentWordingError("consent wording purpose is not allowlisted")
    if review_status not in _REVIEW_STATUSES:
        raise ConsentWordingError("consent wording review status is invalid")
    if not isinstance(approved_for_real_data, bool):
        raise ConsentWordingError("consent wording real-data flag must be boolean")
    if approved_for_real_data != (review_status == "approved"):
        raise ConsentWordingError("consent wording review status and real-data flag disagree")
    if not content.strip():
        raise ConsentWordingError("consent wording content is empty")
    return ConsentWording(
        version=version,
        purpose=purpose,
        review_status=review_status,
        approved_for_real_data=approved_for_real_data,
        content_markdown=content,
        checksum=hashlib.sha256(content_bytes).hexdigest(),
    )


def snapshot_matches(snapshot: Any, wording: ConsentWording) -> bool:
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "required",
        "purpose",
        "wording_version",
        "wording_checksum",
        "content_markdown",
    }:
        return False
    checksum = snapshot.get("wording_checksum")
    content = snapshot.get("content_markdown")
    if not isinstance(checksum, str) or _CHECKSUM_RE.fullmatch(checksum) is None or not isinstance(content, str):
        return False
    actual = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return (
        snapshot.get("required") is True
        and snapshot.get("purpose") == wording.purpose
        and snapshot.get("wording_version") == wording.version
        and hmac.compare_digest(checksum, actual)
        and hmac.compare_digest(checksum, wording.checksum)
        and content == wording.content_markdown
    )


def insert_record(
    cur: Any,
    *,
    tenant_id: str,
    subject_ref: str,
    actor: str,
    source_ref: str,
    wording: ConsentWording,
) -> str:
    """Append one granted event using caller's transaction; never commits or opens a connection."""
    cur.execute(
        "INSERT INTO consent_records (tenant_id, subject_type, subject_ref, purpose, wording_version, "
        "wording_checksum, granted, recorded_at, granted_at, actor, source, source_ref) "
        "VALUES (%s,'user',%s,%s,%s,%s,TRUE,now(),now(),%s,'customer_form',%s) RETURNING id::text",
        (tenant_id, subject_ref, wording.purpose, wording.version, wording.checksum, actor, source_ref),
    )
    return str(cur.fetchone()["id"])
