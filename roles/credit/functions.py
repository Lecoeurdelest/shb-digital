"""roles/credit — labpack Credit (COPY từ LAB shb-digital-experts, KHÔNG sửa logic).

Gộp credit.py + customers.py của mission shb-132 (D-08) thành 1 module role
(lab-joint §3: functions + cụm SCHEMAS/REGISTRY/ANNOTATIONS sống cạnh nhau).
Chỉ credit-pack (4 tool): credit_assess, credit_cic_get, cust_search, cust_get.
Bỏ legal (mount ở sprint sau).

RANH GIỚI N1/D-27: đây là TRÍ KHÔN của LAB — VỎ KHÔNG sửa. `conn` do vỏ cấp là
PGConnAdapter (D-27) giả lập sqlite3.Connection (`.execute()` + `?`→`%s` + row 3-mode),
nên logic dưới KHÔNG đổi 1 ký tự so với bản LAB. Không import SDK/MCP.

_assumptions re-sync LAB 18/7 — D-58 (labpack đã drift bản crash string-key; khôi phục
graceful-skip đúng LAB để nạp được assumption value CHỮ như blocked_record_types).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

MAX_LIMIT = 20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ═══════════════════════════════════════════════════════════════════════════
# credit.py (COPY byte-nguyên từ LAB tools/functions/credit.py)
# ═══════════════════════════════════════════════════════════════════════════

def _annuity(principal: float, annual_rate: float, term_months: int) -> float:
    """Công thức KHOÁ theo SEED-REPORT §1 — tool BẮT BUỘC khớp seed, lệch là ca biên chết."""
    r = annual_rate / 12
    n = term_months
    if r == 0:
        return principal / n
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def _assumptions(conn: sqlite3.Connection) -> dict[str, float]:
    # assumptions chứa cả value chuỗi (blocked_record_types...) — chỉ lấy dòng ép số được
    out: dict[str, float] = {}
    try:
        for k, v in conn.execute("SELECT key, value FROM assumptions").fetchall():
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                continue
    except sqlite3.Error:
        pass
    return out


def _one(conn: sqlite3.Connection, sql: str, args: tuple) -> dict | None:
    r = conn.execute(sql, args).fetchone()
    return dict(r) if r else None


def credit_cic_get(conn: sqlite3.Connection, owner_id: str) -> dict[str, Any]:
    rec = _one(conn, "SELECT owner_id, cic_group, history_note FROM cic_records WHERE owner_id=?", (owner_id,))
    if not rec:
        return {"found": False, "asOf": _now(),
                "hint": f"Không có bản ghi CIC cho '{owner_id}' — coi như chưa có lịch sử tín dụng (nhóm 1 mặc định KHÔNG áp dụng, phải nói rõ 'chưa có bản ghi')."}
    g = rec["cic_group"]
    hint = ("CIC nhóm 1 — lịch sử tốt." if g == 1 else
            f"CIC nhóm {g} — {'CẢNH BÁO nợ cần chú ý' if g == 2 else 'NỢ XẤU, theo chính sách thường TỪ CHỐI vay mới'}."
            + " Đưa thông tin này vào thẩm định, không bỏ qua.")
    return {"found": True, "item": rec, "asOf": _now(), "hint": hint}


def credit_assess(conn: sqlite3.Connection, owner_id: str, loan_amount_vnd: float = 0,
                  collateral_id: str | None = None, loan_type: str | None = None,
                  term_months: int | None = None,
                  income_override_vnd: float | None = None) -> dict[str, Any]:
    """Thẩm định trọn gói: DSCR + LTV + CIC + trần + verdict. loan_amount_vnd=0 → chỉ hiện trạng.
    loan_type 'consumer'|'secured' — bỏ trống thì suy: có collateral_id = secured, không = consumer.
    rate/term lấy từ assumptions THEO LOẠI (công thức khoá SEED-REPORT §1)."""
    # F2/F4 (audit): validate TRƯỚC khi tính — số âm/enum sai phải chết ở cửa, không im lặng
    loan_amount_vnd = float(loan_amount_vnd or 0)
    if term_months is not None:
        term_months = int(term_months)
    if loan_amount_vnd < 0 or (term_months is not None and term_months <= 0):
        return {"code": "invalid_param",
                "message": f"loan_amount_vnd={loan_amount_vnd} phải ≥0; term_months={term_months} phải >0",
                "hint": "Sửa tham số rồi gọi lại.", "retryable": False, "asOf": _now()}
    if loan_type is not None and loan_type not in ("consumer", "secured"):
        return {"code": "bad_enum", "message": f"loan_type '{loan_type}' không hợp lệ",
                "hint": "Dùng 'consumer' | 'secured', hoặc bỏ trống để server tự suy.",
                "retryable": False, "asOf": _now()}
    # QĐ-I-1 (additive, thi hành QĐ-L6): vòng lặp lương-lệch — Legal xác minh lương thật → Credit
    # tính lại theo verified_income. None = hành vi y cũ (key/certify cũ không đụng).
    if income_override_vnd is not None:
        income_override_vnd = float(income_override_vnd)
        import math as _math
        if not _math.isfinite(income_override_vnd) or income_override_vnd <= 0:
            return {"code": "invalid_param",
                    "message": f"income_override_vnd={income_override_vnd} phải là số hữu hạn >0",
                    "hint": "Truyền lương xác minh từ legal_verify_employment (verifiedIncomeVnd).",
                    "retryable": False, "asOf": _now()}

    a = _assumptions(conn)
    dscr_min = a.get("dscr_min", 1.2)
    ltv_max = a.get("ltv_max", 0.70)
    cap_pct = a.get("single_customer_cap_pct", 0.15)
    bank_equity = a.get("bank_equity_bil_vnd", 50000) * 1e9  # tỷ → VND

    explicit_type = loan_type
    if loan_type not in ("consumer", "secured"):
        loan_type = "secured" if collateral_id else "consumer"
    if loan_type == "secured":
        rate = a.get("rate_secured_annual", 0.08)
        term = int(term_months or a.get("term_secured_months", 180))
    else:
        rate = a.get("rate_consumer_annual", 0.15)
        term = int(term_months or a.get("term_consumer_months", 60))

    ent = _one(conn, "SELECT id, full_name AS name, monthly_income AS income FROM customers WHERE id=?", (owner_id,))
    kind = "customer"
    if not ent:
        b = _one(conn, "SELECT id, name, annual_revenue FROM businesses WHERE id=?", (owner_id,))
        if b:
            kind = "business"
            ent = {"id": b["id"], "name": b["name"], "income": (b["annual_revenue"] or 0) / 12.0}
    if not ent:
        return {"found": False, "asOf": _now(), "hint": f"Không có owner '{owner_id}'. Lấy id: cust_search(q=...)."}

    monthly_income = float(ent["income"] or 0)
    income_source = "declared (customers.monthly_income)"
    if income_override_vnd is not None:
        monthly_income = income_override_vnd
        income_source = "OVERRIDE (lương xác minh từ Legal — vòng lặp lương-lệch)"
    pay_row = conn.execute(
        "SELECT COALESCE(SUM(monthly_payment),0) FROM loans WHERE owner_id=? AND status='active'", (owner_id,)
    ).fetchone()
    existing_payment = float(pay_row[0] or 0)
    debt_row = conn.execute(
        "SELECT COALESCE(SUM(outstanding),0) FROM loans WHERE owner_id=? AND status='active'", (owner_id,)
    ).fetchone()
    debt_total = float(debt_row[0] or 0)

    new_payment = _annuity(loan_amount_vnd, rate, term) if loan_amount_vnd > 0 else 0.0
    total_payment = existing_payment + new_payment
    dscr = round(monthly_income / total_payment, 3) if total_payment > 0 else None

    ltv = None
    collateral = None
    warnings: list[str] = []
    if collateral_id:
        collateral = _one(conn, "SELECT id, owner_id, type, appraised_value, docs_status FROM collaterals WHERE id=?",
                          (collateral_id,))
        if not collateral:
            return {"found": False, "asOf": _now(),
                    "hint": f"Không có collateral '{collateral_id}'. Xem tài sản của khách trong cust_get(id) (nếu đã có tool riêng thì dùng), hoặc bỏ collateral_id để thẩm định tín chấp."}
        # F1 (audit — CRITICAL): tài sản phải CỦA CHÍNH owner — không được thế chấp đồ người khác
        if collateral["owner_id"] != owner_id:
            return {"found": False, "code": "collateral_owner_mismatch",
                    "message": f"{collateral_id} thuộc {collateral['owner_id']}, KHÔNG phải của {owner_id}",
                    "hint": f"Dùng tài sản của chính {owner_id} (xem cust_get) hoặc bỏ collateral_id (tín chấp).",
                    "retryable": False, "asOf": _now()}
        # F5 (audit): khai mâu thuẫn thay vì im lặng bỏ qua ý định
        if explicit_type == "consumer":
            warnings.append("loan_type=consumer nhưng có collateral_id — đang chấm TÍN CHẤP (rate consumer); "
                            "LTV chỉ tham khảo. Vay thế chấp thì đặt loan_type='secured' hoặc bỏ trống.")
        if loan_amount_vnd > 0 and (collateral["appraised_value"] or 0) > 0:
            ltv = round(loan_amount_vnd / float(collateral["appraised_value"]), 3)

    cic = _one(conn, "SELECT cic_group FROM cic_records WHERE owner_id=?", (owner_id,))
    cic_group = cic["cic_group"] if cic else None

    reasons: list[str] = []
    missing: list[str] = []
    if loan_amount_vnd > 0:
        if dscr is not None and dscr < dscr_min:
            reasons.append(f"dscr_below_min: DSCR {dscr} < ngưỡng {dscr_min}")
        if ltv is not None and ltv > ltv_max:
            reasons.append(f"ltv_above_max: LTV {ltv} > trần {ltv_max}")
        if loan_amount_vnd > cap_pct * bank_equity:
            reasons.append(f"exceeds_single_customer_cap: vượt trần 1-khách {cap_pct*100:.0f}% vốn tự có "
                           f"({cap_pct*bank_equity/1e9:.0f} tỷ VND)")
        # sanity số-to (án vòng-3: sonnet gõ thừa 1 số 0 → 76.000 tỷ, báo sai 10 lần): cảnh, không chặn
        if loan_amount_vnd > 2 * cap_pct * bank_equity:
            warnings.append(f"loan_amount_vnd={loan_amount_vnd:,.0f} = {loan_amount_vnd/1e9:,.0f} tỷ VND — "
                            f"gấp {loan_amount_vnd/(cap_pct*bank_equity):.0f} lần trần 1-khách. "
                            "SỐ BẤT THƯỜNG LỚN — xác nhận lại đơn vị VND trước khi kết luận.")
        if cic_group is not None and cic_group >= 3:
            reasons.append(f"cic_bad_debt: CIC nhóm {cic_group} (nợ xấu)")
        if loan_type == "secured" and collateral is None:
            missing.append("collateral_id (vay thế chấp phải có tài sản — xem tài sản của khách qua cust_get)")
        if collateral and collateral.get("docs_status") != "complete":
            missing.append(f"giấy tờ tài sản: {collateral['docs_status']} (Legal xử lý — không chặn thẩm định tín dụng)")
    if monthly_income <= 0:
        missing.append("monthly_income (chưa có dữ liệu thu nhập)")

    verdict = ("needs_info" if missing and not reasons else
               "ineligible" if reasons else
               "eligible" if loan_amount_vnd > 0 else "info_only")

    return {
        "found": True, "asOf": _now(),
        "item": {
            "ownerId": owner_id, "kind": kind, "name": ent["name"], "verdict": verdict,
            "metrics": {"dscr": dscr, "ltv": ltv, "cicGroup": cic_group,
                        "debtTotalOutstandingVnd": debt_total,
                        "monthlyPaymentTotalVnd": round(total_payment)},
            "reasons": reasons, "missing": missing, "warnings": warnings,
            "inputs": {"monthlyIncomeVnd": monthly_income, "incomeSource": income_source,
                       "existingMonthlyPaymentVnd": existing_payment,
                       "newLoanMonthlyPaymentVnd": round(new_payment), "loanAmountVnd": loan_amount_vnd,
                       "loanType": loan_type, "termMonths": term if loan_amount_vnd > 0 else None,
                       "collateralAppraisedVnd": (collateral or {}).get("appraised_value")},
            "assumptionsUsed": {"dscr_min": dscr_min, "ltv_max": ltv_max,
                                "single_customer_cap_pct": cap_pct,
                                "annual_rate": rate, "formula": "annuity (SEED-REPORT §1)",
                                "source": "assumptions table (gia-thuyet-lab)"},
            "computedBy": "server",
        },
        "hint": ("Verdict + metrics do SERVER tính — trích thẳng, không tính lại. "
                 "Giấy tờ tài sản thiếu → việc của Legal; chọn gói vay → Products."),
    }


# ═══════════════════════════════════════════════════════════════════════════
# customers.py (COPY byte-nguyên từ LAB tools/functions/customers.py)
# ═══════════════════════════════════════════════════════════════════════════

def _rows(c: sqlite3.Connection, sql: str, args: tuple = ()) -> list[dict]:
    return [dict(r) for r in c.execute(sql, args).fetchall()]


def cust_search(conn: sqlite3.Connection, q: str, limit: int = 5) -> dict[str, Any]:
    q = (q or "").strip()
    if not q:
        return {"code": "bad_param", "message": "q rỗng", "hint": "truyền tên khách hoặc tên DN, vd q='Văn A'",
                "retryable": True}
    limit = min(int(limit or 5), MAX_LIMIT)
    like = f"%{q}%"
    custs = _rows(conn, "SELECT id, full_name, occupation, monthly_income, region FROM customers "
                        "WHERE full_name LIKE ?", (like,))
    bizs = _rows(conn, "SELECT id, name, sector, annual_revenue FROM businesses WHERE name LIKE ?", (like,))
    items = ([{"id": r["id"], "kind": "customer", "name": r["full_name"], "occupation": r["occupation"],
               "monthlyIncomeVnd": r["monthly_income"], "region": r["region"]} for r in custs]
             + [{"id": r["id"], "kind": "business", "name": r["name"], "sector": r["sector"],
                 "annualRevenueVnd": r["annual_revenue"]} for r in bizs])
    total = len(items)
    truncated = total > limit
    out = {"items": items[:limit], "count": min(total, limit), "total": total,
           "truncated": truncated, "asOf": _now()}
    if total == 0:
        out["hint"] = f"Không khớp '{q}'. Thử từ khoá ngắn hơn (chỉ họ hoặc tên) trước khi kết luận không có."
    elif total > 1:
        out["hint"] = f"{total} kết quả trùng/gần tên — HỎI người dùng chọn đúng ai, KHÔNG tự chọn. Chi tiết: cust_get(id)."
    else:
        out["hint"] = "Đúng 1 kết quả. Hồ sơ đầy đủ + khoản vay: cust_get(id)."
    return out


def cust_get(conn: sqlite3.Connection, id: str) -> dict[str, Any]:
    ent = _rows(conn, "SELECT * FROM customers WHERE id=?", (id,))
    kind = "customer"
    if not ent:
        ent = _rows(conn, "SELECT * FROM businesses WHERE id=?", (id,))
        kind = "business"
    if not ent:
        return {"found": False, "hint": f"Không có id '{id}'. Lấy id đúng bằng cust_search(q=<tên>).", "asOf": _now()}
    loans = _rows(conn, "SELECT loan_id, principal, outstanding, monthly_payment, status "
                        "FROM loans WHERE owner_id=?", (id,))
    active = [l for l in loans if l.get("status") == "active"]
    # ÁN-2 (epoch-0): trả kèm tài sản — trò cần collateral_id để credit_assess tính LTV
    collaterals = _rows(conn, "SELECT id, type, appraised_value, docs_status "
                              "FROM collaterals WHERE owner_id=?", (id,))
    item = {"kind": kind, "profile": ent[0], "loans": loans,
            "debtTotalOutstandingVnd": sum(l["outstanding"] or 0 for l in active),
            "monthlyPaymentTotalVnd": sum(l["monthly_payment"] or 0 for l in active),
            "activeLoans": len(active),
            "collaterals": collaterals}
    return {"found": True, "item": item, "asOf": _now(),
            "hint": ("Totals do server tính từ khoản active — dùng thẳng, không tự cộng. "
                     "Vay THẾ CHẤP: lấy collateral id từ 'collaterals' ở đây truyền vào credit_assess "
                     "để server tính LTV. Muốn DSCR/khả-năng-trả (kể cả không vay thêm) → "
                     "credit_assess(owner_id, loan_amount_vnd=0).")}


# ═══════════════════════════════════════════════════════════════════════════
# Cụm contract (COPY từ LAB tools/server.py — chỉ credit-pack, BỎ legal)
# ═══════════════════════════════════════════════════════════════════════════

REGISTRY = {
    "cust_search": cust_search,
    "cust_get": cust_get,
    "credit_assess": credit_assess,
    "credit_cic_get": credit_cic_get,
}

# annotations chuẩn MCP (Trụ 8) — harness đặt policy máy-đọc
ANNOTATIONS = {
    "cust_search": {"readOnlyHint": True},
    "cust_get": {"readOnlyHint": True},
    "credit_assess": {"readOnlyHint": True},
    "credit_cic_get": {"readOnlyHint": True},
}

SCHEMAS: dict[str, Any] = {
    "cust_search": {
        "mô tả": ("Tìm khách cá nhân + doanh nghiệp theo TÊN (một phần cũng được). Trả LEAN"
                  " {items[{id,kind,name,...}]} — hồ sơ đầy đủ dùng cust_get(id). Nhiều kết quả"
                  " trùng/gần tên → HỎI người dùng, KHÔNG tự chọn. Read-only."),
        "params": {
            "q": {"type": "str", "required": True, "desc": "tên khách/DN, vd 'Văn A' hoặc 'Minh Phát'"},
            "limit": {"type": "int", "default": 5, "max": 20},
        }},
    "cust_get": {
        "mô tả": ("Hồ sơ đầy đủ MỘT khách/DN theo id: profile + khoản vay + TÀI SẢN (collaterals — lấy"
                  " id ở đây cho credit_assess vay thế chấp). Server ĐÃ TÍNH tổng dư nợ + tổng trả/tháng"
                  " — dùng thẳng, KHÔNG tự cộng. KHÔNG có DSCR — muốn DSCR/khả-năng-trả (kể cả không"
                  " vay thêm) → credit_assess. Read-only."),
        "params": {"id": {"type": "str", "required": True, "desc": "id từ cust_search, vd 'C007'/'B003'"}}},
    "credit_assess": {
        "mô tả": ("THẨM ĐỊNH TRỌN GÓI + là tool DUY NHẤT trả DSCR: server tính DSCR + LTV + CIC + tổng"
                  " nợ + so ngưỡng → verdict (eligible/ineligible/needs_info/info_only) + reasons +"
                  " missing, kèm inputs + assumptions để truy vết. loan_amount_vnd=0 = đánh giá HIỆN"
                  " TRẠNG (vẫn ra DSCR hiện tại). Vay THẾ CHẤP phải truyền collateral_id (lấy từ"
                  " cust_get) để có LTV. CẤM tự tính lại các số này. Read-only."),
        "params": {
            "owner_id": {"type": "str", "required": True, "desc": "id khách/DN, vd 'C007'/'B003'"},
            "loan_amount_vnd": {"type": "float", "default": 0, "desc": "số tiền muốn vay (VND), vd 500000000"},
            "collateral_id": {"type": "str", "default": None, "desc": "id tài sản thế chấp (nếu vay thế chấp)"},
            "loan_type": {"type": "str", "values": ["consumer", "secured"], "default": None,
                          "desc": "loại vay — bỏ trống server tự suy: có collateral=secured, không=consumer"},
            "term_months": {"type": "int", "default": None,
                            "desc": "kỳ hạn tháng — bỏ trống dùng chuẩn theo loại (consumer 60 / secured 180)"},
            "income_override_vnd": {"type": "float", "default": None,
                                    "desc": "lương XÁC MINH từ Legal (vòng lặp lương-lệch) — chỉ truyền khi Legal flag income_mismatch; bỏ trống dùng lương kê khai"},
        }},
    "credit_cic_get": {
        "mô tả": ("Tra cứu CIC (lịch sử tín dụng) MỘT khách/DN: nhóm nợ 1-5 + ghi chú. Nhóm ≥3 = nợ xấu."
                  " Không có bản ghi → nói rõ 'chưa có bản ghi', KHÔNG suy đoán nhóm. Read-only."),
        "params": {"owner_id": {"type": "str", "required": True, "desc": "id khách/DN"}}},
}
