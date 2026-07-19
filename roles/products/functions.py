"""roles/products — labpack Products (COPY từ LAB shb-digital-experts, KHÔNG sửa logic).

Port CERTIFIED v1 (19/7 rạng sáng — AGENT-products-DONE.md, phong bì bàn giao) thay STUB
vỏ-viết (D-18/D-35). 2 tool: product_list (catalog) · product_suggest (server match hồ sơ thật).
BYTE-IDENTICAL với `missions/shb-132/tools/functions/products.py` — 0 hunk logic, 0 import cần
sửa (products.py KHÔNG cross-import role khác, khác legal→credit).

Aggregate REGISTRY/ANNOTATIONS/SCHEMAS lấy nguyên văn từ `missions/shb-132/tools/server.py`
(cụm product_list/product_suggest — D-08 pattern, giống roles/legal/functions.py).

RANH GIỚI N1/D-27: đây là TRÍ KHÔN của LAB — VỎ KHÔNG sửa. `conn` do vỏ cấp là PGConnAdapter
giả lập sqlite3.Connection (`.execute()` + `?`→`%s`). Logic dưới KHÔNG đổi 1 ký tự so với LAB.
Cả 2 tool READ-ONLY (không cần gated wrapper — khác operations.ops_disburse).
"""
from __future__ import annotations

import math
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


def _lean(p: dict) -> dict:
    return {"id": p["id"], "name": p["name"], "loanType": p["loan_type"],
            "rateAnnual": p["rate_annual"], "termMaxMonths": p["term_max_months"],
            "amountRangeVnd": [p["amount_min_vnd"], p["amount_max_vnd"]],
            "feePct": p["fee_pct"], "status": p["status"]}


def product_list(conn: sqlite3.Connection, loan_type: str | None = None,
                 segment: str | None = None) -> dict[str, Any]:
    """Catalog gói vay (lean, kèm cả gói hết hiệu lực — status rõ). Gợi ý THEO HỒ SƠ → product_suggest."""
    # ÁN-P-F3: strip đối xứng — rỗng-sau-strip = giá trị lạ, không âm thầm thành None
    loan_type = loan_type.strip() if isinstance(loan_type, str) else loan_type
    segment = segment.strip() if isinstance(segment, str) else segment
    if loan_type is not None and loan_type not in ("consumer", "secured", "business"):
        return {"code": "bad_enum", "message": f"loan_type '{loan_type}' không hợp lệ",
                "hint": "consumer | secured | business, hoặc bỏ trống lấy tất.", "retryable": False,
                "asOf": _now()}
    # ÁN-P-F2: segment lạ phải chết ở cửa — không im lặng trả tập segment-NULL
    if segment is not None and segment not in ("mass", "vip", "staff"):
        return {"code": "bad_enum", "message": f"segment '{segment}' không hợp lệ",
                "hint": "mass | vip | staff, hoặc bỏ trống lấy tất.", "retryable": False,
                "asOf": _now()}
    sql, args = "SELECT * FROM products", []
    conds = []
    if loan_type:
        conds.append("loan_type=?"); args.append(loan_type)
    if segment:
        conds.append("(segment IS NULL OR segment=?)"); args.append(segment)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    ps = _rows(conn, sql + " ORDER BY loan_type, rate_annual, id", tuple(args))
    items = [_lean(p) for p in ps]
    n_exp = sum(1 for p in ps if p["status"] == "expired")
    return {"items": items, "count": len(items), "total": len(items), "truncated": False,
            "asOf": _now(),
            "hint": ("Lãi/phí/điều kiện CHỈ theo catalog — không cam kết mức riêng. "
                     + (f"{n_exp} gói status=expired: HẾT HIỆU LỰC, không chào khách. " if n_exp else "")
                     + "Khách cụ thể hợp gói nào → product_suggest(owner_id, ...) để server match hồ sơ.")}


def product_suggest(conn: sqlite3.Connection, owner_id: str, loan_amount_vnd: float = 0,
                    loan_type: str | None = None) -> dict[str, Any]:
    """Server match hồ sơ THẬT với TỪNG gói active: loại · khoảng tiền · income_min · CIC · segment
    → eligible/ineligible + reasons + recommended (rate thấp nhất). KHÔNG chấm khả-năng-trả."""
    loan_amount_vnd = float(loan_amount_vnd or 0)
    # ÁN-P-F1: inf/nan parse được ở float() nhưng vỡ JSON-encode → 500 trần. Chặn ở cửa.
    if not math.isfinite(loan_amount_vnd) or loan_amount_vnd < 0:
        return {"code": "invalid_param", "message": f"loan_amount_vnd={loan_amount_vnd} phải là số hữu hạn ≥0",
                "hint": "0 = tư vấn tổng quát theo hồ sơ (bỏ lọc số tiền).", "retryable": False,
                "asOf": _now()}
    if loan_type is not None and loan_type not in ("consumer", "secured", "business"):
        return {"code": "bad_enum", "message": f"loan_type '{loan_type}' không hợp lệ",
                "hint": "consumer | secured | business, hoặc bỏ trống theo loại khách.",
                "retryable": False, "asOf": _now()}

    cu = _one(conn, "SELECT id, full_name AS name, monthly_income AS income, segment FROM customers WHERE id=?",
              (owner_id,))
    kind = "customer"
    if not cu:
        b = _one(conn, "SELECT id, name, annual_revenue FROM businesses WHERE id=?", (owner_id,))
        if b:
            kind = "business"
            cu = {"id": b["id"], "name": b["name"], "income": (b["annual_revenue"] or 0) / 12.0,
                  "segment": None}
    if not cu:
        return {"found": False, "asOf": _now(),
                "hint": f"Không có owner '{owner_id}'. Lấy id: cust_search(q=...)."}

    income = float(cu["income"] or 0)
    seg = cu.get("segment")
    cic = _one(conn, "SELECT cic_group FROM cic_records WHERE owner_id=?", (owner_id,))
    cic_group = cic["cic_group"] if cic else None

    allowed_types = {"business"} if kind == "business" else {"consumer", "secured"}
    if loan_type:
        allowed_types &= {loan_type}
        if not allowed_types:
            return {"code": "invalid_param",
                    "message": f"loan_type '{loan_type}' không áp cho {kind} ({owner_id})",
                    "hint": "Khách cá nhân: consumer/secured · DN: business.", "retryable": False,
                    "asOf": _now()}

    eligible, inelig = [], []
    for p in _rows(conn, "SELECT * FROM products WHERE status='active' ORDER BY rate_annual, id"):
        if p["loan_type"] not in allowed_types:
            continue
        reasons = []
        if loan_amount_vnd > 0:
            if loan_amount_vnd < p["amount_min_vnd"]:
                reasons.append(f"số tiền dưới sàn gói ({p['amount_min_vnd']:,.0f})")
            elif loan_amount_vnd > p["amount_max_vnd"]:
                reasons.append(f"số tiền vượt trần gói ({p['amount_max_vnd']:,.0f})")
        if p["income_min_vnd"] and income < p["income_min_vnd"]:
            reasons.append(f"thu nhập {income:,.0f} < điều kiện {p['income_min_vnd']:,.0f}")
        if p["cic_max_group"] is not None:
            if cic_group is None:
                reasons.append(f"chưa có bản ghi CIC (gói đòi nhóm ≤{p['cic_max_group']})")
            elif cic_group > p["cic_max_group"]:
                reasons.append(f"CIC nhóm {cic_group} > điều kiện ≤{p['cic_max_group']}")
        if p["segment"] and p["segment"] != seg:
            reasons.append(f"gói dành riêng segment '{p['segment']}' (khách: '{seg or 'chưa phân hạng'}')")
        matched = {"loaiVay": p["loan_type"],
                   **({"khoangTien": "khớp"} if loan_amount_vnd > 0 and not any("số tiền" in r for r in reasons) else {}),
                   **({"thuNhap": "đạt"} if p["income_min_vnd"] and income >= p["income_min_vnd"] else {}),
                   **({"cic": f"nhóm {cic_group} đạt"} if p["cic_max_group"] is not None and cic_group is not None and cic_group <= p["cic_max_group"] else {})}
        (eligible if not reasons else inelig).append(
            {**_lean(p), **({"matchedConditions": matched} if not reasons else {"reasons": reasons})})

    recommended = None
    if eligible:
        recommended = {"id": eligible[0]["id"], "name": eligible[0]["name"],
                       "basis": "rate_annual thấp nhất trong các gói đủ điều kiện "
                                "(assumptions.recommend_by=rate_annual_asc)"}
    return {
        "found": True, "asOf": _now(),
        "item": {"ownerId": owner_id, "kind": kind, "ownerName": cu["name"],
                 "eligibleOptions": eligible, "ineligible": inelig, "recommended": recommended,
                 "inputsUsed": {"monthlyIncomeVnd": income, "cicGroup": cic_group, "segment": seg,
                                "loanAmountVnd": loan_amount_vnd or None,
                                "loanTypesConsidered": sorted(allowed_types)},
                 "computedBy": "server"},
        "hint": (("KHÔNG gói nào nhận hồ sơ/số tiền này — nói thẳng, gợi ý đổi số tiền/loại vay "
                  "trong khoảng catalog, CẤM tự chế gói/lãi riêng. " if not eligible else
                  "recommended = rate thấp nhất trong eligible — trích nguyên văn kèm lý do. ")
                 + "Đây là HỢP GÓI, không phải duyệt vay: khả-năng-trả → credit_assess; "
                   "pháp lý → legal_*."),
    }


# ── Aggregate REGISTRY/ANNOTATIONS/SCHEMAS (từ missions/shb-132/tools/server.py — nguyên văn) ──
REGISTRY = {"product_list": product_list, "product_suggest": product_suggest}
ANNOTATIONS = {
    "product_list": {"readOnlyHint": True},
    "product_suggest": {"readOnlyHint": True},
}
SCHEMAS: dict[str, Any] = {
    "product_list": {
        "mô tả": ("CATALOG gói vay (lean): tên/lãi/kỳ hạn/khoảng tiền/phí/status — kèm cả gói HẾT"
                  " HIỆU LỰC (status=expired, không chào khách). KHÔNG match hồ sơ — khách cụ thể"
                  " hợp gói nào → product_suggest. Read-only."),
        "params": {
            "loan_type": {"type": "str", "values": ["consumer", "secured", "business"],
                          "default": None, "desc": "lọc theo loại — bỏ trống lấy tất"},
            "segment": {"type": "str", "values": ["mass", "vip", "staff"], "default": None,
                        "desc": "lọc gói mở cho segment này"},
        }},
    "product_suggest": {
        "mô tả": ("GỢI Ý GÓI THEO HỒ SƠ THẬT — server match TỪNG gói active với hồ sơ trong DB"
                  " (loại khách, khoảng tiền, thu nhập tối thiểu, CIC, segment) → eligible +"
                  " ineligible(kèm lý do) + recommended (rate thấp nhất). CẤM tự phán hợp gói,"
                  " CẤM chế lãi riêng. Đây là HỢP GÓI — KHÔNG phải duyệt vay (khả-năng-trả:"
                  " credit_assess · pháp lý: legal_*). loan_amount_vnd=0 = tư vấn tổng quát."
                  " Read-only."),
        "params": {
            "owner_id": {"type": "str", "required": True, "desc": "id khách/DN, vd 'C004'/'B001'"},
            "loan_amount_vnd": {"type": "float", "default": 0, "desc": "số tiền muốn vay (VND); 0 = bỏ lọc số tiền"},
            "loan_type": {"type": "str", "values": ["consumer", "secured", "business"],
                          "default": None, "desc": "bỏ trống: cá nhân xét consumer+secured, DN xét business"},
        }},
}
