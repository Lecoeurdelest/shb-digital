"""roles/legal — labpack Legal (COPY từ LAB shb-digital-experts, KHÔNG sửa logic).

Aggregate legal.py + cụm REGISTRY/ANNOTATIONS/SCHEMAS legal-pack (từ tools/server.py) của
mission shb-132 (D-08) thành 1 module role (lab-joint §3). 5 tool:
legal_check_docs · legal_check_compliance · legal_check_police · legal_verify_employment ·
legal_classify_profile (tool GHI assessments — WRITE, xem PGConnAdapter whitelist D-55b).

D-55a: _assumptions + credit_assess SHARE qua import labpack credit (KHÔNG dup 2 hàm).
port đủ 5 tool T7-2 (18/7) — legal.py re-sync LAB nguyên bản, chỉ đổi dòng import .credit →
labpack path (prod-mandatory, N1: adapter lo PG, logic tool 0 đổi). D-58 tinh thần: aggregate
byte-verify vs LAB (0 hunk logic).

RANH GIỚI N1/D-27: đây là TRÍ KHÔN của LAB — VỎ KHÔNG sửa. `conn` do vỏ cấp là PGConnAdapter
(D-27) giả lập sqlite3.Connection (`.execute()` + `?`→`%s` + row 3-mode + WRITE khoanh vùng
assessments D-55b). Logic dưới KHÔNG đổi 1 ký tự so với bản LAB. Không import SDK/MCP.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from roles.credit.functions import _assumptions, credit_assess


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
    # ÁN-L-F4: chuỗi rỗng/space không phải mục đích hợp lệ — chặn ở cửa như enum sai
    purpose_code = (purpose_code or "").strip()
    if not purpose_code:
        return {"code": "invalid_param", "message": "purpose_code rỗng",
                "hint": "Truyền mã mục đích thật, vd 'business_expansion'/'bds_speculation'.",
                "retryable": True, "asOf": _now()}
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


# ── 3 TRỤ PHÊ DUYỆT (mentor-1807): ①công an ②CIC (credit_cic_get sẵn) ③lương xác minh ──

def _assumption_str(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    r = _one(conn, "SELECT value FROM assumptions WHERE key=?", (key,))
    return str(r["value"]) if r else default


def _owner_identity(conn: sqlite3.Connection, owner_id: str) -> dict | None:
    """Bản nhân thân NGÂN HÀNG khai (customers/businesses) — để đối chiếu bản công an giữ."""
    c = _one(conn, "SELECT id, full_name, id_number, address, monthly_income FROM customers WHERE id=?",
             (owner_id,))
    if c:
        return {"kind": "customer", "full_name": c["full_name"], "id_number": c["id_number"],
                "address": c["address"], "declared_income": float(c["monthly_income"] or 0)}
    b = _one(conn, "SELECT id, name, tax_code, address, annual_revenue FROM businesses WHERE id=?",
             (owner_id,))
    if b:
        return {"kind": "business", "full_name": b["name"], "id_number": b["tax_code"],
                "address": b["address"], "declared_income": float(b["annual_revenue"] or 0) / 12.0}
    return None


def legal_check_police(conn: sqlite3.Connection, owner_id: str) -> dict[str, Any]:
    """Tra cổng BỘ CÔNG AN (mock) — 2 tầng: nhân thân khớp/lệch từng trường + tiền án/điều tra.
    Không bản ghi → honest null, KHÔNG suy đoán."""
    bank = _owner_identity(conn, owner_id)
    if not bank:
        return {"found": False, "asOf": _now(),
                "hint": f"Không có owner '{owner_id}'. Lấy id: cust_search(q=...)."}
    rec = _one(conn, "SELECT owner_id, id_number, full_name, address, criminal_status, record_type, "
                     "record_year, notes FROM police_records WHERE owner_id=?", (owner_id,))
    if not rec:
        return {"found": False, "asOf": _now(),
                "hint": (f"Chưa tra được bản ghi công an cho '{owner_id}' — nói rõ 'chưa xác minh "
                         "được nhân thân/tiền án', KHÔNG suy đoán sạch hay không sạch.")}

    mismatches = [{"field": f, "bank": bank.get(k), "police": rec[f]}
                  for f, k in (("id_number", "id_number"), ("full_name", "full_name"),
                               ("address", "address"))
                  if (bank.get(k) or "") != (rec[f] or "")]
    blocked_types = [t for t in _assumption_str(conn, "blocked_record_types").split(",") if t]
    crim = rec["criminal_status"]
    flags: list[str] = []
    if mismatches:
        flags.append("identity_mismatch: nhân thân bank-khai LỆCH bản công an — dừng, xác minh lại hồ sơ")
    if crim == "under_investigation":
        flags.append("under_investigation: ĐANG BỊ ĐIỀU TRA — không phê duyệt trong lúc điều tra")
    elif crim == "criminal_record":
        if rec["record_type"] in blocked_types:
            flags.append(f"criminal_blocked: tiền án {rec['record_type']} thuộc danh mục chặn cứng")
        else:
            # ÁN-L-F1: phân nhánh theo tuổi án (assumption criminal_record_expiry_years — trước là assumption chết)
            expiry = int(_assumptions(conn).get("criminal_record_expiry_years", 7))
            age = datetime.now(timezone.utc).year - int(rec["record_year"] or 0)
            if rec["record_year"] and age >= expiry:
                flags.append(f"criminal_conditional_expired: tiền án {rec['record_type']} "
                             f"({rec['record_year']}, {age} năm — quá hạn {expiry} năm, có thể đã xoá "
                             "án tích) — người thẩm định xem, không chặn tự động")
            else:
                flags.append(f"criminal_recent: tiền án {rec['record_type']} ({rec['record_year']}) "
                             f"CHƯA quá hạn {expiry} năm — thẩm định kỹ, không tự duyệt")
    return {
        "found": True, "asOf": _now(),
        "item": {"ownerId": owner_id, "identityMatch": not mismatches, "mismatches": mismatches,
                 "criminalStatus": crim, "recordType": rec["record_type"],
                 "recordYear": rec["record_year"], "notes": rec["notes"], "flags": flags,
                 "computedBy": "server"},
        "hint": ("Kết quả đối chiếu do server tra — trích thẳng. Giấy tờ đủ/thiếu → legal_check_docs; "
                 "lịch sử tín dụng → credit_cic_get; chốt lane cuối → legal_classify_profile."),
    }


def legal_verify_employment(conn: sqlite3.Connection, owner_id: str) -> dict[str, Any]:
    """Xác minh việc làm + LƯƠNG THỰC (verified) vs kê khai — server tính chênh %.
    KHÔNG tính DSCR (việc credit_assess) — lệch vượt ngưỡng thì BÁO điều phối đề nghị Credit tính lại."""
    bank = _owner_identity(conn, owner_id)
    if not bank:
        return {"found": False, "asOf": _now(),
                "hint": f"Không có owner '{owner_id}'. Lấy id: cust_search(q=...)."}
    rec = _one(conn, "SELECT owner_id, employer, position, tenure_months, verified_income_vnd, "
                     "status, verified_at FROM employment_records WHERE owner_id=?", (owner_id,))
    if not rec:
        return {"found": False, "asOf": _now(),
                "hint": (f"Chưa có bản ghi xác minh việc làm cho '{owner_id}' (DN thường không có) — "
                         "nói rõ 'chưa xác minh được thu nhập', KHÔNG coi kê khai là đã xác minh.")}
    declared = bank["declared_income"]
    verified = float(rec["verified_income_vnd"] or 0)
    mismatch_pct = round((declared - verified) / verified * 100, 1) if verified > 0 else None
    threshold = _assumptions(conn).get("income_mismatch_max_pct", 10)
    within = mismatch_pct is not None and abs(mismatch_pct) <= threshold
    flags: list[str] = []
    if rec["status"] == "expired":
        flags.append("employment_expired: xác nhận việc làm HẾT HIỆU LỰC — yêu cầu xác nhận mới")
    if mismatch_pct is not None and not within:
        flags.append(f"income_mismatch: kê khai lệch {mismatch_pct:+}% so lương xác minh "
                     f"(ngưỡng ±{threshold:g}%) — báo điều phối đề nghị Credit tính lại DSCR "
                     "bằng verified_income")
    return {
        "found": True, "asOf": _now(),
        "item": {"ownerId": owner_id, "employer": rec["employer"], "position": rec["position"],
                 "tenureMonths": rec["tenure_months"], "status": rec["status"],
                 "declaredIncomeVnd": declared, "verifiedIncomeVnd": verified,
                 "mismatchPct": mismatch_pct, "withinThreshold": within, "flags": flags,
                 "verifiedAt": rec["verified_at"], "computedBy": "server",
                 "assumptionsUsed": {"income_mismatch_max_pct": threshold}},
        "hint": ("Chênh % do server tính — trích thẳng. Lệch vượt ngưỡng: KHÔNG tự tính lại DSCR, "
                 "báo điều phối để Credit chạy lại. Chốt lane cuối → legal_classify_profile."),
    }


def legal_classify_profile(conn: sqlite3.Connection, owner_id: str, loan_amount_vnd: float,
                           loan_type: str | None = None, collateral_id: str | None = None,
                           purpose_code: str | None = None) -> dict[str, Any]:
    """⭐ CHỐT CUỐI: server chạy trọn 3 trụ + giấy tờ + mục đích + tín dụng → lane green/yellow/red
    + decision theo phân cấp thẩm quyền, GHI sổ assessments (tool WRITE duy nhất). Agent cấm tự phán lane."""
    loan_amount_vnd = float(loan_amount_vnd or 0)
    if loan_amount_vnd <= 0:
        return {"code": "invalid_param", "message": f"loan_amount_vnd={loan_amount_vnd} phải >0",
                "hint": "classify cần số tiền vay cụ thể của ca.", "retryable": False, "asOf": _now()}
    if loan_type is not None and loan_type not in ("consumer", "secured"):
        return {"code": "bad_enum", "message": f"loan_type '{loan_type}' không hợp lệ",
                "hint": "consumer | secured, hoặc bỏ trống để suy theo collateral.",
                "retryable": False, "asOf": _now()}
    bank = _owner_identity(conn, owner_id)
    if not bank:
        return {"found": False, "asOf": _now(),
                "hint": f"Không có owner '{owner_id}'. Lấy id: cust_search(q=...)."}
    eff_type = loan_type or ("secured" if collateral_id else "consumer")
    a = _assumptions(conn)
    auto_max = a.get("auto_approve_max_vnd", 2e9)
    cic_block = int(a.get("cic_block_min_group", 3))

    criteria: list[dict[str, Any]] = []

    def crit(key: str, level: str, detail: str) -> None:
        criteria.append({"key": key, "level": level, "detail": detail})  # pass|yellow|red

    police = legal_check_police(conn, owner_id)
    if not police.get("found"):
        crit("identity", "yellow", "chưa tra được bản ghi công an — cần xác minh tay")
        crit("criminal", "yellow", "chưa tra được tiền án")
    else:
        pi = police["item"]
        crit("identity", "pass" if pi["identityMatch"] else "yellow",
             "nhân thân khớp bản công an" if pi["identityMatch"]
             else f"lệch {[m['field'] for m in pi['mismatches']]} — xác minh lại hồ sơ")
        if pi["criminalStatus"] == "clean":
            crit("criminal", "pass", "không tiền án")
        elif any(f.startswith(("criminal_blocked", "under_investigation")) for f in pi["flags"]):
            crit("criminal", "red", "; ".join(pi["flags"]) or pi["criminalStatus"])
        else:
            crit("criminal", "yellow", "; ".join(pi["flags"]) or pi["criminalStatus"])

    cic = _one(conn, "SELECT cic_group FROM cic_records WHERE owner_id=?", (owner_id,))
    if cic is None:
        crit("cic", "yellow", "chưa có bản ghi CIC — không suy đoán nhóm")
    elif cic["cic_group"] >= cic_block:
        crit("cic", "red", f"CIC nhóm {cic['cic_group']} ≥ {cic_block} (nợ xấu) — chặn theo chính sách")
    elif cic["cic_group"] == 2:
        crit("cic", "yellow", "CIC nhóm 2 — nợ cần chú ý, người xem thêm")
    else:
        crit("cic", "pass", f"CIC nhóm {cic['cic_group']}")

    emp = legal_verify_employment(conn, owner_id)
    if bank["kind"] == "business":
        # ÁN-L-F2: asymmetry CHỦ ĐÍCH — khoản vay DN luôn qua người (lab chưa có tầng xác minh BCTC)
        crit("employment", "yellow",
             "DN: chưa có cơ chế xác minh tài chính doanh nghiệp (BCTC) trong hệ — "
             "khoản vay DN LUÔN qua người duyệt (chính sách lab, giả-thuyết-tag)")
    elif not emp.get("found"):
        crit("employment", "yellow", "chưa xác minh được việc làm/thu nhập")
    elif emp["item"]["flags"]:
        crit("employment", "yellow", "; ".join(emp["item"]["flags"]))
    else:
        crit("employment", "pass",
             f"lương xác minh khớp kê khai (lệch {emp['item']['mismatchPct']}%)")

    docs = legal_check_docs(conn, owner_id, loan_type=eff_type, collateral_id=collateral_id)
    if docs.get("code") == "collateral_owner_mismatch":
        # ÁN-L-F3: dùng tài sản NGƯỜI KHÁC = tín hiệu gian — criterion riêng, RED, không lẫn thiếu-giấy
        crit("collateral_ownership", "red",
             f"{docs['message']} — TÍN HIỆU GIAN LẬN TIỀM NĂNG, điều tra trước khi xử lý tiếp")
    elif not docs.get("found") or "code" in docs:
        crit("docs", "yellow", str(docs.get("message") or docs.get("hint", "không check được giấy tờ")))
    else:
        dv = docs["item"]["verdict"]
        crit("docs", {"clear": "pass", "needs_docs": "yellow", "blocked": "red"}[dv],
             f"legal_check_docs: {dv}" + (f" — thiếu {[m['doc'] for m in docs['item']['docChecklist']['missing'] if m['mandatory']]}"
                                          if dv == "needs_docs" else ""))

    if purpose_code:
        comp = legal_check_compliance(conn, owner_id, purpose_code)
        if comp.get("found"):
            r = comp["item"]["restriction"]
            crit("purpose", {"not_restricted": "pass", "conditional": "yellow", "banned": "red"}[r],
                 f"mục đích '{purpose_code}': {r}")

    credit = credit_assess(conn, owner_id, loan_amount_vnd=loan_amount_vnd,
                           collateral_id=collateral_id, loan_type=loan_type)
    if credit.get("code") == "collateral_owner_mismatch":
        if not any(c["key"] == "collateral_ownership" for c in criteria):  # docs đã bắt thì không lặp
            crit("collateral_ownership", "red",
                 f"{credit['message']} — TÍN HIỆU GIAN LẬN TIỀM NĂNG, điều tra trước khi xử lý tiếp")
    elif not credit.get("found") or "code" in credit:
        crit("credit", "yellow", str(credit.get("message") or "không chạy được thẩm định tín dụng"))
    else:
        cv = credit["item"]["verdict"]
        crit("credit", {"eligible": "pass", "needs_info": "yellow", "ineligible": "red",
                        "info_only": "yellow"}[cv],
             f"credit_assess: {cv}" + (f" — {credit['item']['reasons']}" if credit["item"]["reasons"] else ""))

    lane = ("red" if any(c["level"] == "red" for c in criteria) else
            "yellow" if any(c["level"] == "yellow" for c in criteria) else "green")
    decision = ("reject_recommended" if lane == "red" else
                "human_review_required" if lane == "yellow" else
                "auto_approve_eligible" if loan_amount_vnd <= auto_max else
                "human_approval_required")
    basis = {"lane_policy_version": _assumption_str(conn, "lane_policy_version", "v1"),
             "auto_approve_max_vnd": auto_max, "cic_block_min_group": cic_block,
             "blocked_record_types": _assumption_str(conn, "blocked_record_types"),
             "source": "assumptions table (mentor-1807-hypothesis)"}
    cur = conn.execute(
        "INSERT INTO assessments(owner_id, loan_type, loan_amount_vnd, lane, criteria_json, basis, created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (owner_id, eff_type, loan_amount_vnd, lane, json.dumps(criteria, ensure_ascii=False),
         json.dumps(basis, ensure_ascii=False), _now()))
    conn.commit()

    return {
        "found": True, "asOf": _now(),
        "item": {"assessmentId": cur.lastrowid, "ownerId": owner_id, "loanType": eff_type,
                 "loanAmountVnd": loan_amount_vnd, "lane": lane, "decision": decision,
                 "criteria": criteria, "basis": basis, "computedBy": "server",
                 "recordedTo": "assessments"},
        "hint": ("Lane + decision do SERVER tính từ tiêu chí máy-đọc và ĐÃ GHI sổ assessments — "
                 "trích NGUYÊN VĂN, cấm tự phán xanh/đỏ. decision=auto_approve_eligible nghĩa là đủ "
                 "điều kiện TỰ ĐỘNG theo phân cấp; human_* → chuyển cấp thẩm quyền, bạn chỉ ĐỀ XUẤT. "
                 "Thực thi giải ngân là việc Operations."),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Cụm contract (COPY từ LAB tools/server.py — chỉ legal-pack, 5 tool)
# ═══════════════════════════════════════════════════════════════════════════

REGISTRY = {
    "legal_check_docs": legal_check_docs,
    "legal_check_compliance": legal_check_compliance,
    "legal_check_police": legal_check_police,
    "legal_verify_employment": legal_verify_employment,
    "legal_classify_profile": legal_classify_profile,
}

# WRITE_TOOLS: legal_classify_profile GHI assessments (adapter mở WRITE khoanh vùng — D-55b)
WRITE_TOOLS = {"legal_classify_profile"}

# annotations chuẩn MCP (Trụ 8) — harness đặt policy máy-đọc
ANNOTATIONS = {
    "legal_check_docs": {"readOnlyHint": True},
    "legal_check_compliance": {"readOnlyHint": True},
    "legal_check_police": {"readOnlyHint": True},
    "legal_verify_employment": {"readOnlyHint": True},
    "legal_classify_profile": {"readOnlyHint": False, "idempotentHint": False},
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
    "legal_check_police": {
        "mô tả": ("TRA CỔNG BỘ CÔNG AN (mock) — 2 tầng trong 1 call: ①NHÂN THÂN bank-khai vs"
                  " công-an-giữ, khớp/lệch TỪNG trường ②TIỀN ÁN/đang-điều-tra + loại án. KHÔNG check"
                  " giấy tờ đủ/thiếu (legal_check_docs) · KHÔNG tra CIC (credit_cic_get) — 3 nguồn"
                  " bổ nhau. Không có bản ghi → nói rõ 'chưa xác minh được', cấm suy đoán. Read-only."),
        "params": {"owner_id": {"type": "str", "required": True, "desc": "id khách/DN, vd 'C013'"}}},
    "legal_verify_employment": {
        "mô tả": ("XÁC MINH VIỆC LÀM + LƯƠNG THỰC: server so lương XÁC MINH vs KÊ KHAI → chênh % +"
                  " cờ vượt ngưỡng. Lệch vượt ngưỡng → BÁO điều phối đề nghị Credit tính lại DSCR"
                  " bằng verified_income — tool này KHÔNG tính DSCR (việc credit_assess). DN thường"
                  " không có bản ghi → nói rõ 'chưa xác minh'. Read-only."),
        "params": {"owner_id": {"type": "str", "required": True, "desc": "id khách/DN"}}},
    "legal_classify_profile": {
        "mô tả": ("⭐ CHỐT CUỐI thẩm định pháp lý — GỌI SAU CÙNG khi đã nắm ca (owner + số tiền):"
                  " server tự chạy TRỌN 3 trụ (công an + CIC + lương) + giấy tờ + mục đích + tín dụng"
                  " → LANE green/yellow/red + DECISION (auto_approve_eligible / human_review_required /"
                  " human_approval_required / reject_recommended) theo phân cấp thẩm quyền, và GHI SỔ"
                  " assessments (tool GHI DB duy nhất — không read-only, mỗi call thêm 1 bản ghi)."
                  " Agent CẤM tự phán lane/quyết duyệt — trích nguyên văn lane + decision + criteria."
                  " LƯU Ý: khoản vay DOANH NGHIỆP (B0xx) không bao giờ auto — luôn qua người duyệt"
                  " (hệ chưa có xác minh BCTC; tiêu chí employment ghi rõ điều này)."),
        "params": {
            "owner_id": {"type": "str", "required": True, "desc": "id khách/DN"},
            "loan_amount_vnd": {"type": "float", "required": True, "desc": "số tiền vay của ca (>0)"},
            "loan_type": {"type": "str", "values": ["consumer", "secured"], "default": None,
                          "desc": "bỏ trống server suy: có collateral=secured"},
            "collateral_id": {"type": "str", "default": None, "desc": "id tài sản nếu vay thế chấp"},
            "purpose_code": {"type": "str", "default": None,
                             "desc": "mã mục đích vay nếu ca có nêu — server check compliance luôn"},
        }},
}
