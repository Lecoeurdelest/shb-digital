"""Verdict-aware disburse decision (T7-3, D-52/D-56) — ĐỌC sổ assessments → MA TRẬN 3 TẦNG.

Tách khỏi gated.py (chuẩn PROD ≤400 LOC + "query verdict = helper riêng"). gated._gated_txn gọi
`gated_decision(action, conn, args, threshold)` ở nhánh 4a — cấu trúc phanh (4-step tx + advisory
lock) KHÔNG đổi; evaluator đồng thời chụp khuyến nghị phản-thực cho phiếu người S18.

BACKWARD KEY: assessments RỖNG/không-verdict → hành vi Y HỆT T5-2' cũ (tầng-1 auto, tầng-2/3 người).
"""

from __future__ import annotations

import logging
import math
from typing import Any

import psycopg2
import psycopg2.extras

from app.db.config import DATABASE_URL
from app.storage import connect_core
from app.tenancy import DEFAULT_TENANT_ID

log = logging.getLogger("orch.verdict")

# Compatibility export cho test/caller cũ. Production resolve từ assumptions rồi truyền tường minh
# vào gated_decision; constant này chỉ còn là default khi key hoàn toàn VẮNG (D-72).
AUTO_APPROVE_THRESHOLD = 500_000_000  # VND
_AUTO_MAX_FALLBACK = 2_000_000_000.0  # assumptions.auto_approve_max_vnd thiếu → fallback 2e9
_DEFAULT_DATABASE_URL = DATABASE_URL


def _connect():
    # Giữ seam monkeypatch DSN của test fail-closed; production dùng pool thống nhất D-76.
    if DATABASE_URL != _DEFAULT_DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return connect_core()


def auto_approve_threshold() -> float:
    """Đọc ngưỡng tầng-1 trên conn RIÊNG để lỗi SELECT không poison transaction tiền.

    Key vắng → 500M tương thích; key có giá trị hữu hạn → dùng chính xác; NULL/rác/DB lỗi → 0
    (fail-closed). Giá trị âm vẫn được giữ chính xác rồi nhánh ``<=0`` cưỡng chế shadow-mode.
    """
    conn = None
    try:
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM assumptions WHERE key='auto_approve_threshold_vnd'")
            row = cur.fetchone()
            if row is None:
                return float(AUTO_APPROVE_THRESHOLD)
            value = float(row[0])
            if not math.isfinite(value):
                raise ValueError("threshold must be finite")
            return value
    except (psycopg2.Error, TypeError, ValueError) as e:
        log.warning("đọc auto_approve_threshold_vnd lỗi (fail-closed 0): %s", e)
        return 0.0
    finally:
        if conn is not None:
            conn.close()


def auto_approve_max(conn: Any) -> float:
    """Ngưỡng trên tầng-2 = assumptions.auto_approve_max_vnd (2e9). Thiếu/lỗi → fallback 2e9
    (KHÔNG nới auto ngoài ý định). conn = gated conn (SELECT read-only, cùng tx an toàn)."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM assumptions WHERE key='auto_approve_max_vnd'")
            row = cur.fetchone()
            if row and row[0] is not None:
                return float(row[0])
    except (psycopg2.Error, TypeError, ValueError) as e:
        log.warning("đọc auto_approve_max_vnd lỗi (fallback 2e9): %s", e)
    return _AUTO_MAX_FALLBACK


def latest_verdict_for_action(action: str, args: dict[str, Any]) -> dict[str, Any] | None:
    """Assessment mới nhất theo owner của đúng seam action → ``{id, lane}`` hoặc ``None``.

    ``disburse`` resolve ``loan_id`` qua loans; ``ops_disburse`` resolve ``application_id`` qua
    applications. Hai action khác hoặc ref thiếu đều trung tính, không đoán owner.

    D-59 (T7-3): assessments GHI 'lane' KHÔNG ghi 'decision' (LAB legal.py:337 chỉ INSERT lane —
    T7-2 byte-identical, KHÔNG được thêm cột decision = phá N1). decision suy từ lane + tầng số
    tiền disburse (xem disburse_decision). SELECT chỉ id, lane.

    CONN RIÊNG ngắn (advisor T7-3): đọc verdict trên conn TÁCH khỏi gated tx — đọc lỗi trên conn
    gated thì tx bị abort → INSERT phiếu-người sau đó nổ InFailedSqlTransaction, phá đúng nhánh
    'DB lỗi → về người'. assessments = data commit độc lập, không thuộc write-set disburse. Match
    theo owner mới-nhất (known-limitation demo-grade: KHÔNG đối chiếu số tiền ca — D-52 note)."""
    conn = None
    try:
        conn = _connect()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # D-79: owner_id của dữ liệu demo có thể trùng giữa tenant; verdict runtime phải theo
            # conversation hiện tại. Context thiếu chỉ xảy ra ở compatibility test/caller cũ.
            from app.orch import registry

            tenant_id = DEFAULT_TENANT_ID
            conv_id = registry.CTX_CONV.get()
            if conv_id:
                cur.execute("SELECT tenant_id::text FROM conversations WHERE id::text=%s", (conv_id,))
                tenant_row = cur.fetchone()
                if tenant_row:
                    tenant_id = tenant_row["tenant_id"]
            if action == "disburse":
                ref = args.get("loan_id")
                query = "SELECT owner_id FROM loans WHERE loan_id=%s"
            elif action == "ops_disburse":
                ref = args.get("application_id")
                query = "SELECT owner_id FROM applications WHERE id=%s"
            else:
                return None
            if not ref:
                return None
            cur.execute(query, (ref,))
            lrow = cur.fetchone()
            if not lrow or not lrow["owner_id"]:
                return None
            cur.execute(
                "SELECT id, lane FROM assessments WHERE tenant_id=%s AND owner_id=%s "
                "ORDER BY created_at DESC, id DESC LIMIT 1",
                (tenant_id, lrow["owner_id"]),
            )
            arow = cur.fetchone()
            return dict(arow) if arow else None
    except psycopg2.Error as e:
        log.warning("đọc verdict assessment lỗi action=%s (coi như không verdict): %s", action, e)
        return None
    finally:
        if conn is not None:
            conn.close()


def latest_verdict(loan_id: str) -> dict[str, Any] | None:
    """Compatibility wrapper: assessment mới nhất cho đường ``disburse`` cũ."""
    return latest_verdict_for_action("disburse", {"loan_id": loan_id})


def gated_decision(
    action: str, conn: Any, args: dict[str, Any], threshold_vnd: float
) -> tuple[str, str | None, dict[str, Any]]:
    """Route thật + snapshot phản-thực dùng cho ledger S18.

    Snapshot được tính trước override shadow ``threshold<=0``. Red luôn khuyến nghị reject; nếu
    ma trận bình thường sẽ auto thì ``auto-eligible``; còn lại trung tính ``human-review``.
    """
    amount_key = "amount" if action == "disburse" else "amount_vnd"
    try:
        amount = float(args.get(amount_key))
        if not math.isfinite(amount):
            raise ValueError("amount must be finite")
    except (TypeError, ValueError):
        amount = None

    verdict = latest_verdict_for_action(action, args)
    lane = verdict.get("lane") if verdict else None
    assessment_id = verdict.get("id") if verdict else None

    # `threshold<=0` là công tắc fail-closed/shadow cho ROUTE THẬT, không phải chính sách thẩm
    # quyền để đo phản-thực. Khi bị override, snapshot dùng ngưỡng danh nghĩa 500M; ngưỡng cấu
    # hình dương vẫn là nguồn duy nhất cho cả route và recommendation.
    policy_threshold = threshold_vnd if threshold_vnd > 0 else float(AUTO_APPROVE_THRESHOLD)
    tier1_auto = action == "disburse" and amount is not None and amount < policy_threshold and lane != "red"
    tier2_auto = False
    if action == "disburse" and amount is not None and lane == "green" and not tier1_auto:
        tier2_auto = amount <= auto_approve_max(conn)

    if lane == "red":
        recommendation = "reject-recommended"
    elif tier1_auto or tier2_auto:
        recommendation = "auto-eligible"
    else:
        recommendation = "human-review"
    snapshot = {
        "system_assessment_id": assessment_id,
        "system_lane": lane,
        "system_recommendation": recommendation,
    }

    # D-72: shadow override đứng TRƯỚC tier green; threshold=0 không thể rơi xuống tier-2 auto.
    if action != "disburse" or amount is None or threshold_vnd <= 0 or lane == "red":
        return ("human", None, snapshot)
    if tier1_auto:
        reason = f"Tự động duyệt theo rule: số tiền dưới ngưỡng {threshold_vnd:,.0f} VND"
        return ("auto", reason, snapshot)
    if tier2_auto:
        reason = f"Hồ sơ XANH — assessment #{assessment_id} (lane green, auto_approve_eligible)"
        return ("auto", reason, snapshot)
    return ("human", None, snapshot)


def disburse_decision(conn: Any, args: dict[str, Any], threshold_vnd: float | None = None) -> tuple[str, str | None]:
    """MA TRẬN 3 TẦNG (D-52/D-56) — trả ('auto', reason) hoặc ('human', None).

    - Tầng 1 (amount < AUTO_APPROVE_THRESHOLD): auto NHƯ CŨ, TRỪ KHI verdict xấu (lane=red HOẶC
      decision=reject_recommended) → thắt về người (có bằng chứng xấu).
    - Tầng 2 (THRESHOLD ≤ amount ≤ auto_max): auto CHỈ KHI verdict lane=green VÀ
      decision=auto_approve_eligible; else người (pain D-52 — hồ sơ XANH agent tự duyệt).
    - Tầng 3 (amount > auto_max): LUÔN người.
    assessments RỖNG/không-verdict → Y HỆT T5-2' cũ. amount thiếu/không parse → ('human', None)."""
    threshold = float(AUTO_APPROVE_THRESHOLD) if threshold_vnd is None else threshold_vnd
    decision, reason, _snapshot = gated_decision("disburse", conn, args, threshold)
    return decision, reason
