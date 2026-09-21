from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest
from fastapi.testclient import TestClient

from app import consent
from app.api import form_intake
from app.db.config import DATABASE_URL
from app.main import app
from app.tenancy import DEFAULT_TENANT_ID

from .conftest import requires_db
from .test_signup_intake_t91 import (
    _GOOD_VALUES,
    _mk_form_card,
    _register_and_conv,
    _rm_user,
    client,
)


def _wording_bytes(content: bytes, *, purpose: str = consent.PURPOSE) -> bytes:
    return (
        b"---\nversion: v1\npurpose: "
        + purpose.encode("utf-8")
        + b"\nreview_status: pending_bank_approval\napproved_for_real_data: false\n---\n"
        + content
    )


def test_wording_v1_snapshot_and_exact_checksum():
    wording = consent.load_wording()
    content_bytes = wording.content_markdown.encode("utf-8")
    assert wording.version == "v1"
    assert wording.purpose == consent.PURPOSE
    assert wording.review_status == "pending_bank_approval"
    assert wording.approved_for_real_data is False
    assert wording.checksum == hashlib.sha256(content_bytes).hexdigest()
    assert wording.snapshot() == {
        "required": True,
        "purpose": consent.PURPOSE,
        "wording_version": "v1",
        "wording_checksum": wording.checksum,
        "content_markdown": wording.content_markdown,
    }
    assert "DPIA" in wording.content_markdown
    assert "shadow" in wording.content_markdown


def test_wording_checksum_changes_when_one_content_byte_changes(tmp_path: Path):
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_bytes(_wording_bytes(b"Content A\n"))
    second.write_bytes(_wording_bytes(b"Content B\n"))
    assert consent.load_wording(first).checksum != consent.load_wording(second).checksum


@pytest.mark.parametrize(
    "raw",
    [
        b"not-front-matter",
        _wording_bytes(b"content\n", purpose="unknown_purpose"),
        b"---\nversion: V1\npurpose: pre_pilot_shadow_preassessment\n"
        b"review_status: approved\napproved_for_real_data: false\n---\ncontent\n",
        b"---\nversion: v1\npurpose: pre_pilot_shadow_preassessment\n"
        b"review_status: invented\napproved_for_real_data: false\n---\ncontent\n",
    ],
)
def test_wording_malformed_or_unknown_metadata_fails_closed(tmp_path: Path, raw: bytes):
    path = tmp_path / "bad.md"
    path.write_bytes(raw)
    with pytest.raises(consent.ConsentWordingError):
        consent.load_wording(path)


def test_consent_has_no_reset_or_mutation_path_in_production_source():
    app_root = Path(__file__).resolve().parents[1] / "app"
    reset_source = (app_root / "db" / "reset_demo.py").read_text(encoding="utf-8")
    assert "consent_records" not in reset_source
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in app_root.rglob("*.py")
        if "migrations/versions" not in path.as_posix()
    )
    assert "UPDATE consent_records" not in source
    assert "DELETE FROM consent_records" not in source
    assert source.count("INSERT INTO consent_records") == 1


def _raw_submit(conv: str, card_id: str, cookies: dict, **extra):
    payload = {"card_id": card_id, "values": _GOOD_VALUES, **extra}
    return client.post(f"/api/conversations/{conv}/form-submit", cookies=cookies, json=payload)


def _form_state(username: str, card_id: str) -> tuple[str | None, str, int]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT owner_id FROM users WHERE username=%s", (username,))
            owner_id = cur.fetchone()[0]
            cur.execute("SELECT data->>'status' FROM cards WHERE id=%s", (card_id,))
            status = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM consent_records WHERE source_ref=%s", (card_id,))
            count = cur.fetchone()[0]
        return owner_id, status, count
    finally:
        conn.close()


@requires_db
@pytest.mark.parametrize("grant", [None, False])
def test_missing_or_false_consent_is_four_field_zero_write(grant):
    username, cookies, conv = _register_and_conv()
    try:
        card_id = _mk_form_card(conv)
        extra = {} if grant is None else {"consent_granted": grant}
        response = _raw_submit(conv, card_id, cookies, **extra)
        assert response.status_code == 400
        assert response.json() == {
            "code": "consent_required",
            "message": "Consent to data processing is required before submitting the application.",
            "hint": "Read the form wording and select the consent checkbox if you agree.",
            "retryable": True,
        }
        assert _form_state(username, card_id) == (None, "pending", 0)
    finally:
        _rm_user(username)


@requires_db
def test_legacy_form_without_snapshot_fails_closed_409():
    username, cookies, conv = _register_and_conv()
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cards(conv_id,type,data,ts) VALUES(%s,'form',%s,now()) RETURNING id::text",
                (conv, psycopg2.extras.Json({"type": "form", "status": "pending"})),
            )
            card_id = cur.fetchone()[0]
        response = _raw_submit(conv, card_id, cookies, consent_granted=True)
        assert response.status_code == 409
        assert set(response.json()) == {"code", "message", "hint", "retryable"}
        assert response.json()["code"] == "consent_wording_unavailable"
        assert _form_state(username, card_id) == (None, "pending", 0)
    finally:
        conn.close()
        _rm_user(username)


@requires_db
def test_client_cannot_override_server_owned_consent_metadata():
    username, cookies, conv = _register_and_conv()
    try:
        card_id = _mk_form_card(conv)
        response = _raw_submit(
            conv,
            card_id,
            cookies,
            consent_granted=True,
            wording_version="v999",
            wording_checksum="0" * 64,
            tenant_id=str(uuid.uuid4()),
        )
        assert response.status_code == 400
        assert response.json()["code"] == "bad_request"
        assert _form_state(username, card_id) == (None, "pending", 0)
    finally:
        _rm_user(username)


@requires_db
def test_form_submit_is_customer_only_even_when_admin_can_access_conversation():
    username, _customer_cookies, conv = _register_and_conv()
    try:
        card_id = _mk_form_card(conv)
        for account in ("user", "admin"):
            login = client.post("/api/auth/login", json={"username": account, "password": account})
            assert login.status_code == 200
            response = _raw_submit(conv, card_id, login.cookies, consent_granted=True)
            assert response.status_code == 403
            assert response.json()["code"] == "forbidden"
        anonymous = TestClient(app).post(
            f"/api/conversations/{conv}/form-submit",
            json={"card_id": card_id, "values": _GOOD_VALUES, "consent_granted": True},
        )
        assert anonymous.status_code == 401
        assert _form_state(username, card_id) == (None, "pending", 0)
    finally:
        _rm_user(username)


@requires_db
def test_consent_insert_failure_rolls_back_card_customer_and_user(monkeypatch):
    username, cookies, conv = _register_and_conv()
    card_id = _mk_form_card(conv)
    original = consent.insert_record

    async def no_wake(*_args, **_kwargs):
        return None

    def fail_insert(*_args, **_kwargs):
        raise RuntimeError("forced consent insert failure")

    monkeypatch.setattr(form_intake, "_wake_main", no_wake)
    monkeypatch.setattr(consent, "insert_record", fail_insert)
    try:
        with pytest.raises(RuntimeError, match="forced consent"):
            _raw_submit(conv, card_id, cookies, consent_granted=True)
        assert _form_state(username, card_id) == (None, "pending", 0)

        monkeypatch.setattr(consent, "insert_record", original)
        retry = _raw_submit(conv, card_id, cookies, consent_granted=True)
        assert retry.status_code == 200
        owner_id, status, count = _form_state(username, card_id)
        assert owner_id == retry.json()["owner_id"]
        assert status == "submitted"
        assert count == 1
    finally:
        _rm_user(username)


@requires_db
def test_consent_record_uses_jwt_tenant_subject_and_card_snapshot(monkeypatch):
    username, cookies, conv = _register_and_conv()

    async def no_wake(*_args, **_kwargs):
        return None

    monkeypatch.setattr(form_intake, "_wake_main", no_wake)
    try:
        card_id = _mk_form_card(conv)
        response = _raw_submit(conv, card_id, cookies, consent_granted=True)
        assert response.status_code == 200
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT id::text,tenant_id::text FROM users WHERE username=%s", (username,))
                user = cur.fetchone()
                cur.execute("SELECT data->'consent' AS snapshot FROM cards WHERE id=%s", (card_id,))
                snapshot = cur.fetchone()["snapshot"]
                cur.execute("SELECT * FROM consent_records WHERE source_ref=%s", (card_id,))
                row = cur.fetchone()
        finally:
            conn.close()
        assert str(row["tenant_id"]) == user["tenant_id"]
        assert row["subject_type"] == "user"
        assert row["subject_ref"] == user["id"] == row["actor"]
        assert row["purpose"] == consent.PURPOSE
        assert row["wording_version"] == snapshot["wording_version"] == "v1"
        assert row["wording_checksum"] == snapshot["wording_checksum"] == consent.load_wording().checksum
        assert row["granted"] is True
        assert row["granted_at"] is not None and row["recorded_at"] is not None
        assert row["source"] == "customer_form" and row["source_ref"] == card_id
    finally:
        _rm_user(username)


def _consent_values(**overrides):
    values = {
        "tenant_id": DEFAULT_TENANT_ID,
        "subject_type": "user",
        "subject_ref": str(uuid.uuid4()),
        "purpose": consent.PURPOSE,
        "wording_version": "v1",
        "wording_checksum": "a" * 64,
        "granted": True,
        "granted_at": "now()",
        "actor": str(uuid.uuid4()),
        "source": "customer_form",
        "source_ref": str(uuid.uuid4()),
    }
    values.update(overrides)
    return values


def _insert_consent(cur, values):
    granted_at = values.pop("granted_at")
    cur.execute(
        "INSERT INTO consent_records(tenant_id,subject_type,subject_ref,purpose,wording_version,"
        "wording_checksum,granted,granted_at,actor,source,source_ref) "
        f"VALUES(%s,%s,%s,%s,%s,%s,%s,{granted_at},%s,%s,%s) RETURNING id",
        tuple(values[key] for key in values),
    )
    return cur.fetchone()[0]


@requires_db
def test_db_trigger_rejects_update_and_delete_without_committing_fixture():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            record_id = _insert_consent(cur, _consent_values())
            cur.execute("SAVEPOINT before_update")
            with pytest.raises(psycopg2.Error):
                cur.execute("UPDATE consent_records SET actor='changed' WHERE id=%s", (record_id,))
            cur.execute("ROLLBACK TO SAVEPOINT before_update")
            cur.execute("SAVEPOINT before_delete")
            with pytest.raises(psycopg2.Error):
                cur.execute("DELETE FROM consent_records WHERE id=%s", (record_id,))
            cur.execute("ROLLBACK TO SAVEPOINT before_delete")
    finally:
        conn.rollback()
        conn.close()


@requires_db
@pytest.mark.parametrize(
    "overrides",
    [
        {"tenant_id": str(uuid.uuid4())},
        {"subject_type": "device"},
        {"subject_ref": " "},
        {"purpose": "unknown"},
        {"wording_version": "V1"},
        {"wording_checksum": "A" * 64},
        {"granted": True, "granted_at": "NULL"},
        {"granted": False, "granted_at": "now()"},
        {"actor": " "},
        {"source": "unknown"},
        {"source_ref": " "},
    ],
)
def test_db_constraints_reject_invalid_consent(overrides):
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur, pytest.raises(psycopg2.Error):
            _insert_consent(cur, _consent_values(**overrides))
    finally:
        conn.rollback()
        conn.close()
