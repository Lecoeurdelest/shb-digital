"""Independent Tester-1 adversarial gate for S23 contract/security invariants.

These tests intentionally exercise seams that are not merely happy-path duplicates of the
implementation tests: disabled-source config validation, source-version identity before RFI
normalization, startup ordering, server-owned memo proof, and linked-conversation authz.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import psycopg2
import pytest
import yaml
from fastapi.testclient import TestClient

from app.auth.security import make_token
from app.case_intake.config import CaseIntakeConfigError, load_case_intake_config
from app.case_intake.normalization import normalize_missing_fields
from app.case_intake.schemas import CaseEventV1
from app.case_intake.service import ingest_case_event
from app.db.config import DATABASE_URL
from app.errors import ApiError
from app.main import app
from app.orch import registry, store
from app.orch.common_tools import present_tool
from app.orch.main_skill import CREDIT_MEMO_SECTIONS, CREDIT_MEMO_TITLE
from app.reason_taxonomy import get_reason_taxonomy
from app.tenancy import DEFAULT_TENANT_ID

from .conftest import requires_db


def _source(*, enabled: bool = True, auto_start: str = "shadow") -> dict:
    return {
        "tenant_slug": "bank-digital-default",
        "enabled": enabled,
        "modes": ["api"],
        "accepted_schema_versions": [1],
        "allowed_event_types": [
            "case.snapshot_upserted",
            "case.preassessment_requested",
            "case.cancelled",
        ],
        "workflow_profile": "preassessment_only",
        "auto_start": auto_start,
        "allowed_products": ["SME_SECURED", "UNSECURED_CONSUMER"],
        "product_profiles": {},
        "max_payload_bytes": 262_144,
        "api_key_env": "SHB_LOS_CASE_INTAKE_API_KEY",
    }


def _write_yaml(path: Path, value: dict) -> Path:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    return path


def _event(case_id: str, event_id: str, *, version: int, missing: list[str]) -> CaseEventV1:
    return CaseEventV1.model_validate(
        {
            "schema_version": 1,
            "event_id": event_id,
            "event_type": "case.preassessment_requested",
            "source_system": "los",
            "source_version": version,
            "occurred_at": "2026-08-24T10:00:00Z",
            "case": {
                "external_case_id": case_id,
                "external_party_id": "external-party-is-not-owner",
                "assigned_rm_subject": "untrusted-assignee",
                "product_code": "UNSECURED_CONSUMER",
                "loan_amount_vnd": 500_000_000,
                "document_refs": ["untrusted-document-ref"],
                "missing_fields": missing,
            },
        }
    )


def _cleanup_case(case_id: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT conversation_id FROM external_case_links WHERE source_system='los' AND external_case_id=%s",
                (case_id,),
            )
            row = cur.fetchone()
            conversation_id = row[0] if row and row[0] else None
            cur.execute(
                "DELETE FROM integration_inbox WHERE source_system='los' AND external_case_id=%s",
                (case_id,),
            )
            cur.execute(
                "DELETE FROM external_case_links WHERE source_system='los' AND external_case_id=%s",
                (case_id,),
            )
            if conversation_id:
                cur.execute("DELETE FROM messages WHERE conv_id=%s", (str(conversation_id),))
                cur.execute("DELETE FROM conversations WHERE id=%s", (conversation_id,))
    finally:
        conn.close()


def _memo(reason_codes: list[str]) -> dict:
    items = [
        {"section": section, "content": f"Content {index}", "source": "credit_assess"}
        for index, section in enumerate(CREDIT_MEMO_SECTIONS, 1)
    ]
    items[4]["reason_codes"] = reason_codes
    items[4]["reason_taxonomy"] = {"version": 999, "checksum": "model-forged"}
    return {"type": "document", "title": CREDIT_MEMO_TITLE, "items": items}


def _tool_payload(envelope: dict) -> dict:
    return json.loads(envelope["content"][0]["text"])


def test_disabled_source_cannot_hide_unsafe_non_sme_fallback(tmp_path: Path):
    """D-81 code guard applies while disabled, so later enable cannot unlock an unsafe profile."""
    source = _source(enabled=False, auto_start="off")
    path = _write_yaml(tmp_path / "unsafe-disabled.yaml", {"version": 2, "sources": {"los": source}})

    with pytest.raises(CaseIntakeConfigError, match="must use preassessment_only with shadow"):
        load_case_intake_config(path)


def test_invalid_case_config_stops_before_cleanup_and_boot(monkeypatch, tmp_path: Path):
    """Independent startup-order proof: static config failure permits only runtime-security."""
    from app import reason_taxonomy, runtime_security
    from app.orch import main_session

    unsafe = {"version": 2, "sources": {"los": _source()}}
    unsafe["sources"]["los"].pop("tenant_slug")
    monkeypatch.setenv("SHB_CASE_INTAKE_CONFIG", str(_write_yaml(tmp_path / "unsafe.yaml", unsafe)))
    seen: list[str] = []
    monkeypatch.setattr(runtime_security, "validate_runtime_security", lambda: seen.append("security"))
    monkeypatch.setattr(reason_taxonomy, "activate_reason_taxonomy", lambda: seen.append("taxonomy"))
    monkeypatch.setattr(registry, "reset_all", lambda: seen.append("registry"))
    monkeypatch.setattr(store, "cleanup_orphans", AsyncMock(side_effect=lambda _: seen.append("cleanup")))
    monkeypatch.setattr(main_session, "boot", lambda: seen.append("boot"))

    with pytest.raises(CaseIntakeConfigError), TestClient(app):
        pass

    assert seen == ["security"]


@requires_db
def test_equal_source_version_with_different_raw_content_conflicts_before_rfi_normalization():
    """Unknown field names may collapse for RFI, but source-version content identity stays raw."""
    case_id = f"LOS-T1-{uuid4()}"
    first_id, second_id = f"evt-{uuid4()}", f"evt-{uuid4()}"
    try:
        first = ingest_case_event(
            _event(case_id, first_id, version=7, missing=["raw-secret-a"]),
            tenant_slug="bank-digital-default",
            shadow=True,
        )
        assert first.receipt["status"] == "accepted"
        assert first.rfi_candidate is not None
        assert first.rfi_candidate.missing_fields == ("additional_information",)

        with pytest.raises(ApiError) as caught:
            ingest_case_event(
                _event(case_id, second_id, version=7, missing=["raw-secret-b"]),
                tenant_slug="bank-digital-default",
                shadow=True,
            )

        assert caught.value.status_code == 409
        assert caught.value.detail["code"] == "source_version_conflict"
        assert set(caught.value.detail) == {"code", "message", "hint", "retryable"}
    finally:
        _cleanup_case(case_id)


@pytest.mark.asyncio
async def test_memo_overwrites_forged_taxonomy_and_unknown_code_has_zero_db_sse(monkeypatch):
    """The model never owns taxonomy proof; an invalid id cannot reach persistence or emission."""
    captured: list[dict] = []
    emitted: list[tuple] = []

    async def insert(_conv_id, _task_id, _card_type, data):
        captured.append(data)
        return {"id": "tester-card", "conv_id": "tester-conv", "type": "document", "data": data}

    monkeypatch.setattr(store, "insert_card", insert)
    monkeypatch.setattr("app.sse.emit.emit", lambda *args: emitted.append(args))
    registry.CTX_CONV.set("tester-conv")
    registry.CTX_TASK.set("")

    valid = _memo(["HS_THIEU_DINH_DANH_NOI_BO"])
    assert _tool_payload(await present_tool.handler(valid))["rendered"] is True
    assert captured[0]["items"][4]["reason_taxonomy"] == get_reason_taxonomy().proof()
    assert captured[0]["items"][4]["reason_taxonomy"] != {"version": 999, "checksum": "model-forged"}
    assert len(emitted) == 1

    captured.clear()
    emitted.clear()
    invalid = _memo(["MODEL_INVENTED_REASON"])
    payload = _tool_payload(await present_tool.handler(invalid))
    assert payload["code"] == "invalid_credit_memo"
    assert payload["retryable"] is True
    assert set(payload) == {"code", "message", "hint", "retryable"}
    assert captured == []
    assert emitted == []


@pytest.mark.asyncio
async def test_rfi_collapses_all_cic_input_and_emits_exact_two_safe_keys(monkeypatch):
    """D-83 forbids even a CIC-consent field name from crossing the webhook boundary."""
    from app.notify import channels

    captured: list[dict] = []

    async def deliver(_url, _channel, _event, body):
        captured.append(body)

    monkeypatch.setenv("SHB_NOTIFY_WEBHOOK_URL", "https://hooks.example/tester1")
    monkeypatch.setenv("SHB_NOTIFY_CHANNEL", "generic")
    monkeypatch.setattr(channels, "app_url", lambda: "https://bank.example")
    monkeypatch.setattr(channels, "_deliver_guarded", deliver)
    case_id = str(uuid4())
    fields = ["cic_consent", "CIC score 700", "identity_document"]

    assert normalize_missing_fields(fields) == ["additional_information", "identity_document"]
    channels.notify_channel_case_rfi(case_id, fields)
    await asyncio.gather(*tuple(channels._bg_tasks))

    assert captured == [
        {
            "missing_fields": ["additional_information", "identity_document"],
            "deep_link": f"https://bank.example/?tab=cases&case={case_id}",
        }
    ]
    assert "cic" not in json.dumps(captured, ensure_ascii=False).lower()


@requires_db
def test_linked_conversation_cannot_be_started_by_non_admin(monkeypatch):
    """A NULL-owner intake conversation is operable only by a same-tenant admin."""
    from app.orch import room

    case_id = f"LOS-T1-{uuid4()}"
    result = ingest_case_event(
        _event(case_id, f"evt-{uuid4()}", version=1, missing=[]),
        tenant_slug="bank-digital-default",
        shadow=True,
    )
    conversation_id = result.receipt["conversation_id"]
    wake = AsyncMock()
    monkeypatch.setattr(room, "handle_room_event", wake)
    try:
        client = TestClient(app)
        for role in ("user", "customer"):
            token = make_token(
                user_id=str(uuid4()),
                username=f"tester1-{role}-{uuid4()}",
                role=role,
                tenant_id=DEFAULT_TENANT_ID,
            )
            response = client.post(
                f"/api/conversations/{conversation_id}/chat",
                headers={"Authorization": f"Bearer {token}"},
                json={"content": "start without admin"},
            )
            assert response.status_code == 404
            assert response.json()["code"] == "not_found"

        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM messages WHERE conv_id=%s", (conversation_id,))
                assert cur.fetchone()[0] == 0
        finally:
            conn.close()
        wake.assert_not_awaited()
    finally:
        _cleanup_case(case_id)
