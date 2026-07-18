"""[TESTER — T3-4] Pre-scaffold từ Exports T3-1 (task #11 Cairn, đọc TRỌN — Task LÀ spec).
Viết ĐỘC LẬP với test backend tự viết (author≠checker, CLAUDE.md §6) — backend cover unit 4
nhánh + payload_hash + atomic claim cơ bản (test ownership của họ, ghi trong task #11 "## Test
ownership"); tester (T3-4) cover: gate S3 happy-path END-TO-END (browser + PG), 4 nhánh lại
qua đường THẬT (không gọi tắt nội bộ), authz decide-flag-OFF, defensive gọi-lại-pending/gọi-
lại-sau-biên-nhận. D-40: happy-path, KHÔNG crash-injection/kill-server.

TRẠNG THÁI: PRE-SCAFFOLD — viết khi T3-1 (#11) đang in_progress, Exports THẬT CHƯA CÓ. Khung
này ĐỎ (ImportError `app.orch.gated`) tới khi backend báo Exports xong — điền logic thật lúc đó,
KHÔNG đoán chi tiết implementation (chỉ theo interface đã đặc tả trong #11 §Exports).

Interface kỳ vọng (từ #11 §Exports — sẽ điều chỉnh nếu backend báo lệch):
- `app.orch.gated.payload_hash(action: str, args: dict) -> str`
- `app.orch.gated.gated(action: str, inner) -> callable` — wrapper 4-bước THREAD-CONN
- `app.orch.gated.GATED_WHITELIST` — set/dict chứa "disburse"
- approvals store CRUD (tên hàm CHƯA CHỐT — #11 nói "D-34 store phình → cân nhắc
  store_approvals.py riêng" — tự dò khi có Exports thật, KHÔNG đoán tên hàm)
- disburse stub: `disburse(conn, loan_id, amount) -> dict` ghi loans.status='disbursed'
- card approval: type='approval' (NGOÀI present enum, vỏ tự sinh — SPEC §6)
- SSE event: 'approval.pending'

Ca gate S3 (D-40 happy-path, brief #14): "giải ngân 5 tỷ cho DN X" (skip-auth admin) → agent
gọi disburse → KÉT CHẶN (approval_required + card approval + loans.status NGUYÊN) → admin BẤM
Duyệt → event resume (T3-2, NGOÀI scope T3-1 — chờ #12/#13) → giải ngân chạy →
loans.status='disbursed' + biên nhận. Bấm Từ chối → KHÔNG giải ngân.

T3-4 CHỈ verify phần T3-1 cung cấp (4 nhánh wrapper qua đường thật + payload_hash equivalence +
double-claim cơ bản) trong file NÀY. Phần T3-2 (decide API + event resume) + T3-3 (FE approval
panel) + gate S3 browser end-to-end sẽ ở file/bước riêng khi #12/#13 có Exports (chưa dispatch
tại thời điểm viết file này — xem Cairn #14 blockedBy [11], chưa thấy 12/13 trong blocks list).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from .conftest import requires_db

pytestmark = requires_db

# ── Ca thử cố định (loan seed thật — L007/B001, quen thuộc từ gate S2) ──────────────────────
TEST_LOAN_ID = "L007"  # seed thật: owner B001, principal 3_000_000_000, status 'active'
TEST_CONV_ID = "tester-t34-gate-s3-conv"  # text tự do (D-31, KHÔNG FK) — cố định để dễ trace
TEST_AMOUNT = 5_000_000_000  # "giải ngân 5 tỷ" — khớp ca gate S3 trong brief


def _restore_loan_status(conn, loan_id: str, status: str = "active") -> None:
    """Helper reset: đưa loans.status về trạng thái sạch trước mỗi test (idempotent test)."""
    cur = conn.cursor()
    cur.execute("UPDATE loans SET status=%s WHERE loan_id=%s", (status, loan_id))
    conn.commit()
    cur.close()


def _cleanup_approvals_and_cards(conn, conv_id: str) -> None:
    """Dọn CẢ approvals LẪN cards — conv_id CỐ ĐỊNH dùng xuyên suốt file (test riêng biệt vẫn
    độc lập nhờ dọn sạch trước/sau mỗi test), nên phải xoá cả 2 bảng, không chỉ approvals.
    Backend (T3-1 Exports) đã cảnh báo đúng hiện tượng pollution — root cause cụ thể: hàm cũ
    chỉ dọn `approvals`, bỏ sót `cards` (bước 4 của gated._gated_txn insert cả 2 bảng)."""
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM cards WHERE conv_id=%s", (conv_id,))
        cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv_id,))
        conn.commit()
    except Exception:  # noqa: BLE001 — bảng approvals/cards có thể chưa tồn tại (chạy trước T3-1)
        conn.rollback()
    finally:
        cur.close()


@pytest.fixture(autouse=True)
def _clean_state(pg_conn):
    """Dọn state TRƯỚC và SAU mỗi test — test có state (phiếu single-use, y hệt cảnh báo
    tester.md REPRO) không reset là run 2 khác run 1."""
    _restore_loan_status(pg_conn, TEST_LOAN_ID, "active")
    _cleanup_approvals_and_cards(pg_conn, TEST_CONV_ID)
    yield
    _restore_loan_status(pg_conn, TEST_LOAN_ID, "active")
    _cleanup_approvals_and_cards(pg_conn, TEST_CONV_ID)


# ═════════════════════════════════════════════════════════════════════════════════════════
# NHÁNH 4 — chưa có phiếu: disburse → approval_required + phiếu pending + card + loans nguyên
# ═════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_branch4_first_call_creates_pending_approval_loans_unchanged():
    """Gọi disburse LẦN ĐẦU (chưa phiếu) qua wrapper gated thật → error 4-field
    approval_required + phiếu pending trong PG + card approval (type='approval') + SSE +
    loans.status KHÔNG ĐỔI (chưa duyệt = két chưa mở, tiền/trạng thái không nhúc nhích)."""
    from app.orch import gated, registry
    from app.sse import bus

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    q = bus.subscribe(TEST_CONV_ID)
    try:
        result = await gated.gated("disburse", None)(args)
    finally:
        bus.unsubscribe(TEST_CONV_ID, q)

    # error 4-field approval_required (SPEC §4.4 bước 4)
    body = result["content"][0]["text"] if "content" in result else result
    payload = json.loads(body) if isinstance(body, str) else body
    assert payload.get("code") == "approval_required", f"phải approval_required: {payload}"
    assert payload.get("retryable") is False
    assert "message" in payload and "hint" in payload, f"error phải đủ 4-field: {payload}"
    # Mặt model KHÔNG có phiếu-id (§15 ID-cho-code) — hint/message nói theo HÀNH ĐỘNG, không lộ
    # uuid phiếu. Assert thật (không "or True" tự-xác-nhận): message/hint không chứa chuỗi UUID.
    import re

    uuid_pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
    assert not uuid_pattern.search(payload.get("message", "") + payload.get("hint", "")), (
        f"message/hint KHÔNG được lộ UUID phiếu ra mặt model (§15 ID-cho-code): {payload}"
    )

    import psycopg2

    from app.db.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT status, payload_hash FROM approvals WHERE conv_id=%s AND action='disburse'",
            (TEST_CONV_ID,),
        )
        rows = cur.fetchall()
        assert len(rows) == 1, f"phải đúng 1 phiếu pending, không đôi: {rows}"
        assert rows[0][0] == "pending"

        cur.execute("SELECT status FROM loans WHERE loan_id=%s", (TEST_LOAN_ID,))
        loan_status = cur.fetchone()[0]
        assert loan_status == "active", f"loans.status PHẢI NGUYÊN khi chưa duyệt: {loan_status}"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_branch4_repeated_call_while_pending_does_not_duplicate_ticket():
    """Defensive (D-40 cơ bản): gọi lại disburse LÚC ĐANG PENDING (chưa duyệt) → approval_pending
    (KHÔNG approval_required lần nữa), KHÔNG đẻ phiếu/card thứ hai (idempotent bước 3)."""
    from app.orch import gated, registry

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    await gated.gated("disburse", None)(args)  # lần 1: tạo phiếu pending
    result2 = await gated.gated("disburse", None)(args)  # lần 2: PHẢI thấy pending

    body = result2["content"][0]["text"] if "content" in result2 else result2
    payload = json.loads(body) if isinstance(body, str) else body
    assert payload.get("code") == "approval_pending", f"lần 2 lúc pending phải approval_pending: {payload}"

    import psycopg2

    from app.db.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) FROM approvals WHERE conv_id=%s AND action='disburse'",
            (TEST_CONV_ID,),
        )
        n = cur.fetchone()[0]
        assert n == 1, f"KHÔNG được đẻ phiếu thứ 2 khi gọi lại lúc pending: {n} phiếu"
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════════════════
# NHÁNH 2 — phiếu approved: claim atomic → chạy thật → loans.status='disbursed' + receipt
# ═════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_branch2_approved_ticket_claimed_atomically_executes_and_disburses():
    """Duyệt phiếu (set status='approved' trực tiếp trong test — mô phỏng admin đã quyết,
    T3-2 decide API là việc khác) → gọi lại disburse → claim atomic (rowcount=1) → disburse
    THẬT chạy → loans.status='disbursed' + receipt lưu + phiếu chuyển 'used'."""
    from app.orch import gated, registry

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    await gated.gated("disburse", None)(args)  # tạo phiếu pending trước

    import psycopg2

    from app.db.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE approvals SET status='approved', decided_by='test-admin', decided_at=now() "
            "WHERE conv_id=%s AND action='disburse' AND status='pending'",
            (TEST_CONV_ID,),
        )
        conn.commit()
        assert cur.rowcount == 1, "setup: phải duyệt đúng 1 phiếu"
        cur.close()
    finally:
        conn.close()

    result = await gated.gated("disburse", None)(args)  # gọi lại — PHẢI claim + chạy
    body = result["content"][0]["text"] if "content" in result else result
    payload = json.loads(body) if isinstance(body, str) else body
    assert payload.get("disbursed") is True or payload.get("code") is None, (
        f"sau duyệt, gọi lại phải THỰC THI (không phải error nữa): {payload}"
    )

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SELECT status FROM loans WHERE loan_id=%s", (TEST_LOAN_ID,))
        assert cur.fetchone()[0] == "disbursed", "loans.status PHẢI đổi sau duyệt+claim"

        cur.execute(
            "SELECT status, receipt FROM approvals WHERE conv_id=%s AND action='disburse'",
            (TEST_CONV_ID,),
        )
        row = cur.fetchone()
        assert row[0] == "used", f"phiếu phải chuyển used sau claim+chạy: {row[0]}"
        assert row[1] is not None, "receipt phải được lưu sau khi chạy thật"
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════════════════
# NHÁNH 1 — biên nhận cũ: gọi lại SAU khi đã used → trả biên nhận, KHÔNG chạy lại (chống đôi)
# ═════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_branch1_repeated_call_after_receipt_returns_cached_no_double_disburse():
    """QUAN TRỌNG NHẤT (money-doubling nếu sai): sau khi đã thực thi (phiếu used + receipt),
    gọi lại disburse VỚI ĐÚNG PAYLOAD → trả biên nhận cũ, KHÔNG chạy inner() lần 2, loans.status
    KHÔNG đổi thêm (đã 'disbursed' rồi, không disburse chồng nữa)."""
    from app.orch import gated, registry

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    await gated.gated("disburse", None)(args)  # tạo pending

    import psycopg2

    from app.db.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE approvals SET status='approved' WHERE conv_id=%s AND action='disburse'",
            (TEST_CONV_ID,),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()

    result_first_execute = await gated.gated("disburse", None)(args)  # claim + chạy thật
    result_retry = await gated.gated("disburse", None)(args)  # PHẢI thấy biên nhận, KHÔNG chạy lại

    body1 = result_first_execute["content"][0]["text"] if "content" in result_first_execute else result_first_execute
    body2 = result_retry["content"][0]["text"] if "content" in result_retry else result_retry
    p1 = json.loads(body1) if isinstance(body1, str) else body1
    p2 = json.loads(body2) if isinstance(body2, str) else body2
    assert p2.get("hint", "").lower().find("đã thực thi") != -1 or p2 == p1, (
        f"gọi lại sau receipt phải trả biên nhận cũ (giống hoặc hint nói rõ đã thực thi trước): {p2}"
    )

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SELECT status FROM loans WHERE loan_id=%s", (TEST_LOAN_ID,))
        assert cur.fetchone()[0] == "disbursed", "loans.status vẫn 'disbursed' — KHÔNG bị disburse chồng"
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════════════════
# NHÁNH 3 — pending (lặp lại, verify qua đường gated() công khai — khác test branch4 ở chỗ
# assert riêng về "không phiếu/card mới" bằng đếm PG kỹ hơn, giữ tách để dễ đọc lỗi khi FAIL)
# ═════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_branch3_pending_call_returns_approval_pending_not_required():
    """Phân biệt rõ 2 code khác nhau: LẦN ĐẦU → approval_required (bước 4); LẦN SAU lúc pending
    → approval_pending (bước 3) — KHÔNG lẫn lộn 2 message, agent cần biết đây là 'đã gửi rồi,
    đang chờ' chứ không phải 'gửi mới lần nữa'."""
    from app.orch import gated, registry

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    r1 = await gated.gated("disburse", None)(args)
    r2 = await gated.gated("disburse", None)(args)

    b1 = r1["content"][0]["text"] if "content" in r1 else r1
    b2 = r2["content"][0]["text"] if "content" in r2 else r2
    p1 = json.loads(b1) if isinstance(b1, str) else b1
    p2 = json.loads(b2) if isinstance(b2, str) else b2

    assert p1["code"] == "approval_required"
    assert p2["code"] == "approval_pending"
    assert p1["code"] != p2["code"], "2 code PHẢI khác nhau — agent phân biệt được 2 tình huống"


# ═════════════════════════════════════════════════════════════════════════════════════════
# payload_hash equivalence — 1 hàm DUY NHẤT, chuẩn hoá đúng (§4.4 + #11 §B)
# ═════════════════════════════════════════════════════════════════════════════════════════


def test_payload_hash_equivalence_int_float_key_order_none_drop():
    """int/float cùng giá trị, thứ tự key khác, field None → CÙNG hash. Số tiền khác nhau
    (1 tỷ vs 5 tỷ) → KHÁC hash rõ ràng (không lách 'xin duyệt A làm B' — SPEC §4.4)."""
    from app.orch import gated

    h1 = gated.payload_hash("disburse", {"loan_id": "L007", "amount": 5_000_000_000})
    h2 = gated.payload_hash("disburse", {"loan_id": "L007", "amount": 5_000_000_000.0})  # float
    h3 = gated.payload_hash("disburse", {"amount": 5_000_000_000, "loan_id": "L007"})  # key order khác
    h4 = gated.payload_hash("disburse", {"loan_id": "L007", "amount": 5_000_000_000, "note": None})  # None-drop
    h5 = gated.payload_hash("disburse", {"loan_id": "L007", "amount": 5e9})  # scientific notation

    assert h1 == h2 == h3 == h4 == h5, f"cùng nghiệp vụ PHẢI cùng hash: {[h1, h2, h3, h4, h5]}"

    h_diff_amount = gated.payload_hash("disburse", {"loan_id": "L007", "amount": 1_000_000_000})
    assert h1 != h_diff_amount, "1 tỷ vs 5 tỷ PHẢI khác hash — không được lách duyệt ít làm nhiều"

    h_diff_loan = gated.payload_hash("disburse", {"loan_id": "L999", "amount": 5_000_000_000})
    assert h1 != h_diff_loan, "loan khác PHẢI khác hash"


def test_payload_hash_used_consistently_at_creation_and_verify():
    """1 HÀM DUY NHẤT dùng chung tạo phiếu lẫn verify — lệch là phanh chết âm thầm (#11 §B
    cảnh báo tường minh). Verify gián tiếp: phiếu tạo ra ở nhánh 4 phải tra được BẰNG ĐÚNG
    payload_hash() gọi độc lập với args y hệt (không phải hash cache nội bộ khác)."""
    from app.orch import gated, registry

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    asyncio.run(gated.gated("disburse", None)(args))

    expected_hash = gated.payload_hash("disburse", args)

    import psycopg2

    from app.db.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT payload_hash FROM approvals WHERE conv_id=%s AND action='disburse'",
            (TEST_CONV_ID,),
        )
        row = cur.fetchone()
        assert row is not None, "phiếu phải tồn tại"
        assert row[0] == expected_hash, (
            f"payload_hash lưu trong phiếu PHẢI khớp payload_hash() gọi độc lập — lệch = phanh chết: "
            f"stored={row[0]} vs computed={expected_hash}"
        )
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════════════════
# Double-claim CƠ BẢN (D-40 — KHÔNG crash-injection, chỉ gather đồng thời + verify rowcount)
# ═════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_concurrent_double_claim_basic_only_one_executes():
    """2 GỌI ĐỒNG THỜI cùng phiếu approved (asyncio.gather, KHÔNG dàn crash/kill server —
    D-40 mức cơ bản) → verify INVARIANT TIỀN: đúng 1 lệnh THỰC SỰ chạy inner() (fresh
    execution), lệnh còn lại thấy BIÊN NHẬN CŨ (KHÔNG chạy lại) — KHÔNG exception từ race.

    LỊCH SỬ (giữ lại — bài học §6b, đừng xoá): lần đầu viết test này (TRƯỚC advisory-lock
    fix), phát hiện qua debug độc lập: dưới race thật, READ COMMITTED không đủ ngăn 2 tx
    cùng đọc "chưa có gì" ở bước 1-3 trước khi 1 bên commit → lệnh thua rơi bước 4, tạo
    THÊM 1 phiếu pending GIẢ (spurious ticket). Money KHÔNG đôi (đã verify) nhưng RÁC sinh
    ra. Báo [STATUS] cho architect — quyết FIX (không waiver): thêm `pg_advisory_xact_lock`
    per-key đầu `_gated_txn` (serialize 2 tx cùng key, D-41a).

    SAU FIX (test này verify): lệnh thua cuộc giờ CHỜ lock, thấy `used`+`receipt` đã commit
    của lệnh thắng → trả **biên nhận cũ** (bước 1), KHÔNG rơi bước 4 nữa. Payload biên nhận
    CŨNG mang field `disbursed:true` (đúng thiết kế — biên nhận phải chứa lại kết quả gốc để
    user biết đã disburse gì) — nên đếm `disbursed_count` (cách viết CŨ, đã tự sửa) KHÔNG
    còn phân biệt được 2 tình huống; phải đếm dựa trên `hint` "đã thực thi trước đó" để tách
    fresh execution khỏi cached-receipt-replay."""
    from app.orch import gated, registry, store

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    await gated.gated("disburse", None)(args)  # tạo pending

    import psycopg2

    from app.db.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE approvals SET status='approved' WHERE conv_id=%s AND action='disburse'",
            (TEST_CONV_ID,),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()

    # 2 gọi ĐỒNG THỜI (gather) — advisory lock serialize: 1 chạy trước, 1 chờ rồi thấy used
    results = await asyncio.gather(
        gated.gated("disburse", None)(args),
        gated.gated("disburse", None)(args),
        return_exceptions=True,
    )

    for r in results:
        assert not isinstance(r, Exception), f"KHÔNG được có exception từ race: {r}"

    def _payload(r: dict) -> dict:
        body = r["content"][0]["text"] if "content" in r else r
        return json.loads(body) if isinstance(body, str) else body

    def _is_fresh_execution(p: dict) -> bool:
        """True = lệnh này THỰC SỰ chạy inner() (claim thành công lần đầu)."""
        return p.get("disbursed") is True and "đã thực thi trước đó" not in p.get("hint", "").lower()

    def _is_cached_receipt(p: dict) -> bool:
        """True = lệnh này thấy biên nhận CŨ (bước 1), KHÔNG chạy lại inner()."""
        return p.get("disbursed") is True and "đã thực thi trước đó" in p.get("hint", "").lower()

    payloads = [_payload(r) for r in results]
    fresh_count = sum(1 for p in payloads if _is_fresh_execution(p))
    cached_count = sum(1 for p in payloads if _is_cached_receipt(p))
    assert fresh_count == 1, (
        f"INVARIANT TIỀN: đúng 1 trong 2 lệnh phải THỰC SỰ chạy inner() lần đầu — thấy {fresh_count}: {payloads}"
    )
    assert cached_count == 1, (
        f"lệnh còn lại PHẢI thấy biên nhận cũ (advisory lock chờ rồi thấy used, KHÔNG rơi bước 4 "
        f"tạo phiếu giả nữa) — thấy {cached_count}: {payloads}"
    )

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) FROM approvals WHERE conv_id=%s AND action='disburse' AND status='used'",
            (TEST_CONV_ID,),
        )
        used_count = cur.fetchone()[0]
        assert used_count == 1, f"INVARIANT TIỀN: đúng 1 phiếu 'used' (1 claim thành công) — thấy {used_count}"

        cur.execute(
            "SELECT count(*) FROM approvals WHERE conv_id=%s AND action='disburse'",
            (TEST_CONV_ID,),
        )
        total_count = cur.fetchone()[0]
        assert total_count == 1, (
            f"SAU FIX (D-41a advisory lock): KHÔNG được có phiếu giả nữa — tổng phải đúng 1 row, thấy {total_count}"
        )

        cur.execute("SELECT status FROM loans WHERE loan_id=%s", (TEST_LOAN_ID,))
        assert cur.fetchone()[0] == "disbursed", "loans.status phải chuyển đúng 1 lần, không revert"
    finally:
        conn.close()

    cards = await store.list_cards(TEST_CONV_ID)
    approval_cards = [c for c in cards if c["type"] == "approval"]
    assert len(approval_cards) == 1, f"SAU FIX: KHÔNG được có card approval giả — thấy {len(approval_cards)}"


# ═════════════════════════════════════════════════════════════════════════════════════════
# Defensive: disburse loan không tồn tại → error 4-field (không traceback agent)
# ═════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_disburse_nonexistent_loan_returns_4field_error_not_traceback():
    """loan_id không tồn tại trong seed → error 4-field {code,message,hint,retryable}, KHÔNG
    traceback lộ ra agent (lab-joint bẫy→rule: 'Trả traceback cho agent để dễ debug — CẤM')."""
    from app.orch import gated, registry

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": "L-KHONG-TON-TAI-999", "amount": TEST_AMOUNT}

    # Nhánh 4 (chưa phiếu) sẽ tạo pending TRƯỚC KHI kiểm tra loan tồn tại hay không (theo #11 —
    # validate loan tồn tại có thể ở bước tạo phiếu HOẶC ở lúc inner() chạy sau duyệt; điều
    # chỉnh test khi biết chính xác backend đặt check ở đâu). Test placeholder — cần Exports thật.
    result = await gated.gated("disburse", None)(args)
    body = result["content"][0]["text"] if "content" in result else result
    payload = json.loads(body) if isinstance(body, str) else body
    assert set(payload.keys()) >= {"code", "message"}, f"phải là error 4-field, không traceback: {payload}"


# ═════════════════════════════════════════════════════════════════════════════════════════
# Card approval + SSE — vỏ tự sinh (type='approval', NGOÀI present enum — SPEC §6)
# ═════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_card_approval_auto_generated_by_vo_not_via_present_tool():
    """Card approval (type='approval') PHẢI do VỎ tự sinh khi tạo phiếu pending (bước 4) —
    KHÔNG qua present-tool (agent không tự present được type này — 'approval' NGOÀI enum
    present hợp lệ, SPEC §6 + N2: agent không tự mở két bằng lời dặn)."""
    from app.orch import gated, registry, store

    registry.CTX_CONV.set(TEST_CONV_ID)
    args = {"loan_id": TEST_LOAN_ID, "amount": TEST_AMOUNT}

    await gated.gated("disburse", None)(args)

    cards = await store.list_cards(TEST_CONV_ID)
    approval_cards = [c for c in cards if c["type"] == "approval"]
    assert len(approval_cards) == 1, f"phải có đúng 1 card approval tự sinh: {cards}"
    card = approval_cards[0]
    assert "options" in card or "items" in card, f"card approval phải có options Duyệt/Từ chối: {card}"
    # Mặt model không thấy phiếu-id trên PROMPT — nhưng card DB có id vỏ-inject (khác chuyện —
    # id card là để FE bấm nút, không phải id lộ ra agent). Không assert nhầm 2 khái niệm.
