"""[BACKEND] Test T3-2: decide atomic + list_pending + API 400/404/409 + đánh thức main + prompt.

decide atomic (pending→approved, 2 lần→None). API qua TestClient (flag OFF → require_admin cần
cookie admin; dùng login). Đánh thức reuse handle_room_event (mock turn_runner).
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.db.config import DATABASE_URL
from app.main import app
from app.orch import gated, registry, room, store_approvals
from app.orch.main_prompts import _build_event_prompt
from app.sse import bus

from .conftest import requires_db, requires_test_db

client = TestClient(app)


def _admin_cookie():
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    return r.cookies


async def _make_pending(conv: str) -> str:
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    bus.subscribe(conv)
    _set_loan("L001", "active")
    await gated.gated("disburse", None)({"loan_id": "L001", "amount": 5000000000})
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM approvals WHERE conv_id=%s AND status='pending'", (conv,))
            return str(cur.fetchone()[0])
    finally:
        conn.close()


def _set_loan(lid: str, st: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE loans SET status=%s WHERE loan_id=%s", (st, lid))
        conn.commit()
    finally:
        conn.close()


# ── prompt approval_decided (không cần DB) ──────────────────────────────────


def test_prompt_approved_says_action_not_ticket_id():
    p = _build_event_prompt(
        "approval_decided",
        {"action": "disburse", "decision": "approved", "payload": {"loan_id": "L001", "amount": 5000000000}},
    )
    assert "DUYỆT" in p and "giao lại" in p and "operations" in p
    assert "approval_id" not in p  # §15 — không phiếu-id trên mặt model


def test_prompt_rejected_says_no_execute():
    p = _build_event_prompt(
        "approval_decided",
        {"action": "disburse", "decision": "rejected", "payload": {"loan_id": "L001"}},
    )
    assert "TỪ CHỐI" in p and "KHÔNG thực thi" in p


def test_prompt_rejected_with_reason_verbatim():
    """DF-B-07: reason có → chèn NGUYÊN VĂN + lệnh truyền đạt cho khách (không diễn dịch)."""
    p = _build_event_prompt(
        "approval_decided",
        {
            "action": "disburse",
            "decision": "rejected",
            "payload": {"loan_id": "L001"},
            "reason": "DSCR dưới ngưỡng 1.2, cần bổ sung tài sản đảm bảo",
        },
    )
    assert "TỪ CHỐI" in p and "KHÔNG thực thi" in p
    assert "DSCR dưới ngưỡng 1.2, cần bổ sung tài sản đảm bảo" in p  # reason nguyên văn trong prompt
    assert "NGUYÊN VĂN" in p  # lệnh MAIN không diễn dịch lại


def test_prompt_rejected_no_reason_no_none():
    """reason None/rỗng → prompt KHÔNG in 'None', dùng câu 'không ghi lý do cụ thể'."""
    for data in (
        {"action": "disburse", "decision": "rejected", "payload": {"loan_id": "L001"}},  # thiếu key
        {"action": "disburse", "decision": "rejected", "payload": {"loan_id": "L001"}, "reason": None},
        {"action": "disburse", "decision": "rejected", "payload": {"loan_id": "L001"}, "reason": "  "},  # whitespace
    ):
        p = _build_event_prompt("approval_decided", data)
        assert "TỪ CHỐI" in p and "None" not in p
        assert "không ghi lý do" in p


def test_valid_decision():
    assert store_approvals.valid_decision("approved")
    assert store_approvals.valid_decision("rejected")
    assert not store_approvals.valid_decision("maybe")


# ── decide atomic (cần DB) ──────────────────────────────────────────────────


@requires_db
@pytest.mark.asyncio
async def test_decide_atomic_pending_to_approved():
    conv = f"appr-decide-{uuid4()}"
    aid = await _make_pending(conv)
    decided = await store_approvals.decide(aid, "approved", "admin", "duyệt")
    assert decided is not None
    assert decided["status"] == "approved"
    assert decided["decided_by"] == "admin"
    assert decided["reason"] == "duyệt"
    assert decided["conv_id"] == conv


@requires_db
@pytest.mark.asyncio
async def test_decide_twice_second_none_no_double_wake():
    conv = f"appr-twice-{uuid4()}"
    aid = await _make_pending(conv)
    d1 = await store_approvals.decide(aid, "approved", "admin", None)
    d2 = await store_approvals.decide(aid, "approved", "admin2", None)
    assert d1 is not None
    assert d2 is None  # atomic — phiếu không còn pending → 409, không đánh thức lần 2


@requires_db
@pytest.mark.asyncio
async def test_decide_rejected():
    conv = f"appr-rej-{uuid4()}"
    aid = await _make_pending(conv)
    decided = await store_approvals.decide(aid, "rejected", "admin", "không đủ điều kiện")
    assert decided["status"] == "rejected"


@requires_db
@pytest.mark.asyncio
async def test_list_pending():
    conv = f"appr-list-{uuid4()}"
    aid = await _make_pending(conv)
    pend = await store_approvals.list_pending(conv)
    assert len(pend) == 1
    assert pend[0]["id"] == aid
    assert pend[0]["status"] == "pending"


@requires_db
@pytest.mark.asyncio
async def test_approval_exists():
    conv = f"appr-exist-{uuid4()}"
    aid = await _make_pending(conv)
    assert await store_approvals.approval_exists(aid)
    assert not await store_approvals.approval_exists("00000000-0000-0000-0000-000000000000")


# ── đánh thức main reuse handle_room_event ──────────────────────────────────


@pytest.mark.asyncio
async def test_emit_and_wake_reuses_handle_room_event():
    registry.reset_room("wake-t32")
    seen = []

    async def tr(conv_id, event, data):
        seen.append((event, data.get("action"), data.get("decision")))

    room.set_turn_runner(tr)
    try:
        from app.api.approvals import _emit_and_wake

        _emit_and_wake(
            {
                "id": "a1",
                "conv_id": "wake-t32",
                "action": "disburse",
                "status": "approved",
                "decided_by": "admin",
                "reason": None,
                "payload": {"loan_id": "L001"},
            }
        )
        await asyncio.sleep(0.05)
        assert seen == [("approval_decided", "disburse", "approved")]
    finally:
        room.set_turn_runner(None)
        registry.reset_room("wake-t32")


@pytest.mark.asyncio
async def test_emit_and_wake_carries_reason_in_payload():
    """DF-B-07: reason của quyết định phải ĐI KÈM wake payload (đứt mạch trước đây)."""
    registry.reset_room("wake-reason")
    captured = {}

    async def tr(conv_id, event, data):
        captured.update(data)

    room.set_turn_runner(tr)
    try:
        from app.api.approvals import _emit_and_wake

        _emit_and_wake(
            {
                "id": "a2",
                "conv_id": "wake-reason",
                "action": "disburse",
                "status": "rejected",
                "decided_by": "admin",
                "reason": "Vượt hạn mức chi nhánh",
                "payload": {"loan_id": "L001"},
            }
        )
        await asyncio.sleep(0.05)
        assert captured.get("reason") == "Vượt hạn mức chi nhánh"  # reason nối vào payload wake
        assert captured.get("decision") == "rejected"
    finally:
        room.set_turn_runner(None)
        registry.reset_room("wake-reason")


# ── API 400/404/409 (cần DB + admin cookie) ─────────────────────────────────


@requires_db
def test_api_decide_bad_decision_400():
    cookies = _admin_cookie()
    r = client.post(f"/api/approvals/{uuid4()}/decide", json={"decision": "maybe"}, cookies=cookies)
    assert r.status_code == 400
    assert r.json()["code"] == "bad_decision"


@requires_db
def test_api_decide_not_found_404():
    cookies = _admin_cookie()
    r = client.post(f"/api/approvals/{uuid4()}/decide", json={"decision": "approved"}, cookies=cookies)
    assert r.status_code == 404
    assert r.json()["code"] == "not_found"


@requires_db
def test_api_decide_malformed_uuid_404_not_500():
    """approval_id KHÔNG phải UUID (input rác) → 404 (KHÔNG 500). rà 3-API T4-3: _decide_sync raise
    InvalidTextRepresentation lọt 500 → giờ catch → None → _exists (cũng catch) → 404."""
    cookies = _admin_cookie()
    r = client.post("/api/approvals/nonexistent-xyz/decide", json={"decision": "approved"}, cookies=cookies)
    assert r.status_code == 404, f"malformed approval_id PHẢI 404 không 500 — thấy {r.status_code}"
    assert r.json()["code"] == "not_found"


@requires_db
@pytest.mark.asyncio
async def test_api_decide_already_decided_409():
    conv = f"appr-409-{uuid4()}"
    aid = await _make_pending(conv)
    await store_approvals.decide(aid, "approved", "admin", None)  # quyết trước
    cookies = _admin_cookie()
    r = client.post(f"/api/approvals/{aid}/decide", json={"decision": "approved"}, cookies=cookies)
    assert r.status_code == 409
    assert r.json()["code"] == "approval_already_decided"


def test_api_list_bad_status_400():
    cookies = _admin_cookie()
    r = client.get("/api/approvals?status=used", cookies=cookies)
    assert r.status_code == 400
    assert r.json()["code"] == "bad_status"


def test_api_approvals_requires_auth_no_cookie_401():
    # no cookie (flag OFF) → 401. Client RIÊNG (TestClient cookie persist giữa test — dùng client
    # sạch để no-cookie thật, không dính cookie từ test khác).
    fresh = TestClient(app)
    r = fresh.get("/api/approvals")
    assert r.status_code == 401


@requires_db
@requires_db
def test_api_approvals_customer_forbidden_D56():
    """D-56 (ĐẢO D-54): duyệt = việc NGÂN HÀNG (admin). Customer/user gọi → 403 forbidden 4-field.
    App = cửa khách: khách chat, agent auto-duyệt nhỏ, lớn bắn NGÂN HÀNG duyệt."""
    r = client.post("/api/auth/login", json={"username": "c001", "password": "c001"})
    if r.status_code != 200:
        pytest.skip("seed customer account chưa có")
    r2 = client.get("/api/approvals?status=pending", cookies=r.cookies)
    assert r2.status_code == 403  # customer KHÔNG duyệt được (D-56 — việc ngân hàng)
    assert r2.json()["code"] == "forbidden"


@pytest.mark.asyncio
async def test_emit_and_wake_guarded_logs_not_swallow(caplog):
    """Fix nhất quán _report: handle_room_event raise trong resume → log lỗi (KHÔNG nuốt im,
    KHÔNG treo API). stub turn_runner raise → _emit_and_wake không nổ ra ngoài, log có dòng lỗi."""
    import logging

    registry.reset_room("wake-err")

    async def boom_runner(conv_id, event, data):
        raise RuntimeError("resume nổ demo")

    room.set_turn_runner(boom_runner)
    try:
        from app.api.approvals import _emit_and_wake

        with caplog.at_level(logging.ERROR, logger="api.approvals"):
            _emit_and_wake(
                {
                    "id": "a1",
                    "conv_id": "wake-err",
                    "action": "disburse",
                    "status": "approved",
                    "decided_by": "admin",
                    "reason": None,
                    "payload": {"loan_id": "L001"},
                }
            )
            await asyncio.sleep(0.05)  # cho _wake_guarded chạy + log
        assert any("resume approval_decided lỗi" in r.message for r in caplog.records), (
            "resume fail phải log (không nuốt im)"
        )
    finally:
        room.set_turn_runner(None)
        registry.reset_room("wake-err")


def _payload(env: dict) -> dict:
    return json.loads(env["content"][0]["text"])


# ── DF-B-01: enrich hàng chờ duyệt (display object) — cán bộ thấy tên khách + số + lane ──


def _mk_pending_raw(conv: str, payload: dict, action: str = "disburse") -> str:
    """INSERT thẳng 1 phiếu pending với payload cho trước (KHÔNG qua money-path — test enrich đọc).
    action mặc định 'disburse' (backward); T12-5 FAIL C truyền 'ops_disburse' để test enrich key mới.
    payload_hash unique để không đụng constraint. Trả approval id."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO approvals (conv_id, action, payload, payload_hash, status) "
                "VALUES (%s,%s,%s,%s,'pending') RETURNING id",
                (conv, action, json.dumps(payload), "dfb01_" + uuid4().hex[:12]),
            )
            return str(cur.fetchone()[0])
    finally:
        conn.close()


def _seed_assessment(owner_id: str, lane: str) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO assessments (owner_id, lane, loan_amount_vnd, criteria_json, created_at) "
                "VALUES (%s,%s,%s,'[]',now()::text) RETURNING id",
                (owner_id, lane, 100_000_000),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def _rm_dfb01(conv: str, owners: tuple[str, ...] = ()) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM approvals WHERE conv_id=%s", (conv,))
        for o in owners:
            cur.execute("DELETE FROM assessments WHERE owner_id=%s", (o,))
    conn.close()


@requires_test_db
@pytest.mark.asyncio
async def test_enrich_display_real_loan_full_5_fields():
    """(a) Phiếu có loan THẬT (L001→C001) + assessment → display đủ 5 field, không null."""
    lane_id = _seed_assessment("C001", "green")
    aid = _mk_pending_raw("dfb01a", {"loan_id": "L001", "amount": 5000000000})
    try:
        rows = await store_approvals.list_pending("dfb01a")
        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == aid
        # field cũ giữ nguyên (không phá contract cũ)
        assert row["payload"] == {"loan_id": "L001", "amount": 5000000000}
        assert row["status"] == "pending"
        d = row["display"]
        assert set(d) == {"customer_name", "owner_id", "loan_id", "amount_vnd", "lane"}
        assert d["customer_name"] == "Nguyễn Văn An"  # L001 → C001 → full_name
        assert d["owner_id"] == "C001"
        assert d["loan_id"] == "L001"
        assert d["amount_vnd"] == 5000000000  # int
        assert d["lane"] == "green"  # assessment mới nhất của C001
    finally:
        _rm_dfb01("dfb01a")
        _cleanup_assessment(lane_id)


@requires_db
@pytest.mark.asyncio
async def test_enrich_display_loan_id_is_owner_fallback():
    """(b) Edge tester: loan_id="C001" (owner nhét vào loan_id) → loans MISS → fallback customers.id.
    customer_name điền được, loan_id GIỮ giá trị gốc "C001"."""
    aid = _mk_pending_raw("dfb01b", {"loan_id": "C001", "amount": 300000000})
    try:
        rows = await store_approvals.list_pending("dfb01b")
        d = next(r for r in rows if r["id"] == aid)["display"]
        assert d["customer_name"] == "Nguyễn Văn An"  # fallback customers.id=C001
        assert d["owner_id"] == "C001"
        assert d["loan_id"] == "C001"  # GIỮ nguyên giá trị gốc, không đổi
        assert d["amount_vnd"] == 300000000
    finally:
        _rm_dfb01("dfb01b")


@requires_db
@pytest.mark.asyncio
async def test_enrich_display_ops_disburse_application_id_amount_vnd():
    """T12-5 FAIL C regression: phiếu ops_disburse (application_id/amount_vnd — KHÁC key disburse cũ)
    → display KHÔNG null (COALESCE key + JOIN applications.owner). Trước fix: toàn null."""
    aid = _mk_pending_raw(
        "dfb01ops", {"application_id": "APP01", "amount_vnd": 250000000}, action="ops_disburse"
    )
    try:
        rows = await store_approvals.list_pending("dfb01ops")
        d = next(r for r in rows if r["id"] == aid)["display"]
        assert d["customer_name"] == "Phạm Thị Dung"  # APP01 → applications.owner=C004 → full_name
        assert d["owner_id"] == "C004"
        assert d["loan_id"] == "APP01"  # ref_id = application_id (COALESCE)
        assert d["amount_vnd"] == 250000000  # amount_vnd (COALESCE với amount)
    finally:
        _rm_dfb01("dfb01ops")


@requires_db
@pytest.mark.asyncio
async def test_enrich_display_garbage_payload_all_null_no_500():
    """(c) payload rác (amount không phải số / thiếu key / payload rỗng) → display toàn null, KHÔNG 500."""
    a_bad_amt = _mk_pending_raw("dfb01c", {"loan_id": "L001", "amount": "notanumber"})
    a_empty = _mk_pending_raw("dfb01c", {})
    a_no_loan = _mk_pending_raw("dfb01c", {"amount": 123})
    try:
        rows = await store_approvals.list_pending("dfb01c")
        by_id = {r["id"]: r["display"] for r in rows}
        # amount rác → amount_vnd null NHƯNG customer vẫn resolve (loan L001 thật)
        assert by_id[a_bad_amt]["amount_vnd"] is None
        assert by_id[a_bad_amt]["customer_name"] == "Nguyễn Văn An"
        # payload rỗng → toàn null
        assert all(by_id[a_empty][k] is None for k in ("customer_name", "owner_id", "loan_id", "amount_vnd", "lane"))
        # thiếu loan_id → tên/owner null, amount vẫn cast được
        assert by_id[a_no_loan]["customer_name"] is None
        assert by_id[a_no_loan]["loan_id"] is None
        assert by_id[a_no_loan]["amount_vnd"] == 123
    finally:
        _rm_dfb01("dfb01c")


@requires_db
@pytest.mark.asyncio
async def test_enrich_orphan_loan_owner_not_customer_name_null():
    """Defensive: loan mồ côi (owner không có trong customers) → owner_id có, customer_name null."""
    # tạo loan mồ côi owner giả
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO loans (loan_id, owner_id, principal, outstanding, monthly_payment, status) "
            "VALUES ('LDFB1','GHOST_OWNER',1,1,1,'active') ON CONFLICT (loan_id) DO NOTHING"
        )
    conn.close()
    aid = _mk_pending_raw("dfb01d", {"loan_id": "LDFB1", "amount": 1})
    try:
        d = next(r for r in (await store_approvals.list_pending("dfb01d")) if r["id"] == aid)["display"]
        assert d["owner_id"] == "GHOST_OWNER"  # loan tồn tại → owner_id có
        assert d["customer_name"] is None  # owner không trong customers → name null
    finally:
        _rm_dfb01("dfb01d")
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        conn.cursor().execute("DELETE FROM loans WHERE loan_id='LDFB1'")
        conn.close()


@requires_db
def test_enrich_api_endpoint_returns_display():
    """(d) qua API TestClient (require_admin) — phiếu có display, field cũ nguyên vẹn."""
    aid = _mk_pending_raw("dfb01e", {"loan_id": "L001", "amount": 5000000000})
    try:
        r = client.get("/api/approvals?status=pending", cookies=_admin_cookie())
        assert r.status_code == 200
        rows = r.json()
        row = next(x for x in rows if x["id"] == aid)
        assert "display" in row and row["display"]["customer_name"] == "Nguyễn Văn An"
        # field cũ vẫn còn (không phá contract cũ)
        assert row["payload"] == {"loan_id": "L001", "amount": 5000000000}
        assert row["status"] == "pending" and "payload_hash" in row
    finally:
        _rm_dfb01("dfb01e")


def _cleanup_assessment(aid: int) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    conn.cursor().execute("DELETE FROM assessments WHERE id=%s", (aid,))
    conn.close()
