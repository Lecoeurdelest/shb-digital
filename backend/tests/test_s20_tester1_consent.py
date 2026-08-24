"""Independent T20-5 adversarial consent/DB gate owned by tester-1."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import psycopg2
import psycopg2.extras
import pytest
from fastapi.testclient import TestClient

from app import consent
from app.api import form_intake
from app.auth.security import make_token
from app.db.config import DATABASE_URL
from app.main import app
from app.tenancy import DEFAULT_TENANT_ID

from .conftest import requires_db, requires_test_db

client = TestClient(app)
_GOOD_VALUES = {
    "full_name": "Khach T20 Tester 1",
    "id_number": "T20-TESTER-1",
    "address": "Dia chi test",
    "occupation": "Kiem thu",
    "monthly_income": "25000000",
    "loan_purpose": "kiem thu atomicity",
}


def _headers(case: dict[str, str]) -> dict[str, str]:
    token = make_token(
        user_id=case["user_id"],
        username=case["username"],
        role="customer",
        tenant_id=DEFAULT_TENANT_ID,
    )
    return {"Authorization": f"Bearer {token}"}


def _assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert set(response.json()) == {"code", "message", "hint", "retryable"}
    assert response.json()["code"] == code


def _seed_form(*, consent_data: dict | None = None) -> dict[str, str]:
    marker = uuid4().hex
    case = {
        "user_id": str(uuid4()),
        "conv_id": str(uuid4()),
        "card_id": str(uuid4()),
        "username": f"t20_tester1_{marker[:12]}",
        "marker": marker,
    }
    data = {"type": "form", "fields": [], "status": "pending"}
    if consent_data is not None:
        data["consent"] = consent_data
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users(id,tenant_id,username,pass_hash,role,owner_id) VALUES(%s,%s,%s,'x','customer',NULL)",
            (case["user_id"], DEFAULT_TENANT_ID, case["username"]),
        )
        cur.execute(
            "INSERT INTO conversations(id,tenant_id,user_id,title,status,created_at) "
            "VALUES(%s,%s,%s,'T20 consent','idle',now())",
            (case["conv_id"], DEFAULT_TENANT_ID, case["username"]),
        )
        cur.execute(
            "INSERT INTO cards(id,tenant_id,conv_id,type,data,ts) VALUES(%s,%s,%s,'form',%s,now())",
            (
                case["card_id"],
                DEFAULT_TENANT_ID,
                case["conv_id"],
                psycopg2.extras.Json(data),
            ),
        )
    conn.close()
    return case


def _form_state(case: dict[str, str]) -> tuple[str, str | None, int, int]:
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("SELECT data->>'status' FROM cards WHERE id=%s", (case["card_id"],))
        status = cur.fetchone()[0]
        cur.execute("SELECT owner_id FROM users WHERE id=%s", (case["user_id"],))
        owner_id = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM customers WHERE id_number=%s",
            (_GOOD_VALUES["id_number"] + case["marker"],),
        )
        customer_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM consent_records WHERE source_ref=%s", (case["card_id"],))
        consent_count = cur.fetchone()[0]
    conn.close()
    return status, owner_id, customer_count, consent_count


def _cleanup_form(case: dict[str, str]) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT owner_id FROM users WHERE id=%s", (case["user_id"],))
        row = cur.fetchone()
        owner_id = row[0] if row else None
        cur.execute("DELETE FROM cards WHERE conv_id=%s", (case["conv_id"],))
        cur.execute("DELETE FROM conversations WHERE id=%s", (case["conv_id"],))
        cur.execute("DELETE FROM users WHERE id=%s", (case["user_id"],))
        if owner_id:
            cur.execute("DELETE FROM customers WHERE id=%s", (owner_id,))
    conn.close()


def _submit(case: dict[str, str], *, granted=True, extras: dict | None = None):
    values = {**_GOOD_VALUES, "id_number": _GOOD_VALUES["id_number"] + case["marker"]}
    body = {
        "card_id": case["card_id"],
        "values": values,
        **(extras or {}),
    }
    if granted is not None:
        body["consent_granted"] = granted
    return client.post(
        f"/api/conversations/{case['conv_id']}/form-submit",
        headers=_headers(case),
        json=body,
    )


@requires_test_db
def test_tester1_form_fail_closed_atomic_retry_and_double_submit(monkeypatch):
    wording = consent.load_wording()
    no_consent = _seed_form(consent_data=wording.snapshot())
    legacy = _seed_form()
    tampered = wording.snapshot()
    tampered["content_markdown"] += "tamper"
    broken = _seed_form(consent_data=tampered)
    rollback_case = _seed_form(consent_data=wording.snapshot())

    async def no_wake(*_args, **_kwargs):
        return None

    monkeypatch.setattr(form_intake, "_wake_main", no_wake)
    try:
        for granted in (None, False):
            _assert_error(_submit(no_consent, granted=granted), 400, "consent_required")
            assert _form_state(no_consent) == ("pending", None, 0, 0)

        _assert_error(_submit(legacy), 409, "consent_wording_unavailable")
        assert _form_state(legacy) == ("pending", None, 0, 0)
        _assert_error(_submit(broken), 400, "consent_wording_invalid")
        assert _form_state(broken) == ("pending", None, 0, 0)

        _assert_error(
            _submit(
                no_consent,
                extras={
                    "wording_version": "v999",
                    "tenant_id": str(uuid4()),
                    "actor": "attacker",
                },
            ),
            400,
            "bad_request",
        )
        assert _form_state(no_consent) == ("pending", None, 0, 0)

        real_insert = consent.insert_record

        def fail_insert(*_args, **_kwargs):
            raise RuntimeError("tester-1 forced consent failure")

        monkeypatch.setattr(consent, "insert_record", fail_insert)
        with pytest.raises(RuntimeError, match="forced consent failure"):
            form_intake._submit_txn(
                rollback_case["conv_id"],
                rollback_case["user_id"],
                DEFAULT_TENANT_ID,
                rollback_case["card_id"],
                {**_GOOD_VALUES, "id_number": _GOOD_VALUES["id_number"] + rollback_case["marker"]},
                25_000_000,
                wording,
            )
        assert _form_state(rollback_case) == ("pending", None, 0, 0)

        monkeypatch.setattr(consent, "insert_record", real_insert)
        success = _submit(rollback_case)
        assert success.status_code == 200, success.text
        status, owner_id, customer_count, consent_count = _form_state(rollback_case)
        assert status == "submitted" and owner_id and customer_count == consent_count == 1
        _assert_error(_submit(rollback_case), 409, "form_already_submitted")
        assert _form_state(rollback_case)[2:] == (1, 1)

        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tenant_id::text,subject_type,subject_ref,purpose,wording_version,"
                "wording_checksum,granted,actor,source,source_ref FROM consent_records "
                "WHERE source_ref=%s",
                (rollback_case["card_id"],),
            )
            proof = cur.fetchone()
        conn.close()
        assert proof == (
            DEFAULT_TENANT_ID,
            "user",
            rollback_case["user_id"],
            consent.PURPOSE,
            "v1",
            wording.checksum,
            True,
            rollback_case["user_id"],
            "customer_form",
            rollback_case["card_id"],
        )
    finally:
        for case in (no_consent, legacy, broken, rollback_case):
            _cleanup_form(case)


@requires_db
def test_tester1_wording_checksum_and_fail_closed_parser(tmp_path: Path):
    canonical = consent.load_wording()
    raw = consent.DEFAULT_WORDING_PATH.read_bytes()
    changed_path = tmp_path / "changed.md"
    changed_path.write_bytes(raw + b"\n")
    changed = consent.load_wording(changed_path)
    assert changed.version == canonical.version == "v1"
    assert changed.checksum != canonical.checksum

    bad_path = tmp_path / "bad.md"
    bad_path.write_text(
        "---\nversion: v1\npurpose: invented\nreview_status: draft\napproved_for_real_data: false\n---\ntext",
        encoding="utf-8",
    )
    with pytest.raises(consent.ConsentWordingError, match="allowlisted"):
        consent.load_wording(bad_path)


@requires_test_db
def test_tester1_consent_constraints_unique_and_append_only_trigger():
    source_ref, checksum = str(uuid4()), "a" * 64
    insert = (
        "INSERT INTO consent_records(tenant_id,subject_type,subject_ref,purpose,wording_version,"
        "wording_checksum,granted,recorded_at,granted_at,actor,source,source_ref) "
        "VALUES(%s,%s,'subject','pre_pilot_shadow_preassessment','v1',%s,TRUE,now(),now(),"
        "'actor','customer_form',%s)"
    )
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(insert, (DEFAULT_TENANT_ID, "user", checksum, source_ref))
    conn.close()

    invalid = (
        (DEFAULT_TENANT_ID, "robot", checksum, str(uuid4())),
        (DEFAULT_TENANT_ID, "user", "bad-hash", str(uuid4())),
        (str(uuid4()), "user", checksum, str(uuid4())),
    )
    for params in invalid:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with pytest.raises(psycopg2.IntegrityError):
            with conn.cursor() as cur:
                cur.execute(insert, params)
        conn.close()

    for statement in (
        "UPDATE consent_records SET actor='changed' WHERE source_ref=%s",
        "DELETE FROM consent_records WHERE source_ref=%s",
    ):
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with pytest.raises(psycopg2.DatabaseError) as error:
            with conn.cursor() as cur:
                cur.execute(statement, (source_ref,))
        assert error.value.pgcode == "55000"
        conn.close()

    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM consent_records WHERE source_ref=%s", (source_ref,))
        assert cur.fetchone()[0] == 1
        with pytest.raises(psycopg2.IntegrityError):
            cur.execute(insert, (DEFAULT_TENANT_ID, "user", checksum, source_ref))
    conn.rollback()
    conn.close()


def test_tester1_static_ledgers_have_only_allowlisted_insert_seams():
    app_root = Path(__file__).resolve().parents[1] / "app"
    sources = {
        path: path.read_text(encoding="utf-8") for path in app_root.rglob("*.py") if "migrations" not in path.parts
    }
    shadow_inserts = [path for path, text in sources.items() if "INSERT INTO shadow_reviews" in text]
    consent_inserts = [path for path, text in sources.items() if "INSERT INTO consent_records" in text]
    assert shadow_inserts == [app_root / "orch" / "store_shadow.py"]
    assert consent_inserts == [app_root / "consent.py"]
    for text in sources.values():
        assert "UPDATE shadow_reviews" not in text
        assert "DELETE FROM shadow_reviews" not in text
        assert "UPDATE consent_records" not in text
        assert "DELETE FROM consent_records" not in text
    reset_source = (app_root / "db" / "reset_demo.py").read_text(encoding="utf-8")
    assert "consent_records" not in reset_source
