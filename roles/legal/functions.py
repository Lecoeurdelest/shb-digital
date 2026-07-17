"""roles/legal — labpack Legal (COPY từ LAB shb-digital-experts, KHÔNG sửa logic).

legal.py của mission shb-132 (D-08) + cụm SCHEMAS/REGISTRY/ANNOTATIONS (từ tools/server.py,
chỉ legal-pack: legal_check_docs, legal_check_compliance).

RANH GIỚI N1/D-27: TRÍ KHÔN LAB — vỏ KHÔNG sửa. conn do vỏ cấp = PGConnAdapter (D-27) giả lập
sqlite3.Connection. Logic dưới byte-identical bản LAB. Không import SDK/MCP.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rows(c: sqlite3.Connection, sql: str, args: tuple = ()) -> list[dict]:
    return [dict(r) for r in c.execute(sql, args).fetchall()]


def _one(c: sqlite3.Connection, sql: str, args: tuple) -> dict | None:
    r = c.execute(sql, args).fetchone()
    return dict(r) if r else None


def legal_check_docs(conn: sqlite3.Connection, owner_id: str, loan_type: str = "consumer",
                     collateral_id: str | None = None) -> dict[str, Any]:
    """Checklist giấy tờ 2 TẦNG (nhân thân owner + tài sản) + pháp lý tài sản. Server đối chiếu
    danh mục legal_requirements — verdict clear/needs_docs/blocked tính sẵn."""
    if loan_type not in ("consumer", "secured"):
        return {"code": "bad_enum", "message": f"loan_type '{loan_type}' không hợp lệ",
                "hint": "consumer | secured", "retryable": False, "asOf": _now()}
    ent = _one(conn, "SELECT id FROM customers WHERE id=?", (owner_id,)) or \
          _one(conn, "SELECT id FROM businesses WHERE id=?", (owner_id,))
    if not ent:
        return {"found": False, "asOf": _now(),
                "hint": f"Không có owner '{owner_id}'. Lấy id: cust_search(q=...)."}

    reqs = _rows(conn, "SELECT doc_code, doc_name, mandatory FROM legal_requirements WHERE loan_type=?",
                 (loan_type,))
    docs = {d["doc_code"]: d["status"] for d in
            _rows(conn, "SELECT doc_code, status FROM owner_documents WHERE owner_id=?", (owner_id,))}
    missing = [{"doc": r["doc_code"], "name": r["doc_name"],
                "why": docs.get(r["doc_code"], "missing"),
                "mandatory": bool(r["mandatory"])}
               for r in reqs if docs.get(r["doc_code"]) != "valid"]
    hard_missing = [m for m in missing if m["mandatory"]]

    legal_flags: list[str] = []
    col_info = None
    if collateral_id:
        col = _one(conn, "SELECT id, owner_id, docs_status FROM collaterals WHERE id=?", (collateral_id,))
        if not col:
            return {"found": False, "asOf": _now(),
                    "hint": f"Không có collateral '{collateral_id}'. Xem tài sản của owner trong cust_get."}
        if col["owner_id"] != owner_id:
            return {"found": False, "code": "collateral_owner_mismatch",
                    "message": f"{collateral_id} thuộc {col['owner_id']}, KHÔNG phải {owner_id}",
                    "hint": "Dùng tài sản của chính owner (cust_get).", "retryable": False, "asOf": _now()}
        cl = _one(conn, "SELECT dispute_status, zoning_status, note FROM collateral_legal "
                        "WHERE collateral_id=?", (collateral_id,))
        col_info = {"id": collateral_id, "docs_status": col["docs_status"], **(cl or {})}
        if col["docs_status"] != "complete":
            legal_flags.append(f"collateral_docs:{col['docs_status']}")
        if cl and cl["dispute_status"] == "disputed":
            legal_flags.append("collateral_disputed: tài sản ĐANG TRANH CHẤP — không nhận thế chấp")
        if cl and cl["zoning_status"] == "planning_zone":
            legal_flags.append("collateral_planning_zone: đất trong quy hoạch — cần thẩm định pháp lý bổ sung")

    blocked = any("disputed" in f for f in legal_flags)
    verdict = "blocked" if blocked else ("needs_docs" if (hard_missing or legal_flags) else "clear")
    return {
        "found": True, "asOf": _now(),
        "item": {"ownerId": owner_id, "loanType": loan_type, "verdict": verdict,
                 "docChecklist": {"required": [r["doc_code"] for r in reqs],
                                  "missing": missing},
                 "collateral": col_info, "legalFlags": legal_flags, "computedBy": "server"},
        "hint": ("Verdict pháp-lý do server đối chiếu danh mục — trích thẳng. Đây KHÔNG phải "
                 "duyệt vay: khả-năng-trả là việc Credit (credit_assess), verdict tổng là của "
                 "điều phối. Mục đích vay hợp pháp? → legal_check_compliance."),
    }


def legal_check_compliance(conn: sqlite3.Connection, owner_id: str, purpose_code: str) -> dict[str, Any]:
    """Mục đích vay có bị cấm/điều-kiện không — server tra restricted_purposes."""
    ent = _one(conn, "SELECT id FROM customers WHERE id=?", (owner_id,)) or \
          _one(conn, "SELECT id FROM businesses WHERE id=?", (owner_id,))
    if not ent:
        return {"found": False, "asOf": _now(), "hint": f"Không có owner '{owner_id}'."}
    all_codes = [r["purpose_code"] for r in _rows(conn, "SELECT purpose_code FROM restricted_purposes")]
    rec = _one(conn, "SELECT purpose_code, purpose_name, restriction, legal_basis "
                     "FROM restricted_purposes WHERE purpose_code=?", (purpose_code,))
    if not rec:
        return {"found": True, "asOf": _now(),
                "item": {"ownerId": owner_id, "purposeCode": purpose_code, "restriction": "not_restricted",
                         "verdict": "clear", "computedBy": "server"},
                "hint": f"'{purpose_code}' không nằm trong danh mục hạn chế ({all_codes}) → về pháp lý "
                        "mục đích là CLEAR. Nếu đây là cách gọi khác của một mục trong danh mục, dùng "
                        "đúng purpose_code danh mục để chắc."}
    verdict = "blocked" if rec["restriction"] == "banned" else "conditional"
    return {"found": True, "asOf": _now(),
            "item": {"ownerId": owner_id, "purposeCode": purpose_code,
                     "purposeName": rec["purpose_name"], "restriction": rec["restriction"],
                     "verdict": verdict, "legalBasis": rec["legal_basis"], "computedBy": "server"},
            "hint": ("banned → TỪ CHỐI theo căn cứ; conditional → nêu rõ điều kiện phải đáp ứng, "
                     "không tự quyết duyệt/không (điều phối tổng hợp).")}


# ═══════════ Cụm contract (COPY từ LAB tools/server.py — chỉ legal-pack) ═══════════

REGISTRY = {
    "legal_check_docs": legal_check_docs,
    "legal_check_compliance": legal_check_compliance,
}

ANNOTATIONS = {
    "legal_check_docs": {"readOnlyHint": True},
    "legal_check_compliance": {"readOnlyHint": True},
}

SCHEMAS: dict[str, Any] = {
    "legal_check_docs": {
        "mô tả": ("PHÁP LÝ GIẤY TỜ 2 tầng: giấy nhân thân owner (so danh mục bắt buộc theo loại vay)"
                  " + giấy/pháp-lý tài sản (tranh chấp, quy hoạch). Server đối chiếu danh mục, trả"
                  " verdict clear/needs_docs/blocked + checklist missing. KHÔNG chấm DSCR/khả-năng-trả"
                  " (việc credit_assess) — 2 tool bổ nhau, không thay nhau. Read-only."),
        "params": {
            "owner_id": {"type": "str", "required": True, "desc": "id khách/DN, vd 'C013'"},
            "loan_type": {"type": "str", "values": ["consumer", "secured"], "default": "consumer",
                          "desc": "loại vay — quyết danh mục giấy bắt buộc"},
            "collateral_id": {"type": "str", "default": None,
                              "desc": "id tài sản (vay thế chấp) — check thêm pháp lý tài sản"},
        }},
    "legal_check_compliance": {
        "mô tả": ("MỤC ĐÍCH VAY hợp pháp không — server tra danh mục hạn chế: banned (từ chối)/"
                  "conditional (kèm điều kiện)/not_restricted. KHÔNG check giấy tờ (legal_check_docs)."
                  " Read-only."),
        "params": {
            "owner_id": {"type": "str", "required": True, "desc": "id khách/DN"},
            "purpose_code": {"type": "str", "required": True,
                             "desc": "mã mục đích vay, vd 'business_expansion'/'bds_speculation'"},
        }},
}
