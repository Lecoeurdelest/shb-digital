"""S23 contract tests for case-intake config v2 and the static startup gate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml
from fastapi.testclient import TestClient

from app.case_intake.config import CaseIntakeConfigError, ProductProfile, load_case_intake_config
from app.main import app


def _source() -> dict:
    return {
        "enabled": True,
        "modes": ["api"],
        "accepted_schema_versions": [1],
        "allowed_event_types": [
            "case.snapshot_upserted",
            "case.preassessment_requested",
            "case.cancelled",
        ],
        "workflow_profile": "preassessment_only",
        "auto_start": "shadow",
        "allowed_products": ["SME_SECURED"],
        "max_payload_bytes": 262_144,
        "api_key_env": "SHB_LOS_CASE_INTAKE_API_KEY",
    }


def _write(path: Path, payload: dict) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_v1_keeps_source_behavior_and_server_owned_defaults(tmp_path):
    config = load_case_intake_config(_write(tmp_path / "v1.yaml", {"version": 1, "sources": {"los": _source()}}))

    source = config.sources["los"]
    assert config.version == 1
    assert source.tenant_slug == "bank-digital-default"
    assert source.product_profiles == {}
    assert source.profile_for("SME_SECURED") == ProductProfile("preassessment_only", "shadow")
    assert source.allowed_products == {"SME_SECURED"}


def test_v2_resolves_product_override_then_absolute_source_fallback(tmp_path):
    source = _source()
    source.update(
        {
            "tenant_slug": "tenant-a",
            "allowed_products": ["SME_SECURED", "UNSECURED_CONSUMER", "UNSECURED_PUBLIC"],
            "product_profiles": {
                "SME_SECURED": {"workflow_profile": "preassessment_only", "auto_start": "off"},
                "UNSECURED_CONSUMER": {
                    "workflow_profile": "preassessment_only",
                    "auto_start": "shadow",
                },
            },
        }
    )
    config = load_case_intake_config(_write(tmp_path / "v2.yaml", {"version": 2, "sources": {"los": source}}))

    assert config.sources["los"].tenant_slug == "tenant-a"
    assert config.sources["los"].profile_for("SME_SECURED").auto_start == "off"
    assert config.sources["los"].profile_for("UNSECURED_PUBLIC") == ProductProfile("preassessment_only", "shadow")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda source: source.pop("tenant_slug"),
        lambda source: source.__setitem__("tenant_slug", "TENANT/unsafe"),
        lambda source: source.pop("product_profiles"),
        lambda source: source["product_profiles"]["UNSECURED_CONSUMER"].__setitem__("extra", True),
        lambda source: source["product_profiles"]["UNSECURED_CONSUMER"].__setitem__("auto_start", "off"),
        lambda source: source["allowed_products"].append("UNKNOWN_PRODUCT"),
        lambda source: source["product_profiles"].__setitem__(
            "UNSECURED_PUBLIC_NOT_ALLOWED",
            {"workflow_profile": "preassessment_only", "auto_start": "shadow"},
        ),
    ],
)
def test_v2_rejects_missing_or_unsafe_tenant_and_product_profiles(tmp_path, mutate):
    source = _source()
    source.update(
        {
            "tenant_slug": "tenant-a",
            "allowed_products": ["SME_SECURED", "UNSECURED_CONSUMER"],
            "product_profiles": {
                "UNSECURED_CONSUMER": {
                    "workflow_profile": "preassessment_only",
                    "auto_start": "shadow",
                }
            },
        }
    )
    mutate(source)

    with pytest.raises(CaseIntakeConfigError):
        load_case_intake_config(_write(tmp_path / "unsafe.yaml", {"version": 2, "sources": {"los": source}}))


def test_unsafe_static_config_stops_before_registry_cleanup_taxonomy_and_boot(monkeypatch, tmp_path):
    from app import reason_taxonomy, runtime_security
    from app.orch import main_session, registry, store

    unsafe = {"version": 2, "sources": {"los": _source()}}  # v2 lacks tenant_slug/product_profiles
    monkeypatch.setenv("SHB_CASE_INTAKE_CONFIG", str(_write(tmp_path / "unsafe-startup.yaml", unsafe)))
    seen: list[str] = []
    monkeypatch.setattr(runtime_security, "validate_runtime_security", lambda: seen.append("security"))
    monkeypatch.setattr(reason_taxonomy, "activate_reason_taxonomy", lambda: seen.append("taxonomy"))
    monkeypatch.setattr(registry, "reset_all", lambda: seen.append("registry"))
    monkeypatch.setattr(store, "cleanup_orphans", AsyncMock(side_effect=lambda _: seen.append("cleanup")))
    monkeypatch.setattr(main_session, "boot", lambda: seen.append("boot"))

    with pytest.raises(CaseIntakeConfigError), TestClient(app):
        pass

    assert seen == ["security"]


def test_runtime_reload_of_invalid_config_returns_safe_503(monkeypatch, tmp_path):
    broken = tmp_path / "broken-runtime.yaml"
    broken.write_text("version: [not-a-schema", encoding="utf-8")
    monkeypatch.setenv("SHB_CASE_INTAKE_CONFIG", str(broken))
    response = TestClient(app).post(
        "/api/integrations/v1/case-events",
        headers={"Authorization": "Bearer present", "Idempotency-Key": "evt-runtime"},
        json={"source_system": "los"},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "case_intake_not_ready"
    assert set(response.json()) == {"code", "message", "hint", "retryable"}
