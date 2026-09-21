"""T23-3 strict reason taxonomy and deterministic canonical proof."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.reason_taxonomy import (
    DEFAULT_TAXONOMY_PATH,
    MANDATORY_CODES,
    ReasonTaxonomyError,
    load_reason_taxonomy,
)


def _write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def _valid(*, version: str = "1", code_id: str = "HS_THIEU_DINH_DANH_NOI_BO", group: str = "HS_THIEU") -> str:
    return (
        f"version: {version}\ncodes:\n  - id: {code_id}\n    group: {group}\n"
        "    description: Additional evidence required.\n"
    )


def test_repository_taxonomy_has_required_groups_code_and_checksum():
    taxonomy = load_reason_taxonomy(DEFAULT_TAXONOMY_PATH)

    assert taxonomy.version == 1
    assert MANDATORY_CODES <= taxonomy.allowed_ids
    assert "THU_NHAP_DA_XAC_MINH" in taxonomy.allowed_ids
    assert {code.group for code in taxonomy.codes} == {"HS_THIEU", "CIC", "THU_NHAP", "PHAP_LY", "TSDB"}
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", taxonomy.checksum)


def test_checksum_is_parsed_sorted_canonical_json_not_yaml_bytes(tmp_path: Path):
    first = _write(
        tmp_path / "first.yaml",
        """version: 1
codes:
  - id: HS_THIEU_DINH_DANH_NOI_BO
    group: HS_THIEU
    description: Additional evidence required.
  - id: CIC_CAN_RA_SOAT
    group: CIC
    description: Review required.
""",
    )
    second = _write(
        tmp_path / "second.yaml",
        """# comment and order do not affect proof
codes:
- {description: Review required., group: CIC, id: CIC_CAN_RA_SOAT}
- description: Additional evidence required.
  id: HS_THIEU_DINH_DANH_NOI_BO
  group: HS_THIEU
version: 1
""",
    )

    assert load_reason_taxonomy(first).checksum == load_reason_taxonomy(second).checksum


@pytest.mark.parametrize(
    "body",
    [
        _valid(version="2"),
        _valid(version="true"),
        _valid(group="UNKNOWN"),
        _valid(code_id="hs_thieu_bad"),
        _valid(code_id="CIC_SAI_PREFIX"),
        "version: 1\ncodes: []\n",
        "version: 1\ncodes:\n  - id: CIC_CAN_RA_SOAT\n    group: CIC\n    description: x\n",
        _valid() + "  - id: HS_THIEU_DINH_DANH_NOI_BO\n    group: HS_THIEU\n    description: Trung.\n",
        _valid() + "extra: true\n",
    ],
)
def test_malformed_taxonomy_fails_closed(tmp_path: Path, body: str):
    with pytest.raises(ReasonTaxonomyError):
        load_reason_taxonomy(_write(tmp_path / "bad.yaml", body))


def test_unsafe_taxonomy_stops_startup_before_registry_cleanup_and_boot(monkeypatch, tmp_path: Path):
    from app import runtime_security
    from app.case_intake import config as intake_config
    from app.main import app
    from app.orch import main_session, registry, store

    monkeypatch.setenv("SHB_REASON_TAXONOMY_CONFIG", str(_write(tmp_path / "unsafe.yaml", _valid(version="2"))))
    seen: list[str] = []
    monkeypatch.setattr(runtime_security, "validate_runtime_security", lambda: seen.append("security"))
    monkeypatch.setattr(intake_config, "load_case_intake_config", lambda: seen.append("case_config"))
    monkeypatch.setattr(registry, "reset_all", lambda: seen.append("registry"))
    monkeypatch.setattr(store, "cleanup_orphans", AsyncMock(side_effect=lambda _: seen.append("cleanup")))
    monkeypatch.setattr(main_session, "boot", lambda: seen.append("boot"))

    with pytest.raises(ReasonTaxonomyError), TestClient(app):
        pass

    assert seen == ["security", "case_config"]
