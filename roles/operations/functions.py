"""roles/operations — labpack Operations (COPY từ LAB shb-digital-experts, KHÔNG sửa logic).

Port CERTIFIED v1 (19/7 ~2h sáng — AGENT-ops-DONE.md, phong bì bàn giao) thay STUB vỏ-viết
(D-18/D-35). 3 tool: ops_app_get · ops_plan (read-only) · ops_disburse (WRITE + GATE — LAB tự
gác cổng nghiệp vụ TRỌN trên schema riêng `applications/disbursements/procedure_steps` — T12-2,
CHƯA có trên worktree này tại thời điểm port T12-3; xem ghi chú "SEAM T12-2" dưới).
BYTE-IDENTICAL với `missions/shb-132/tools/functions/operations.py` — 0 hunk logic, 0 import
cần sửa (operations.py KHÔNG cross-import role khác).

Aggregate REGISTRY/ANNOTATIONS/SCHEMAS lấy nguyên văn từ `missions/shb-132/tools/server.py`
(cụm ops_app_get/ops_plan/ops_disburse — D-08 pattern, giống roles/legal/functions.py).

RANH GIỚI N1/D-27: đây là TRÍ KHÔN của LAB — VỎ KHÔNG sửa. Logic dưới KHÔNG đổi 1 ký tự so
với LAB (kể cả `sqlite3.Connection` type hint + `conn.execute("BEGIN IMMEDIATE")` — SQL LAB
viết cho SQLite, KHÔNG portable Postgres nguyên trạng; xem seam note).

── PHANH (T12-3, "SỐNG CÒN" — CLAUDE.md §"ops_disburse × PHANH") ──────────────────────────────
`ops_disburse` là tool WRITE của LAB, KHÔNG được chạy trực tiếp qua `run_labpack_fn` (path đọc
thường của mount_role — PGConnAdapter write-whitelist D-55b CHỈ mở cho `INSERT INTO assessments`,
nên dù lỡ mount thường thì insert `disbursements`/update `applications` cũng bị chặn fail-closed
— nhưng đó là lưới an toàn, KHÔNG phải thiết kế). Thiết kế ĐÚNG: `ops_disburse` nằm trong
`app/orch/gated.GATED_WHITELIST` (mount_role.py áp `gated()` wrapper theo TÊN tool — N1 giữ,
0 sửa gated.py cấu trúc 4-nhánh/advisory-lock/receipt-invariant mà 30 money-test hiện có đang
neo vào `disburse`/`loans`/`loan_id`/`amount`). `ops_disburse` là tool GATED THỨ HAI, ĐỘC LẬP
hoàn toàn với `disburse` cũ (khác action-key trong payload_hash/approvals, khác GATED_TOOLS
entry) — KHÔNG đụng 1 dòng nào của đường `disburse` cũ → 30 test cũ nguyên vẹn.

── SEAM T12-2 (khai báo tường minh, KHÔNG tự vá — ngoài scope T12-3) ──────────────────────────
LAB `ops_disburse` thao tác trên bảng `applications`/`disbursements`/`procedure_steps`
(application_id/amount_vnd) — schema RIÊNG của LAB, CHƯA migrate vào Postgres hệ thống (T12-2,
dependency của T12-3, chưa chạy trên worktree cổng này). Vỏ `loans`/`loan_id`/`amount` (D-21
write-back) là bảng KHÁC, KHÔNG map 1-1 với `applications`. Do đó `GATED_TOOLS["ops_disburse"]`
gọi THẲNG hàm LAB nguyên trạng (nhận `conn` gated cấp, SAME tx — khớp interface `fn(conn,**kw)`
D-18) — khi bảng `applications` chưa tồn tại, PG trả lỗi "relation does not exist" → gated bắt
ở `except Exception` (gated.py cửa cuối) → trả `gated_error` 4-field sạch (KHÔNG traceback,
KHÔNG bypass phanh — phiếu vẫn tạo/claim đúng quy trình 4-nhánh TRƯỚC khi inner chạy, human-path
luôn tạo phiếu pending an toàn dù inner sau đó lỗi bảng-thiếu).

**KHÔNG "chạy thật ngay" chỉ bằng thêm bảng** (sửa nhận định sai lúc đầu viết seam này —
advisor bắt lúc review): LAB `ops_disburse` tự mở tx riêng (`conn.execute("BEGIN IMMEDIATE")`
+ `conn.commit()`/`conn.rollback()` NỘI BỘ + bắt `sqlite3.IntegrityError`/`sqlite3.OperationalError`)
— xung đột trực tiếp với mô hình gated (1 conn/1 tx CHUNG xuyên claim+inner+receipt, gated tự
sở hữu commit, invariant `status='used' ⟺ receipt present` — xem module docstring gated.py).
Nếu chạy verbatim: inner tự commit sớm → receipt-save sau đó KHÔNG cùng tx với ghi disbursement
→ vỡ đúng invariant money mà 30 test đang bảo vệ. T12-2 khi portable-hoá (D-21 A2: việc của LAB,
không phải vỏ reimplement) PHẢI làm 3 việc, không chỉ tạo bảng: (a) `?`→`%s` + bỏ
`BEGIN IMMEDIATE` (gated đã BEGIN qua psycopg2 connect thường + advisory-lock, không cần LAB tự
mở tx), (b) đổi `sqlite3.IntegrityError/OperationalError`→tương đương `psycopg2.Error`, (c) BỎ
`conn.commit()`/`conn.rollback()` nội bộ của LAB fn (gated._gated_txn sở hữu commit/rollback
DUY NHẤT — như `disburse` stub vỏ hiện tại KHÔNG tự commit, chỉ ghi qua cursor). T12-3 (port
này) CHỈ đảm bảo: không bypass phanh + lỗi-bảng-thiếu ra 4-field sạch — KHÔNG tự sửa logic/tx
LAB (N1). Verify: test port dưới đây.
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


def _owner_name(c: sqlite3.Connection, owner_id: str) -> str:
    r = _one(c, "SELECT full_name AS n FROM customers WHERE id=?", (owner_id,)) or \
        _one(c, "SELECT name AS n FROM businesses WHERE id=?", (owner_id,))
    return r["n"] if r else owner_id


def _gate_check(conn: sqlite3.Connection, app: dict) -> tuple[list[str], list[dict], dict | None]:
    """Trả (blockers, steps, executed_dsb) — 1 nguồn sự thật cho cả ops_plan lẫn ops_disburse."""
    blockers: list[str] = []
    if app["status"] == "rejected":
        blockers.append("application_rejected: hồ sơ đã bị TỪ CHỐI — không có gì để giải ngân")
    if not app["credit_ok"]:
        blockers.append("credit_gate: chưa qua thẩm định tín dụng (credit_ok=0)")
    if not app["legal_ok"]:
        blockers.append("legal_gate: chưa qua pháp chế (legal_ok=0) — chờ Legal xử lý xong")
    if app["human_approval"] == "pending":
        blockers.append("human_approval_pending: phiếu duyệt đang CHỜ NGƯỜI ký — không được vượt")
    elif app["human_approval"] == "denied":
        blockers.append("human_approval_denied: cấp thẩm quyền ĐÃ TỪ CHỐI")
    steps = _rows(conn, "SELECT step, status, done_at FROM procedure_steps WHERE application_id=? "
                        "ORDER BY step", (app["id"],))
    for s in steps:
        if s["status"] != "done":
            blockers.append(f"procedure_pending: thủ tục '{s['step']}' chưa hoàn tất "
                            "(công chứng/đăng ký GDBĐ xong mới giải ngân)")
    dsb = _one(conn, "SELECT * FROM disbursements WHERE application_id=? AND status='executed'",
               (app["id"],))
    if dsb:
        blockers.append(f"already_disbursed: ĐÃ giải ngân ({dsb['id']}, biên nhận "
                        f"{dsb['receipt_code']}, {dsb['executed_at']}) — cấm giải ngân đôi")
    return blockers, steps, dsb


def ops_app_get(conn: sqlite3.Connection, application_id: str) -> dict[str, Any]:
    """Hồ sơ vận hành MỘT application: trạng thái + cổng + thủ tục + biên nhận đã có."""
    app = _one(conn, "SELECT * FROM applications WHERE id=?", (application_id,))
    if not app:
        ids = [r["id"] for r in _rows(conn, "SELECT id FROM applications ORDER BY id")]
        return {"found": False, "asOf": _now(),
                "hint": f"Không có application '{application_id}'. Hiện có: {ids}."}
    blockers, steps, dsb = _gate_check(conn, app)
    return {"found": True, "asOf": _now(),
            "item": {"applicationId": app["id"], "ownerId": app["owner_id"],
                     "ownerName": _owner_name(conn, app["owner_id"]),
                     "productId": app["product_id"], "loanAmountVnd": app["loan_amount_vnd"],
                     "loanType": app["loan_type"], "collateralId": app["collateral_id"],
                     "status": app["status"],
                     "gates": {"creditOk": bool(app["credit_ok"]), "legalOk": bool(app["legal_ok"]),
                               "humanApproval": app["human_approval"],
                               "approvalRef": app["approval_ref"]},
                     "procedureSteps": steps, "disbursement": dsb,
                     "blockers": blockers, "computedBy": "server"},
            "hint": ("Lộ trình còn lại + việc kế → ops_plan. Giải ngân → ops_disburse (server tự "
                     "gác cổng — đừng tự kết luận đủ/thiếu điều kiện).")}


def ops_plan(conn: sqlite3.Connection, application_id: str) -> dict[str, Any]:
    """Lộ trình còn lại tới giải ngân — SERVER tính từ cổng + thủ tục, trả nextAction rõ."""
    app = _one(conn, "SELECT * FROM applications WHERE id=?", (application_id,))
    if not app:
        return {"found": False, "asOf": _now(),
                "hint": f"Không có application '{application_id}'. Tra danh sách: ops_app_get."}
    blockers, steps, dsb = _gate_check(conn, app)
    if dsb:
        next_action = "không còn gì — hồ sơ ĐÃ giải ngân, lưu biên nhận"
    elif app["status"] == "rejected" or app["human_approval"] == "denied":
        next_action = "đóng hồ sơ — đã từ chối; muốn vay lại phải mở hồ sơ mới"
    elif not app["legal_ok"] or not app["credit_ok"]:
        next_action = "chờ phòng chuyên môn xử lý xong cổng đang thiếu (xem blockers) — Ops không làm hộ"
    elif app["human_approval"] == "pending":
        next_action = "chờ cấp thẩm quyền ký phiếu duyệt — không được vượt"
    elif any(s["status"] != "done" for s in steps):
        pend = [s["step"] for s in steps if s["status"] != "done"]
        next_action = f"hoàn tất thủ tục: {pend} → rồi mới ops_disburse"
    else:
        next_action = "đủ điều kiện — thực hiện ops_disburse (số tiền phải khớp hồ sơ)"
    return {"found": True, "asOf": _now(),
            "item": {"applicationId": app["id"], "status": app["status"], "blockers": blockers,
                     "remainingSteps": [s["step"] for s in steps if s["status"] != "done"],
                     "nextAction": next_action, "computedBy": "server",
                     "assumptionsUsed": {"disburse_requires":
                                         "credit_ok, legal_ok, human_approval_resolved, procedures_done"
                                         " (assumptions, gia-thuyet-ops)"}},
            "hint": "nextAction do server tính — trích thẳng, không tự chế lộ trình."}


def ops_disburse(conn: sqlite3.Connection, application_id: str, amount_vnd: float,
                 beneficiary: str | None = None) -> dict[str, Any]:
    """⭐ GIẢI NGÂN (tool WRITE + GATE): server verify TRỌN điều kiện — thiếu 1 cổng là CHẶN,
    trả blockers rõ. Đủ → ghi disbursements + cập nhật status, trả biên nhận. Chống double."""
    amount_vnd = float(amount_vnd or 0)
    if not math.isfinite(amount_vnd) or amount_vnd <= 0:
        return {"code": "invalid_param", "message": f"amount_vnd={amount_vnd} phải là số hữu hạn >0",
                "hint": "Số tiền giải ngân phải khớp đúng loan_amount_vnd của hồ sơ.",
                "retryable": False, "asOf": _now()}
    app = _one(conn, "SELECT * FROM applications WHERE id=?", (application_id,))
    if not app:
        return {"found": False, "asOf": _now(),
                "hint": f"Không có application '{application_id}'."}
    blockers, _steps, _dsb = _gate_check(conn, app)
    if amount_vnd != float(app["loan_amount_vnd"]):
        # N1: số có phần lẻ phải hiện phần lẻ — không để 2 số khác nhau in ra giống hệt
        shown = f"{amount_vnd:,.0f}" if amount_vnd == int(amount_vnd) else f"{amount_vnd:,.5f}"
        blockers.append(f"amount_mismatch: đề nghị {shown} ≠ hồ sơ duyệt "
                        f"{app['loan_amount_vnd']:,.0f} — không giải ngân lệch số")
    if blockers:
        return {"code": "disburse_blocked",
                "message": f"KHÔNG giải ngân {application_id} — {len(blockers)} chặn",
                "blockers": blockers,
                "hint": "Xử lý hết blockers (ops_plan cho lộ trình) rồi gọi lại. "
                        "CẤM lách cổng dưới mọi lý do.",
                "retryable": True, "asOf": _now()}
    # ÁN-O-F1: serialize đoạn ghi (race 2 request cùng COUNT → cùng id → UNIQUE nổ db_error trần)
    bene = beneficiary or f"{_owner_name(conn, app['owner_id'])} ({app['owner_id']})"
    try:
        conn.execute("BEGIN IMMEDIATE")
        dup = _one(conn, "SELECT id, receipt_code FROM disbursements WHERE application_id=? "
                         "AND status='executed'", (application_id,))
        if dup:
            conn.rollback()
            return {"code": "disburse_blocked",
                    "message": f"KHÔNG giải ngân {application_id} — 1 chặn",
                    "blockers": [f"already_disbursed: ĐÃ giải ngân ({dup['id']}, biên nhận "
                                 f"{dup['receipt_code']}) — request song song đã chi trước"],
                    "hint": "Đã có biên nhận — trích biên nhận cũ, không chi đôi.",
                    "retryable": False, "asOf": _now()}
        n = _one(conn, "SELECT COUNT(*) AS n FROM disbursements", ())["n"]
        dsb_id = f"DSB{n + 1:02d}"
        receipt = f"RC-2026-{100000 + n + 1:06d}"
        conn.execute("INSERT INTO disbursements(id, application_id, amount_vnd, beneficiary, status, "
                     "executed_at, receipt_code) VALUES(?,?,?,?,?,?,?)",
                     (dsb_id, application_id, amount_vnd, bene, "executed", _now(), receipt))
        conn.execute("UPDATE applications SET status='disbursed' WHERE id=?", (application_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        return {"code": "disburse_blocked",
                "message": f"KHÔNG giải ngân {application_id} — đụng ghi đồng thời",
                "blockers": ["concurrent_write: request song song vừa ghi sổ — kiểm tra lại "
                             "bằng ops_app_get trước khi thử lại"],
                "hint": "Gọi ops_app_get xem đã có biên nhận chưa; đã có thì KHÔNG gọi lại.",
                "retryable": True, "asOf": _now()}
    except sqlite3.OperationalError as e:
        conn.rollback()
        return {"code": "disburse_blocked",
                "message": f"KHÔNG giải ngân {application_id} — sổ đang bận ({str(e)[:60]})",
                "blockers": ["ledger_busy: sổ giải ngân đang bị khoá bởi request khác"],
                "hint": "Thử lại 1 lần; kiểm ops_app_get trước để tránh chi đôi.",
                "retryable": True, "asOf": _now()}
    return {"found": True, "asOf": _now(),
            "item": {"disbursementId": dsb_id, "applicationId": application_id,
                     "amountVnd": amount_vnd, "beneficiary": bene, "status": "executed",
                     "receiptCode": receipt, "computedBy": "server"},
            "hint": ("ĐÃ GIẢI NGÂN — trích biên nhận nguyên văn. Gọi lại lần nữa sẽ bị chặn "
                     "already_disbursed (chống đôi).")}


# ── Aggregate REGISTRY/ANNOTATIONS/SCHEMAS (từ missions/shb-132/tools/server.py — nguyên văn) ──
# ops_disburse trong app/orch/gated.GATED_WHITELIST (name-match) → mount_role áp gated() wrapper,
# KHÔNG chạy qua run_labpack_fn thường (xem docstring seam trên). ops_app_get/ops_plan read-only.
REGISTRY = {"ops_app_get": ops_app_get, "ops_plan": ops_plan, "ops_disburse": ops_disburse}
ANNOTATIONS = {
    "ops_app_get": {"readOnlyHint": True},
    "ops_plan": {"readOnlyHint": True},
    "ops_disburse": {"readOnlyHint": False, "idempotentHint": False},  # gated (§4.4)
}
SCHEMAS: dict[str, Any] = {
    "ops_app_get": {
        "mô tả": ("HỒ SƠ VẬN HÀNH một application: trạng thái pipeline + 4 cổng (credit/legal/"
                  "người-ký/thủ-tục) + biên nhận đã có + blockers server-tính. KHÔNG trả lộ-trình-"
                  "việc-kế (ops_plan) · KHÔNG giải ngân (ops_disburse). Read-only."),
        "params": {"application_id": {"type": "str", "required": True, "desc": "vd 'APP01'"}}},
    "ops_plan": {
        "mô tả": ("LỘ TRÌNH còn lại tới giải ngân — server tính blockers + remainingSteps +"
                  " nextAction từ 4 cổng. Trích nguyên văn, cấm tự chế lộ trình. Read-only."),
        "params": {"application_id": {"type": "str", "required": True, "desc": "vd 'APP02'"}}},
    "ops_disburse": {
        "mô tả": ("⭐ GIẢI NGÂN (tool GHI + GATE — không read-only): server verify TRỌN điều kiện"
                  " (credit_ok + legal_ok + người-ký-xong + thủ-tục-done + số-tiền-khớp-hồ-sơ +"
                  " chưa-từng-giải-ngân) — thiếu 1 cổng là CHẶN kèm blockers, KHÔNG lách được"
                  " bằng lời. Đủ → ghi sổ + biên nhận. Agent chỉ THI HÀNH khi được yêu cầu giải"
                  " ngân; không tự ý gọi khi chỉ được hỏi trạng thái."),
        "params": {
            "application_id": {"type": "str", "required": True, "desc": "hồ sơ cần giải ngân"},
            "amount_vnd": {"type": "float", "required": True,
                           "desc": "số tiền — PHẢI khớp đúng loan_amount_vnd của hồ sơ"},
            "beneficiary": {"type": "str", "default": None,
                            "desc": "bên thụ hưởng — bỏ trống = chủ hồ sơ"},
        }},
}


# ── HOTFIX F3 (T12-3 regression): mount lại tool `disburse` cũ (loans-based) — đường DEMO CHÍNH ──
# T12-3 thay stub vỏ bằng LAB ops → REGISTRY mất `disburse` → MAIN brief "gọi tool disburse" chết
# (sub không thấy tool). `disburse` là GATED (app/orch/gated.GATED_WHITELIST) — REGISTRY entry CHỈ để
# mount thấy tên+schema; gated wrapper (mount_role name-match) chặn + tự chạy GATED_TOOLS['disburse']
# (fn dưới KHÔNG được gọi trực tiếp). fn+schema COPY từ stub vỏ cũ (git e075f37~1 — byte-identical).
def disburse(conn: sqlite3.Connection, loan_id: str, amount: float = 0) -> dict[str, Any]:
    """[GATED — vỏ, T3-1] Giải ngân khoản vay. CÓ PHANH: gọi đầu → chờ người duyệt → duyệt →
    chạy (ghi loans.status='disbursed'). Logic thật ở app/orch/gated.disburse (wrapper thread-conn
    tự chạy — REGISTRY entry này chỉ để mount thấy tên+schema; gated wrapper KHÔNG gọi fn này).
    D-18: phanh là của VỎ. GATED_WHITELIST={disburse}."""
    # KHÔNG chạy trực tiếp — gated wrapper (mount) chặn + tự chạy GATED_TOOLS['disburse'].
    raise RuntimeError("disburse phải qua gated wrapper (T3-1) — không gọi trực tiếp")


REGISTRY["disburse"] = disburse
ANNOTATIONS["disburse"] = {"destructiveHint": True}  # gated (§4.4) — harness policy máy-đọc
SCHEMAS["disburse"] = {
    "mô tả": ("GIẢI NGÂN khoản vay (CÓ PHANH — cần người duyệt). Gọi lần đầu → hệ thống CHẶN, "
              "tạo phiếu chờ duyệt; báo main kết thúc lượt. Sau khi được DUYỆT, gọi lại đúng "
              "tham số → giải ngân chạy thật. KHÔNG tự nhẩm/bỏ qua phanh."),
    "params": {
        "loan_id": {"type": "str", "required": True, "desc": "id khoản vay, vd 'L001'"},
        "amount": {"type": "float", "default": 0, "desc": "số tiền giải ngân (VND)"},
    }}
