"""[BACKEND] Test T7-3 — MA TRẬN 3 TẦNG verdict-aware wire assessments vào phanh disburse (D-52/D-56).

- disburse_decision unit (3 tầng × verdict) — auto/human đúng ma trận.
- BACKWARD KEY: assessments RỖNG → hành vi Y HỆT (L006<500tr auto · L007≥500tr người).
- Seed assessment green → tầng-2 auto (reason dẫn #id) · red → chặn tầng-1 · yellow → người.
- Boundary chính xác: 500tr → tầng 2, 2e9 → tầng 2, 2e9+1 → tầng 3.
- DB-error path (conn riêng — không poison gated tx) không crash.
- Rider reset_demo wipe conversation dirs (giữ CONV_ROOT).

Verdict đọc conn RIÊNG (không cùng gated tx) — DB lỗi verdict KHÔNG abort tx phiếu-người.
"""

from __future__ import annotations

from datetime import UTC

import psycopg2

from app.db.config import DATABASE_URL
from app.orch.verdict import AUTO_APPROVE_THRESHOLD, disburse_decision, latest_verdict

from .conftest import requires_db

# ── helpers ──────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    """created_at ĐÚNG format LAB (_now isoformat 'T' separator) — KHÔNG dùng now()::text (space
    separator sort lexical SAI: ' '(0x20) < 'T'(0x54) → space-row luôn cũ hơn T-row bất kể giờ
    thật). Prod mọi row qua LAB _now() nên nhất quán; test phải khớp format để ORDER BY đúng."""
    from datetime import datetime

    return datetime.now(UTC).isoformat(timespec="seconds")


def _seed_assessment(owner_id: str, lane: str) -> int:
    """Seed 1 assessment (chỉ lane — D-59: assessments KHÔNG có cột decision, LAB suy từ lane)."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO assessments(owner_id, lane, loan_amount_vnd, created_at) "
                "VALUES(%s,%s,%s,%s) RETURNING id",
                (owner_id, lane, 300_000_000, _now_iso()),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def _rm_assessments(owner_id: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM assessments WHERE owner_id=%s", (owner_id,))
    conn.close()


def _owner_of(loan_id: str) -> str:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT owner_id FROM loans WHERE loan_id=%s", (loan_id,))
            return cur.fetchone()[0]
    finally:
        conn.close()


class _FakeConn:
    """conn giả cho disburse_decision — auto_approve_max đọc assumptions; trả 2e9 để test tầng."""

    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *a):
            self._done = True

        def fetchone(self):
            return ("2000000000",)  # auto_approve_max_vnd = 2e9

    def cursor(self, *a, **k):
        return self._Cur()


# ── 1. disburse_decision unit — 3 tầng × verdict (không cần loan lookup: dùng amount + conn giả) ──


def test_tier1_no_verdict_auto():
    """Tầng 1 (amount < 500tr) không verdict → auto (như T5-2' cũ)."""
    d, reason = disburse_decision(_FakeConn(), {"loan_id": "NOEXIST_LOAN_T73", "amount": 300_000_000})
    assert d == "auto"
    assert "ngưỡng" in reason  # reason cũ byte-identical (test cũ assert 'ngưỡng')


def test_tier3_above_max_always_human():
    """Tầng 3 (amount > 2e9) → luôn người, bất kể (không loan → no verdict)."""
    d, reason = disburse_decision(_FakeConn(), {"loan_id": "NOEXIST_LOAN_T73", "amount": 2_000_000_001})
    assert d == "human"
    assert reason is None


def test_tier2_no_verdict_human():
    """Tầng 2 (500tr ≤ amount ≤ 2e9) không verdict → người (pain D-52: cần XANH mới auto)."""
    d, _ = disburse_decision(_FakeConn(), {"loan_id": "NOEXIST_LOAN_T73", "amount": 700_000_000})
    assert d == "human"


def test_amount_missing_human():
    """amount thiếu/không parse → người (an toàn, không auto oan)."""
    assert disburse_decision(_FakeConn(), {"loan_id": "X"})[0] == "human"
    assert disburse_decision(_FakeConn(), {"loan_id": "X", "amount": "abc"})[0] == "human"


def test_boundary_500tr_is_tier2():
    """amount == 500tr (ngưỡng dưới) → tầng 2 (không < threshold) → người khi không verdict."""
    d, _ = disburse_decision(_FakeConn(), {"loan_id": "NOEXIST_LOAN_T73", "amount": AUTO_APPROVE_THRESHOLD})
    assert d == "human"  # == threshold KHÔNG < threshold → tầng 2


def test_boundary_2e9_is_tier2_not_tier3():
    """amount == 2e9 (ngưỡng trên) → tầng 2 (≤ max), KHÔNG tầng 3."""
    d, _ = disburse_decision(_FakeConn(), {"loan_id": "NOEXIST_LOAN_T73", "amount": 2_000_000_000})
    assert d == "human"  # tầng 2 no-verdict → người (không crash sang tầng 3 logic)


def test_boundary_2e9_plus_1_is_tier3():
    """amount == 2e9+1 → tầng 3 → người."""
    d, r = disburse_decision(_FakeConn(), {"loan_id": "NOEXIST_LOAN_T73", "amount": 2_000_000_001})
    assert d == "human" and r is None


# ── 2. verdict-aware trên loan THẬT (requires_db) ────────────────────────────


@requires_db
def test_tier2_green_verdict_auto_reason_id():
    """Owner L007 có assessment GREEN/auto_eligible → tầng-2 (700tr) AUTO + reason dẫn #id."""
    owner = _owner_of("L007")
    aid = _seed_assessment(owner, "green")
    try:
        d, reason = disburse_decision(_FakeConn(), {"loan_id": "L007", "amount": 700_000_000})
        assert d == "auto"
        assert f"#{aid}" in reason and "XANH" in reason
    finally:
        _rm_assessments(owner)


@requires_db
def test_tier2_green_but_above_max_human():
    """Green NHƯNG amount > 2e9 → tầng 3 → người (green không cứu tầng 3)."""
    owner = _owner_of("L007")
    _seed_assessment(owner, "green")
    try:
        d, _ = disburse_decision(_FakeConn(), {"loan_id": "L007", "amount": 3_000_000_000})
        assert d == "human"
    finally:
        _rm_assessments(owner)


@requires_db
def test_tier1_red_verdict_blocks_auto():
    """Tầng 1 (300tr) NHƯNG verdict RED → chặn auto → người (thắt chặt có bằng chứng xấu)."""
    owner = _owner_of("L006")
    _seed_assessment(owner, "red")
    try:
        d, _ = disburse_decision(_FakeConn(), {"loan_id": "L006", "amount": 300_000_000})
        assert d == "human"  # red chặn auto tầng-1
    finally:
        _rm_assessments(owner)


@requires_db
def test_tier1_yellow_verdict_does_not_block_auto():
    """D-59: Tầng 1 verdict YELLOW → KHÔNG chặn auto (chỉ RED chặn — bad ⟺ lane=red).

    LAB: decision=reject_recommended CHỈ đi cùng lane=red (không có yellow+reject). bad rút gọn
    về lane=red. Yellow ở tầng-1 = auto (khớp định nghĩa 'bad' dispatch — ghi rõ để không đọc nhầm
    là regression)."""
    owner = _owner_of("L006")
    _seed_assessment(owner, "yellow")
    try:
        d, reason = disburse_decision(_FakeConn(), {"loan_id": "L006", "amount": 300_000_000})
        assert d == "auto", "yellow KHÔNG chặn auto tầng-1 (chỉ red chặn)"
        assert "ngưỡng" in reason
    finally:
        _rm_assessments(owner)


@requires_db
def test_tier2_yellow_verdict_human():
    """Tầng 2 (700tr) verdict YELLOW (không green) → người."""
    owner = _owner_of("L007")
    _seed_assessment(owner, "yellow")
    try:
        d, _ = disburse_decision(_FakeConn(), {"loan_id": "L007", "amount": 700_000_000})
        assert d == "human"
    finally:
        _rm_assessments(owner)


@requires_db
def test_latest_verdict_picks_newest():
    """Nhiều assessment 1 owner → latest_verdict lấy MỚI NHẤT (created_at DESC, id DESC)."""
    owner = _owner_of("L007")
    _seed_assessment(owner, "red")
    newest = _seed_assessment(owner, "green")
    try:
        v = latest_verdict("L007")
        assert v is not None and v["id"] == newest and v["lane"] == "green"
    finally:
        _rm_assessments(owner)


@requires_db
def test_latest_verdict_no_loan_none():
    """loan không tồn tại → latest_verdict None (không crash)."""
    assert latest_verdict("NOEXIST_LOAN_ZZZ") is None


# ── 3. DB-error path (conn riêng — verdict lỗi KHÔNG poison gated tx) ─────────


def test_latest_verdict_db_error_returns_none(monkeypatch):
    """DB lỗi khi đọc verdict → None (coi như không verdict), KHÔNG raise ra ngoài."""
    import app.orch.verdict as v

    monkeypatch.setattr(v, "DATABASE_URL", "postgresql://bad:bad@localhost:1/nope")
    assert v.latest_verdict("L007") is None  # nuốt lỗi → None, không nổ


def test_disburse_decision_db_error_tier1_still_auto(monkeypatch):
    """DB lỗi verdict + tầng 1 → vẫn auto (fail về hành vi hiện hành — infra chớp không đổi hành vi)."""
    import app.orch.verdict as v

    monkeypatch.setattr(v, "DATABASE_URL", "postgresql://bad:bad@localhost:1/nope")
    d, _ = v.disburse_decision(_FakeConn(), {"loan_id": "L006", "amount": 300_000_000})
    assert d == "auto"  # verdict None (DB lỗi) → tầng 1 không bad → auto


# ── 4. Rider — reset_demo wipe conversation dirs ─────────────────────────────


@requires_db
def test_reset_demo_wipes_conversation_dirs():
    """reset_demo xoá dir con trong CONV_ROOT, GIỮ CONV_ROOT (folder neo mồ côi khỏi tích tụ)."""
    from app.orch.main_session import CONV_ROOT

    CONV_ROOT.mkdir(parents=True, exist_ok=True)
    d = CONV_ROOT / "t73-rider-fake"
    d.mkdir(exist_ok=True)
    (d / "neo.txt").write_text("x")
    from app.db.reset_demo import reset_demo

    r = reset_demo(DATABASE_URL)
    assert r["_conversation_dirs_wiped"] >= 1
    assert CONV_ROOT.exists()  # root GIỮ
    assert not d.exists()  # dir con xoá
