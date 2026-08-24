"""Atomic D-77 ingestion; deliberately contains no orchestrator or tool imports."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import psycopg2.extras

from app.case_intake.schemas import CaseEventReceipt, CaseEventV1, CaseStatus
from app.errors import ApiError
from app.storage import connect_core


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _case_status(event: CaseEventV1) -> CaseStatus:
    if event.event_type == "case.cancelled":
        return "cancelled"
    if event.case.missing_fields:
        return "missing_information"
    if event.event_type == "case.preassessment_requested":
        return "ready_for_preassessment"
    return "received"


def _receipt(event: CaseEventV1, row: dict[str, Any], status: str) -> dict[str, Any]:
    return CaseEventReceipt(
        id=str(row["id"]),
        event_id=event.event_id,
        status=status,
        source_system=event.source_system,
        external_case_id=event.case.external_case_id,
        source_version=event.source_version,
        case_status=row["case_status"],
        conversation_id=str(row["conversation_id"]) if row.get("conversation_id") else None,
    ).model_dump()


def _insert_inbox(
    cur: Any, event: CaseEventV1, payload: dict[str, Any], payload_hash: str, receipt: dict[str, Any]
) -> None:
    cur.execute(
        "INSERT INTO integration_inbox "
        "(source_system,event_id,event_type,schema_version,external_case_id,source_version,"
        "payload,payload_hash,receipt) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            event.source_system,
            event.event_id,
            event.event_type,
            event.schema_version,
            event.case.external_case_id,
            event.source_version,
            json.dumps(payload, ensure_ascii=False),
            payload_hash,
            json.dumps(receipt, ensure_ascii=False),
        ),
    )


def _create_conversation(cur: Any) -> str:
    cur.execute(
        "INSERT INTO conversations (user_id,title,status,created_at) VALUES (NULL,%s,'idle',now()) RETURNING id",
        ("Phiên xử lý sơ thẩm",),
    )
    return str(cur.fetchone()["id"])


def ingest_case_event(event: CaseEventV1, *, shadow: bool) -> dict[str, Any]:
    """Persist inbox, case link and optional linked conversation in one transaction.

    P0 stops at durable state. It never wakes MAIN, mounts a tool, creates an approval or executes
    a payment; the import boundary above makes that property reviewable.
    """
    payload = event.model_dump(mode="json")
    payload_hash = _hash(payload)
    content_hash = _hash({"event_type": event.event_type, "case": payload["case"]})
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Khoá event trước, case sau trên mọi request: vừa đóng race cùng event xuyên hai case,
            # vừa giữ thứ tự lock cố định để tránh deadlock khi nhiều version tới đồng thời.
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"event:{event.source_system}:{event.event_id}",),
            )
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"case:{event.source_system}:{event.case.external_case_id}",),
            )
            cur.execute(
                "SELECT payload_hash,receipt FROM integration_inbox WHERE source_system=%s AND event_id=%s",
                (event.source_system, event.event_id),
            )
            duplicate = cur.fetchone()
            if duplicate:
                if duplicate["payload_hash"] != payload_hash:
                    raise ApiError(
                        409,
                        "idempotency_conflict",
                        "Idempotency-Key đã được dùng cho payload khác.",
                        "Dùng lại đúng payload cũ hoặc phát event_id mới.",
                        retryable=False,
                    )
                prior = dict(duplicate["receipt"])
                prior["status"] = "duplicate"
                conn.commit()
                return prior

            cur.execute(
                "SELECT * FROM external_case_links WHERE source_system=%s AND external_case_id=%s FOR UPDATE",
                (event.source_system, event.case.external_case_id),
            )
            current = cur.fetchone()
            if current and event.source_version < current["source_version"]:
                receipt = _receipt(event, dict(current), "stale_ignored")
                _insert_inbox(cur, event, payload, payload_hash, receipt)
                conn.commit()
                return receipt
            if current and event.source_version == current["source_version"]:
                if current["content_hash"] != content_hash:
                    raise ApiError(
                        409,
                        "source_version_conflict",
                        "source_version hiện tại có nội dung khác.",
                        "Tăng source_version cho thay đổi mới.",
                        retryable=False,
                    )
                receipt = _receipt(event, dict(current), "duplicate")
                _insert_inbox(cur, event, payload, payload_hash, receipt)
                conn.commit()
                return receipt

            if current and (event.event_type == "case.snapshot_upserted" or current["case_status"] == "cancelled"):
                status = current["case_status"]
            else:
                status = _case_status(event)
            conversation_id = str(current["conversation_id"]) if current and current.get("conversation_id") else None
            # D-77 P0 không có sự kiện reopen: case đã huỷ phải dừng hẳn, kể cả khi LOS
            # gửi pre-assessment version mới đến muộn.
            if (
                event.event_type == "case.preassessment_requested"
                and shadow
                and status != "cancelled"
                and conversation_id is None
            ):
                conversation_id = _create_conversation(cur)
            case = event.case
            if current:
                cur.execute(
                    "UPDATE external_case_links SET party_reference=%s,assigned_rm_subject=%s,product_code=%s,"
                    "loan_amount_vnd=%s,document_refs=%s,missing_fields=%s,source_version=%s,content_hash=%s,"
                    "case_status=%s,data_as_of=%s,conversation_id=%s,synced_at=now() WHERE id=%s RETURNING *",
                    (
                        case.external_party_id,
                        case.assigned_rm_subject,
                        case.product_code,
                        case.loan_amount_vnd,
                        json.dumps(case.document_refs),
                        json.dumps(case.missing_fields),
                        event.source_version,
                        content_hash,
                        status,
                        event.occurred_at,
                        conversation_id,
                        current["id"],
                    ),
                )
            else:
                cur.execute(
                    "INSERT INTO external_case_links "
                    "(source_system,external_case_id,party_reference,assigned_rm_subject,product_code,loan_amount_vnd,"
                    "document_refs,missing_fields,source_version,content_hash,case_status,data_as_of,conversation_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                    (
                        event.source_system,
                        case.external_case_id,
                        case.external_party_id,
                        case.assigned_rm_subject,
                        case.product_code,
                        case.loan_amount_vnd,
                        json.dumps(case.document_refs),
                        json.dumps(case.missing_fields),
                        event.source_version,
                        content_hash,
                        status,
                        event.occurred_at,
                        conversation_id,
                    ),
                )
            link = dict(cur.fetchone())
            receipt = _receipt(event, link, "accepted")
            _insert_inbox(cur, event, payload, payload_hash, receipt)
        conn.commit()
        return receipt
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
