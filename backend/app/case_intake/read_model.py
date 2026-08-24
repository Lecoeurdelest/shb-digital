"""Admin case summary read-model merging D-77 links and legacy demo applications."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import psycopg2.extras

from app.storage import connect_core
from app.tenancy import DEFAULT_TENANT_ID

_NEXT_ACTION = {
    "received": "Kiểm tra thông tin hồ sơ",
    "missing_information": "Bổ sung thông tin còn thiếu",
    "ready_for_preassessment": "Bắt đầu sơ thẩm",
    "preassessment_in_progress": "Theo dõi kết quả sơ thẩm",
    "needs_specialist": "Chuyển chuyên gia nghiệp vụ",
    "ready_for_handover": "Bàn giao bước tiếp theo",
    "cancelled": "Không cần xử lý",
}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _external_summary(row: dict[str, Any]) -> dict[str, Any]:
    status = row["case_status"]
    return {
        "id": str(row["id"]),
        "source_system": row["source_system"],
        "external_case_id": row["external_case_id"],
        "internal_application_id": row["internal_application_id"],
        "party_reference": row["party_reference"],
        "product_code": row["product_code"],
        "loan_amount_vnd": row["loan_amount_vnd"],
        "case_status": status,
        "next_action": _NEXT_ACTION[status],
        "document_count": len(row["document_refs"] or []),
        "missing_fields": row["missing_fields"] or [],
        "source_version": row["source_version"],
        "data_as_of": _iso(row["data_as_of"]),
        "synced_at": _iso(row["synced_at"]),
        "conversation_id": str(row["conversation_id"]) if row["conversation_id"] else None,
        "assessment": {"lane": row["lane"], "created_at": _iso(row["assessment_created_at"])},
    }


def _legacy_status(raw: str | None) -> str:
    if raw in {"ready_to_disburse", "disbursed"}:
        return "ready_for_handover"
    if raw == "reviewing":
        return "ready_for_preassessment"
    return "needs_specialist"


def _legacy_summary(row: dict[str, Any]) -> dict[str, Any]:
    status = _legacy_status(row["status"])
    created_at = row.get("created_at")
    data_as_of = None
    if created_at:
        rendered = str(created_at)
        data_as_of = rendered if "T" in rendered else f"{rendered}T00:00:00+00:00"
    next_action = {
        "disbursed": "Kiểm tra biên nhận",
        "ready_to_disburse": "Bàn giao vận hành",
        "approved_pending_procedures": "Hoàn tất thủ tục",
        "rejected": "Kiểm tra kết quả thẩm định",
    }.get(row["status"], "Tiếp tục kiểm tra hồ sơ")
    return {
        "id": f"internal_operations:{row['id']}",
        "source_system": "internal_operations",
        "external_case_id": row["id"],
        "internal_application_id": row["id"],
        "party_reference": row["owner_id"],
        "product_code": row["product_id"],
        "loan_amount_vnd": row["loan_amount_vnd"],
        "case_status": status,
        "next_action": next_action,
        "document_count": 0,
        "missing_fields": [],
        "source_version": None,
        "data_as_of": data_as_of,
        "synced_at": data_as_of or datetime.fromtimestamp(0, UTC).isoformat(),
        "conversation_id": None,
        "assessment": {"lane": row["lane"], "created_at": row["assessment_created_at"]},
    }


def list_cases(
    *,
    status: str | None,
    source: str | None,
    limit: int,
    tenant_id: str,
) -> list[dict[str, Any]]:
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            external: list[dict[str, Any]] = []
            if source in {None, ""} or source != "internal_operations":
                clauses: list[str] = ["e.tenant_id=%s"]
                params: list[Any] = [tenant_id]
                if source:
                    clauses.append("e.source_system=%s")
                    params.append(source)
                if status:
                    clauses.append("e.case_status=%s")
                    params.append(status)
                where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
                cur.execute(
                    "SELECT e.*,a.lane,a.created_at AS assessment_created_at FROM external_case_links e "
                    "LEFT JOIN applications p ON p.id=e.internal_application_id "
                    "LEFT JOIN LATERAL (SELECT lane,created_at FROM assessments "
                    "WHERE tenant_id=e.tenant_id AND owner_id=p.owner_id ORDER BY id DESC LIMIT 1) a ON true "
                    f"{where} ORDER BY e.synced_at DESC LIMIT %s",
                    (*params, limit),
                )
                external = [_external_summary(dict(row)) for row in cur.fetchall()]
            legacy: list[dict[str, Any]] = []
            # Legacy applications là dữ liệu demo chung trước D-79; chỉ tenant mặc định được thấy.
            if source in {None, "", "internal_operations"} and tenant_id == DEFAULT_TENANT_ID:
                cur.execute(
                    "SELECT p.*,a.lane,a.created_at AS assessment_created_at FROM applications p "
                    "LEFT JOIN LATERAL (SELECT lane,created_at FROM assessments "
                    "WHERE tenant_id=%s AND owner_id=p.owner_id ORDER BY id DESC LIMIT 1) a ON true",
                    (DEFAULT_TENANT_ID,),
                )
                legacy = [_legacy_summary(dict(row)) for row in cur.fetchall()]
                if status:
                    legacy = [row for row in legacy if row["case_status"] == status]
        merged = external + legacy
        merged.sort(key=lambda row: row["synced_at"] or "", reverse=True)
        return merged[:limit]
    finally:
        conn.close()


def get_case(case_id: str, *, tenant_id: str) -> dict[str, Any] | None:
    """Return one external case in the authenticated tenant; absence and cross-tenant are identical."""
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT e.*,a.lane,a.created_at AS assessment_created_at FROM external_case_links e "
                "LEFT JOIN applications p ON p.id=e.internal_application_id "
                "LEFT JOIN LATERAL (SELECT lane,created_at FROM assessments "
                "WHERE tenant_id=e.tenant_id AND owner_id=p.owner_id ORDER BY id DESC LIMIT 1) a ON true "
                "WHERE e.tenant_id=%s AND e.id=%s",
                (tenant_id, case_id),
            )
            row = cur.fetchone()
            return _external_summary(dict(row)) if row is not None else None
    finally:
        conn.close()
