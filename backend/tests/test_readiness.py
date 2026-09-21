from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.api.readiness as readiness_api
import app.readiness as readiness
from app.main import app

from .conftest import requires_db


@pytest.mark.asyncio
async def test_readiness_snapshot_success_shape_is_non_sensitive(monkeypatch):
    monkeypatch.setattr(readiness, "runtime_mode", lambda: "demo")
    monkeypatch.setattr(readiness, "check_database", lambda: None)
    monkeypatch.setattr(readiness, "check_migration_head", lambda: None)
    monkeypatch.setattr(readiness, "check_provider_config", lambda: None)

    async def roles() -> int:
        return 4

    monkeypatch.setattr(readiness, "check_role_mounts", roles)

    assert await readiness.readiness_snapshot() == {
        "ready": True,
        "profile": "demo",
        "checks": {
            "database": True,
            "migrations": True,
            "provider": True,
            "mcp_mounts": True,
        },
    }


def test_ready_failure_is_503_four_field_envelope(monkeypatch):
    async def failed() -> dict:
        raise readiness.ReadinessFailure(["provider_config"])

    monkeypatch.setattr(readiness_api, "readiness_snapshot", failed)
    response = TestClient(app).get("/api/ready")

    assert response.status_code == 503
    assert response.json() == {
        "code": "not_ready",
        "message": "The service is not ready.",
        "hint": "Check the database, migrations, providers, and role mounts in the server logs.",
        "retryable": True,
    }


def test_role_discovery_excludes_internal_retrieval_package():
    from app.orch.sub_runner import discovered_roles

    assert discovered_roles() == {"credit", "legal", "products", "operations"}


@pytest.mark.asyncio
async def test_all_discovered_roles_mount_and_advertise_tools():
    assert await readiness.check_role_mounts() == 4


@requires_db
def test_database_and_migration_head_checks_real_database():
    readiness.check_database()
    readiness.check_migration_head()
