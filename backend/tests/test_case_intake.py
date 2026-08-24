"""D-77 P0 integration tests: auth, atomic idempotency/versioning and legacy read-model."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.db.config import DATABASE_URL
from app.main import app

from .conftest import requires_db


def _config(path: Path, *, enabled: bool = True) -> Path:
    path.write_text(
        "\n".join(
            [
                "version: 1",
                "sources:",
                "  los:",
                f"    enabled: {'true' if enabled else 'false'}",
                "    modes: [api]",
                "    accepted_schema_versions: [1]",
                "    allowed_event_types: [case.snapshot_upserted, case.preassessment_requested, case.cancelled]",
                "    workflow_profile: preassessment_only",
                "    auto_start: shadow",
                "    allowed_products: [SME_SECURED]",
                "    max_payload_bytes: 262144",
                "    api_key_env: SHB_LOS_CASE_INTAKE_API_KEY",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _event(case_id: str, event_id: str, version: int, *, amount: int = 500_000_000) -> dict:
    return {
        "schema_version": 1,
        "event_id": event_id,
        "event_type": "case.preassessment_requested",
        "source_system": "los",
        "source_version": version,
        "occurred_at": "2026-08-24T10:00:00Z",
        "case": {
            "external_case_id": case_id,
            "external_party_id": "CIF-009",
            "assigned_rm_subject": "idp-rm-1",
            "product_code": "SME_SECURED",
            "loan_amount_vnd": amount,
            "document_refs": ["DOC-1", "DOC-2"],
            "missing_fields": [],
        },
    }


def _headers(event_id: str, key: str = "test-intake-key") -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Idempotency-Key": event_id}


def _cleanup(case_id: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT conversation_id FROM external_case_links WHERE source_system='los' AND external_case_id=%s",
                (case_id,),
            )
            row = cur.fetchone()
            cur.execute("DELETE FROM integration_inbox WHERE source_system='los' AND external_case_id=%s", (case_id,))
            cur.execute("DELETE FROM external_case_links WHERE source_system='los' AND external_case_id=%s", (case_id,))
            if row and row[0]:
                cur.execute("DELETE FROM conversations WHERE id=%s", (row[0],))
    finally:
        conn.close()


@pytest.fixture
def intake_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SHB_CASE_INTAKE_CONFIG", str(_config(tmp_path / "case-intake.yaml")))
    monkeypatch.setenv("SHB_LOS_CASE_INTAKE_API_KEY", "test-intake-key")


@requires_db
def test_happy_event_is_atomic_and_does_not_start_agent_or_approval(intake_env):
    case_id = f"LOS-{uuid4()}"
    event_id = f"evt-{uuid4()}"
    try:
        response = TestClient(app).post(
            "/api/integrations/v1/case-events", json=_event(case_id, event_id, 1), headers=_headers(event_id)
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "accepted"
        assert body["case_status"] == "ready_for_preassessment"
        assert body["conversation_id"]

        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM integration_inbox WHERE source_system='los' AND event_id=%s", (event_id,)
                )
                assert cur.fetchone()[0] == 1
                cur.execute("SELECT count(*) FROM tasks WHERE conv_id=%s", (body["conversation_id"],))
                assert cur.fetchone()[0] == 0
                cur.execute("SELECT count(*) FROM approvals WHERE conv_id=%s", (body["conversation_id"],))
                assert cur.fetchone()[0] == 0
                cur.execute("SELECT count(*) FROM messages WHERE conv_id=%s", (body["conversation_id"],))
                assert cur.fetchone()[0] == 0
                cur.execute("SELECT title FROM conversations WHERE id=%s", (body["conversation_id"],))
                assert cur.fetchone()[0] == "Phiên xử lý sơ thẩm"
        finally:
            conn.close()
    finally:
        _cleanup(case_id)


@requires_db
def test_same_event_is_duplicate_but_changed_payload_conflicts(intake_env):
    case_id = f"LOS-{uuid4()}"
    event_id = f"evt-{uuid4()}"
    client = TestClient(app)
    try:
        original = _event(case_id, event_id, 1)
        assert (
            client.post("/api/integrations/v1/case-events", json=original, headers=_headers(event_id)).status_code
            == 202
        )
        duplicate = client.post("/api/integrations/v1/case-events", json=original, headers=_headers(event_id))
        assert duplicate.status_code == 202
        assert duplicate.json()["status"] == "duplicate"

        changed = _event(case_id, event_id, 1, amount=600_000_000)
        conflict = client.post("/api/integrations/v1/case-events", json=changed, headers=_headers(event_id))
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "idempotency_conflict"
    finally:
        _cleanup(case_id)


@requires_db
def test_stale_version_is_recorded_and_equal_changed_version_conflicts(intake_env):
    case_id = f"LOS-{uuid4()}"
    client = TestClient(app)
    try:
        current_id = f"evt-{uuid4()}"
        current = _event(case_id, current_id, 2)
        assert (
            client.post("/api/integrations/v1/case-events", json=current, headers=_headers(current_id)).status_code
            == 202
        )

        stale_id = f"evt-{uuid4()}"
        stale = client.post(
            "/api/integrations/v1/case-events",
            json=_event(case_id, stale_id, 1),
            headers=_headers(stale_id),
        )
        assert stale.status_code == 202
        assert stale.json()["status"] == "stale_ignored"

        conflict_id = f"evt-{uuid4()}"
        conflict = client.post(
            "/api/integrations/v1/case-events",
            json=_event(case_id, conflict_id, 2, amount=600_000_000),
            headers=_headers(conflict_id),
        )
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "source_version_conflict"
    finally:
        _cleanup(case_id)


@requires_db
def test_source_requires_correct_service_key_and_must_be_enabled(monkeypatch, tmp_path):
    case_id = f"LOS-{uuid4()}"
    event_id = f"evt-{uuid4()}"
    monkeypatch.setenv("SHB_CASE_INTAKE_CONFIG", str(_config(tmp_path / "enabled.yaml")))
    monkeypatch.setenv("SHB_LOS_CASE_INTAKE_API_KEY", "test-intake-key")
    client = TestClient(app)
    assert client.post("/api/integrations/v1/case-events", json=_event(case_id, event_id, 1)).status_code == 401
    assert (
        client.post(
            "/api/integrations/v1/case-events",
            json=_event(case_id, event_id, 1),
            headers=_headers(event_id, "wrong"),
        ).status_code
        == 401
    )

    monkeypatch.setenv("SHB_CASE_INTAKE_CONFIG", str(_config(tmp_path / "disabled.yaml", enabled=False)))
    disabled = client.post(
        "/api/integrations/v1/case-events", json=_event(case_id, event_id, 1), headers=_headers(event_id)
    )
    assert disabled.status_code == 403
    assert disabled.json()["code"] == "source_disabled"


@requires_db
def test_same_event_race_across_two_cases_never_returns_500(intake_env):
    event_id = f"evt-{uuid4()}"
    first_case = f"LOS-{uuid4()}"
    second_case = f"LOS-{uuid4()}"

    def send(case_id: str, amount: int):
        return TestClient(app).post(
            "/api/integrations/v1/case-events",
            json=_event(case_id, event_id, 1, amount=amount),
            headers=_headers(event_id),
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(
                pool.map(lambda args: send(*args), [(first_case, 500_000_000), (second_case, 600_000_000)])
            )
        assert sorted(response.status_code for response in responses) == [202, 409]
        assert (
            next(response for response in responses if response.status_code == 409).json()["code"]
            == "idempotency_conflict"
        )
    finally:
        _cleanup(first_case)
        _cleanup(second_case)


@requires_db
def test_snapshot_preserves_workflow_and_cancelled_status_and_external_party_does_not_join_assessment(intake_env):
    case_id = f"LOS-{uuid4()}"
    client = TestClient(app)

    def send(event_id: str, version: int, event_type: str, missing: list[str] | None = None):
        payload = _event(case_id, event_id, version)
        payload["event_type"] = event_type
        payload["case"]["external_party_id"] = "C001"  # coincides with a seeded internal owner
        payload["case"]["missing_fields"] = missing or []
        return client.post("/api/integrations/v1/case-events", json=payload, headers=_headers(event_id))

    try:
        first = f"evt-{uuid4()}"
        assert send(first, 1, "case.preassessment_requested").json()["case_status"] == "ready_for_preassessment"
        snapshot = f"evt-{uuid4()}"
        assert (
            send(snapshot, 2, "case.snapshot_upserted", ["tax_return"]).json()["case_status"]
            == "ready_for_preassessment"
        )
        cancelled = f"evt-{uuid4()}"
        assert send(cancelled, 3, "case.cancelled").json()["case_status"] == "cancelled"
        later = f"evt-{uuid4()}"
        assert send(later, 4, "case.snapshot_upserted").json()["case_status"] == "cancelled"

        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        assert login.status_code == 200
        rows = client.get("/api/cases", params={"source": "los"}).json()
        row = next(item for item in rows if item["external_case_id"] == case_id)
        assert row["assessment"] == {"lane": None, "created_at": None}
    finally:
        _cleanup(case_id)


@requires_db
def test_cancelled_case_cannot_be_reopened_or_create_conversation(intake_env):
    case_id = f"LOS-{uuid4()}"
    client = TestClient(app)

    def send(event_type: str, version: int):
        event_id = f"evt-{uuid4()}"
        payload = _event(case_id, event_id, version)
        payload["event_type"] = event_type
        return client.post("/api/integrations/v1/case-events", json=payload, headers=_headers(event_id))

    try:
        cancelled = send("case.cancelled", 1)
        assert cancelled.status_code == 202
        assert cancelled.json()["case_status"] == "cancelled"
        assert cancelled.json()["conversation_id"] is None

        later = send("case.preassessment_requested", 2)
        assert later.status_code == 202
        assert later.json()["case_status"] == "cancelled"
        # Hồ sơ đã hủy phải dừng hẳn; không được âm thầm tạo workflow mới chỉ vì event tới muộn.
        assert later.json()["conversation_id"] is None

        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT e.conversation_id,count(DISTINCT t.id),count(DISTINCT a.id),"
                    "count(DISTINCT m.id) FROM external_case_links e "
                    "LEFT JOIN tasks t ON t.conv_id=e.conversation_id::text "
                    "LEFT JOIN approvals a ON a.conv_id=e.conversation_id::text "
                    "LEFT JOIN messages m ON m.conv_id=e.conversation_id::text "
                    "WHERE e.source_system='los' AND e.external_case_id=%s GROUP BY e.conversation_id",
                    (case_id,),
                )
                assert cur.fetchone() == (None, 0, 0, 0)
        finally:
            conn.close()
    finally:
        _cleanup(case_id)


@requires_db
def test_async_routes_offload_sync_database_work(intake_env, monkeypatch):
    import app.api.case_intake as case_api

    original = case_api.asyncio.to_thread
    calls = []

    async def tracking(func, *args, **kwargs):
        calls.append(func)
        return await original(func, *args, **kwargs)

    monkeypatch.setattr(case_api.asyncio, "to_thread", tracking)
    case_id = f"LOS-{uuid4()}"
    event_id = f"evt-{uuid4()}"
    client = TestClient(app)
    try:
        response = client.post(
            "/api/integrations/v1/case-events", json=_event(case_id, event_id, 1), headers=_headers(event_id)
        )
        assert response.status_code == 202
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        assert login.status_code == 200
        assert client.get("/api/cases", params={"source": "los"}).status_code == 200
        assert case_api.ingest_case_event in calls
        assert case_api.list_cases in calls
    finally:
        _cleanup(case_id)


@requires_db
def test_admin_case_read_model_includes_legacy_applications():
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert login.status_code == 200
    response = client.get("/api/cases", params={"source": "internal_operations", "limit": 20})
    assert response.status_code == 200
    rows = response.json()
    assert rows
    app01 = next(row for row in rows if row["external_case_id"] == "APP01")
    assert app01["id"] == "internal_operations:APP01"
    assert app01["internal_application_id"] == "APP01"
    assert app01["source_system"] == "internal_operations"
    assert set(app01["assessment"]) == {"lane", "created_at"}
    app03 = next(row for row in rows if row["external_case_id"] == "APP03")
    assert app03["case_status"] == "ready_for_preassessment"
    assert app03["data_as_of"].count("T") == 1


@requires_db
def test_admin_case_read_model_exposes_source_configuration_state(monkeypatch, tmp_path):
    client = TestClient(app)
    # Source existence is operational information: auth must run before route validation.
    assert client.get("/api/cases", params={"source": "not_configured"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).status_code == 200

    internal = client.get("/api/cases", params={"source": "internal_operations"})
    assert internal.status_code == 200

    monkeypatch.setenv("SHB_CASE_INTAKE_CONFIG", str(_config(tmp_path / "enabled.yaml")))
    enabled = client.get("/api/cases", params={"source": "los"})
    assert enabled.status_code == 200

    unknown = client.get("/api/cases", params={"source": "not_configured"})
    assert unknown.status_code == 404
    assert unknown.json() == {
        "code": "source_not_configured",
        "message": "Nguồn hồ sơ chưa được cấu hình.",
        "hint": "Kiểm tra tên nguồn tích hợp.",
        "retryable": False,
    }

    monkeypatch.setenv("SHB_CASE_INTAKE_CONFIG", str(_config(tmp_path / "disabled.yaml", enabled=False)))
    disabled = client.get("/api/cases", params={"source": "los"})
    assert disabled.status_code == 403
    assert disabled.json() == {
        "code": "source_disabled",
        "message": "Nguồn hồ sơ đang bị tắt.",
        "hint": "Liên hệ vận hành tích hợp để kiểm tra trạng thái nguồn.",
        "retryable": False,
    }


@requires_db
def test_case_read_model_requires_admin_and_uses_four_field_errors():
    anonymous = TestClient(app).get("/api/cases")
    assert anonymous.status_code == 401
    assert set(anonymous.json()) == {"code", "message", "hint", "retryable"}

    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "user", "password": "user"})
    assert login.status_code == 200
    forbidden = client.get("/api/cases")
    assert forbidden.status_code == 403
    assert set(forbidden.json()) == {"code", "message", "hint", "retryable"}


def test_committed_config_is_disabled_and_contains_only_env_name():
    text = Path(__file__).resolve().parents[2].joinpath("configs/case-intake.yaml").read_text(encoding="utf-8")
    assert "enabled: false" in text
    assert "api_key_env: SHB_LOS_CASE_INTAKE_API_KEY" in text
    assert "test-intake-key" not in text
