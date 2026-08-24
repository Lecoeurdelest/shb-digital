"""S23 DB/API tests for tenant-bound zero-auto intake, RFI and exact-case authz."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import psycopg2
import pytest
import yaml
from fastapi.testclient import TestClient

from app.auth.security import make_token
from app.db.config import DATABASE_URL
from app.main import app
from app.tenancy import DEFAULT_TENANT_ID

from .conftest import requires_db


def _config(path: Path, tenant_slug: str = "bank-digital-default") -> Path:
    source = {
        "tenant_slug": tenant_slug,
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
        "allowed_products": ["SME_SECURED", "UNSECURED_CONSUMER", "UNSECURED_PUBLIC"],
        "product_profiles": {
            "UNSECURED_CONSUMER": {"workflow_profile": "preassessment_only", "auto_start": "shadow"},
            "UNSECURED_PUBLIC": {"workflow_profile": "preassessment_only", "auto_start": "shadow"},
        },
        "max_payload_bytes": 262_144,
        "api_key_env": "SHB_LOS_CASE_INTAKE_API_KEY",
    }
    path.write_text(yaml.safe_dump({"version": 2, "sources": {"los": source}}), encoding="utf-8")
    return path


def _event(
    case_id: str,
    event_id: str,
    version: int,
    *,
    product: str = "UNSECURED_CONSUMER",
    missing: list[str] | None = None,
    event_type: str = "case.preassessment_requested",
) -> dict:
    return {
        "schema_version": 1,
        "event_id": event_id,
        "event_type": event_type,
        "source_system": "los",
        "source_version": version,
        "occurred_at": "2026-08-24T10:00:00Z",
        "case": {
            "external_case_id": case_id,
            "external_party_id": "party-secret",
            "assigned_rm_subject": "assignee-secret",
            "product_code": product,
            "loan_amount_vnd": 500_000_000,
            "document_refs": ["document-secret"],
            "missing_fields": missing or [],
        },
    }


def _headers(event_id: str) -> dict[str, str]:
    return {"Authorization": "Bearer s23-service-key", "Idempotency-Key": event_id}


def _auth(role: str, tenant_id: str = DEFAULT_TENANT_ID) -> dict[str, str]:
    token = make_token(user_id=str(uuid4()), username=f"s23-{role}-{uuid4()}", role=role, tenant_id=tenant_id)
    return {"Authorization": f"Bearer {token}"}


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
            conv_id = str(row[0]) if row and row[0] else None
            cur.execute("DELETE FROM integration_inbox WHERE source_system='los' AND external_case_id=%s", (case_id,))
            cur.execute("DELETE FROM external_case_links WHERE source_system='los' AND external_case_id=%s", (case_id,))
            if conv_id:
                for table in ("messages", "tasks", "cards", "tool_calls", "approvals"):
                    cur.execute(f"DELETE FROM {table} WHERE conv_id=%s", (conv_id,))
                cur.execute("DELETE FROM conversations WHERE id=%s", (conv_id,))
    finally:
        conn.close()


@pytest.fixture
def intake_v2(monkeypatch, tmp_path):
    monkeypatch.setenv("SHB_CASE_INTAKE_CONFIG", str(_config(tmp_path / "case-intake-v2.yaml")))
    monkeypatch.setenv("SHB_LOS_CASE_INTAKE_API_KEY", "s23-service-key")


@requires_db
def test_new_product_credential_binds_default_tenant_and_ingest_is_zero_auto(intake_v2, monkeypatch):
    from app.orch import room

    other_tenant, other_slug = str(uuid4()), f"tenant-{uuid4().hex[:10]}"
    case_id, event_id = f"LOS-{uuid4()}", f"evt-{uuid4()}"
    wake = AsyncMock()
    monkeypatch.setattr(room, "handle_room_event", wake)
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tenants(id,slug,name) VALUES(%s,%s,'Other tenant')", (other_tenant, other_slug))
    conn.close()
    try:
        client = TestClient(app)
        first = client.post(
            "/api/integrations/v1/case-events",
            params={"tenant_id": other_tenant},
            json=_event(case_id, event_id, 1),
            headers=_headers(event_id),
        )
        assert first.status_code == 202
        duplicate = client.post(
            "/api/integrations/v1/case-events",
            params={"tenant_id": other_tenant},
            json=_event(case_id, event_id, 1),
            headers=_headers(event_id),
        )
        assert duplicate.status_code == 202
        assert duplicate.json()["status"] == "duplicate"
        assert duplicate.json()["conversation_id"] == first.json()["conversation_id"]

        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT e.tenant_id::text,c.tenant_id::text,i.tenant_id::text "
                    "FROM external_case_links e JOIN conversations c ON c.id=e.conversation_id "
                    "JOIN integration_inbox i ON i.tenant_id=e.tenant_id AND i.source_system=e.source_system "
                    "AND i.external_case_id=e.external_case_id WHERE e.source_system='los' AND e.external_case_id=%s",
                    (case_id,),
                )
                assert cur.fetchone() == (DEFAULT_TENANT_ID, DEFAULT_TENANT_ID, DEFAULT_TENANT_ID)
                conv_id = first.json()["conversation_id"]
                for table in ("messages", "tasks", "cards", "tool_calls", "approvals", "shadow_reviews"):
                    cur.execute(f"SELECT count(*) FROM {table} WHERE conv_id=%s", (conv_id,))
                    assert cur.fetchone()[0] == 0, table
        finally:
            conn.close()
        assert wake.await_count == 0
    finally:
        _cleanup(case_id)
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tenants WHERE id=%s", (other_tenant,))
        conn.close()


@requires_db
def test_unknown_tenant_and_forced_database_failure_return_503_without_partial_write(monkeypatch, tmp_path):
    import app.case_intake.service as service

    case_id, event_id = f"LOS-{uuid4()}", f"evt-{uuid4()}"
    monkeypatch.setenv("SHB_LOS_CASE_INTAKE_API_KEY", "s23-service-key")
    monkeypatch.setenv("SHB_CASE_INTAKE_CONFIG", str(_config(tmp_path / "unknown.yaml", "missing-tenant")))
    client = TestClient(app)
    unknown = client.post(
        "/api/integrations/v1/case-events", json=_event(case_id, event_id, 1), headers=_headers(event_id)
    )
    assert unknown.status_code == 503
    assert set(unknown.json()) == {"code", "message", "hint", "retryable"}
    assert unknown.json()["code"] == "case_intake_not_ready"

    monkeypatch.setenv("SHB_CASE_INTAKE_CONFIG", str(_config(tmp_path / "default.yaml")))
    monkeypatch.setattr(service, "connect_core", lambda: (_ for _ in ()).throw(psycopg2.OperationalError("forced")))
    failed_id = f"evt-{uuid4()}"
    failed = client.post(
        "/api/integrations/v1/case-events", json=_event(case_id, failed_id, 1), headers=_headers(failed_id)
    )
    assert failed.status_code == 503
    assert failed.json()["code"] == "case_intake_not_ready"

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM external_case_links WHERE external_case_id=%s", (case_id,))
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT count(*) FROM integration_inbox WHERE external_case_id=%s", (case_id,))
            assert cur.fetchone()[0] == 0
    finally:
        conn.close()


@requires_db
def test_rfi_changed_set_matrix_normalizes_unknown_and_schedules_only_after_commit(intake_v2, monkeypatch):
    import app.api.case_intake as case_api

    case_id = f"LOS-{uuid4()}"
    seen: list[tuple[str, tuple[str, ...]]] = []
    committed_counts: list[tuple[int, int]] = []

    def observe_postcommit(cid, fields):
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT source_system,external_case_id FROM external_case_links WHERE id=%s", (cid,))
                identity = cur.fetchone()
                assert identity is not None
                cur.execute(
                    "SELECT count(*) FROM integration_inbox WHERE source_system=%s AND external_case_id=%s",
                    identity,
                )
                committed_counts.append((1, cur.fetchone()[0]))
        finally:
            conn.close()
        seen.append((cid, fields))

    monkeypatch.setattr(case_api, "_notify_rfi", observe_postcommit)
    client = TestClient(app)

    def send(
        version: int,
        missing: list[str],
        *,
        event_id: str | None = None,
        event_type: str = "case.preassessment_requested",
    ):
        eid = event_id or f"evt-{uuid4()}"
        response = client.post(
            "/api/integrations/v1/case-events",
            json=_event(case_id, eid, version, missing=missing, event_type=event_type),
            headers=_headers(eid),
        )
        assert response.status_code == 202
        return response

    try:
        first_id = f"evt-{uuid4()}"
        first = send(1, ["identity_document", "DROP TABLE docs", "identity_document"], event_id=first_id)
        changed = send(2, ["income_proof"])
        third_id = f"evt-{uuid4()}"
        same = send(3, ["income_proof"], event_id=third_id)
        assert send(3, ["income_proof"], event_id=third_id).json()["status"] == "duplicate"
        assert send(2, ["identity_document"]).json()["status"] == "stale_ignored"
        assert send(3, ["income_proof"]).json()["status"] == "duplicate"
        send(4, ["legal_document"], event_type="case.cancelled")
        send(5, [], event_type="case.snapshot_upserted")

        assert [fields for _, fields in seen] == [
            ("additional_information", "identity_document"),
            ("income_proof",),
        ]
        assert {cid for cid, _ in seen} == {first.json()["id"]}
        assert committed_counts == [(1, 1), (1, 2)]
        assert changed.json()["id"] == same.json()["id"]
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT missing_fields FROM external_case_links WHERE id=%s", (first.json()["id"],))
                assert cur.fetchone()[0] == []
        finally:
            conn.close()
    finally:
        _cleanup(case_id)


@requires_db
def test_mid_transaction_failure_rolls_back_case_conversation_and_rfi_schedule(intake_v2, monkeypatch):
    import app.api.case_intake as case_api
    import app.case_intake.service as service

    case_id, event_id = f"LOS-{uuid4()}", f"evt-{uuid4()}"
    scheduled: list[object] = []
    created_conversations: list[str] = []
    original_create = service._create_conversation

    def track_create(cur, tenant_id):
        conv_id = original_create(cur, tenant_id)
        created_conversations.append(conv_id)
        return conv_id

    def fail_inbox(*_args, **_kwargs):
        raise psycopg2.OperationalError("forced after case write")

    monkeypatch.setattr(service, "_create_conversation", track_create)
    monkeypatch.setattr(service, "_insert_inbox", fail_inbox)
    monkeypatch.setattr(case_api, "_notify_rfi", lambda *args: scheduled.append(args))
    response = TestClient(app).post(
        "/api/integrations/v1/case-events",
        json=_event(case_id, event_id, 1, missing=["identity_document"]),
        headers=_headers(event_id),
    )

    assert response.status_code == 503
    assert response.json()["code"] == "case_intake_not_ready"
    assert scheduled == []
    assert len(created_conversations) == 1
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM external_case_links WHERE external_case_id=%s", (case_id,))
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT count(*) FROM integration_inbox WHERE event_id=%s", (event_id,))
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT count(*) FROM conversations WHERE id=%s", (created_conversations[0],))
            assert cur.fetchone()[0] == 0
    finally:
        conn.close()


@requires_db
def test_exact_case_is_admin_tenant_scoped_and_malformed_is_404(intake_v2):
    case_id, event_id = f"LOS-{uuid4()}", f"evt-{uuid4()}"
    other_tenant = str(uuid4())
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants(id,slug,name) VALUES(%s,%s,'Other tenant')", (other_tenant, f"t-{uuid4().hex}")
        )
    conn.close()
    try:
        client = TestClient(app)
        created = client.post(
            "/api/integrations/v1/case-events", json=_event(case_id, event_id, 1), headers=_headers(event_id)
        ).json()
        exact_url = f"/api/cases/{created['id']}"
        admin = client.get(exact_url, headers=_auth("admin"))
        assert admin.status_code == 200
        assert admin.json()["id"] == created["id"]
        assert set(admin.json()["assessment"]) == {"lane", "created_at"}

        assert client.get(exact_url).status_code == 401
        for role in ("user", "customer"):
            assert client.get(exact_url, headers=_auth(role)).status_code == 403
        hidden = client.get(exact_url, headers=_auth("admin", other_tenant))
        malformed = client.get("/api/cases/not-a-uuid", headers=_auth("admin"))
        for response in (hidden, malformed, client.get(f"/api/cases/{uuid4()}", headers=_auth("admin"))):
            assert response.status_code == 404
            assert response.json()["code"] == "not_found"
            assert set(response.json()) == {"code", "message", "hint", "retryable"}
    finally:
        _cleanup(case_id)
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tenants WHERE id=%s", (other_tenant,))
        conn.close()


@pytest.mark.asyncio
async def test_rfi_generic_webhook_body_has_exact_two_keys_and_safe_codes(monkeypatch):
    from app.notify import channels

    captured: list[dict] = []

    async def deliver(_url, _channel, _event, body):
        captured.append(body)

    monkeypatch.setenv("SHB_NOTIFY_WEBHOOK_URL", "https://hooks.example/rfi")
    monkeypatch.setenv("SHB_NOTIFY_CHANNEL", "generic")
    monkeypatch.setattr(channels, "app_url", lambda: "https://bank.example/")
    monkeypatch.setattr(channels, "_deliver_guarded", deliver)
    case_id = str(uuid4())
    channels.notify_channel_case_rfi(
        case_id,
        ["tax_return", "raw customer name", "cic_consent", "tax_return"],
    )
    await asyncio.gather(*tuple(channels._bg_tasks))

    assert captured == [
        {
            "missing_fields": ["additional_information", "tax_return"],
            "deep_link": f"https://bank.example/?tab=cases&case={case_id}",
        }
    ]
    assert "cic" not in str(captured).lower()
