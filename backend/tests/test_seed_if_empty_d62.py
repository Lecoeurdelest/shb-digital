"""[BACKEND] Test D-62 — seed_if_empty (deploy entrypoint) + fallback chain seed source.

- seed_if_empty: DB có nghiệp vụ → SKIP (giữ khách C9xx — gate S10 session-bền) · DB rỗng → seed.
- _resolve_seed_db: LAB sibling tồn tại → LAB (dev) · không → snapshot repo (deploy).
"""

from __future__ import annotations

from pathlib import Path

from app.db.seed_from_lab import LAB_SEED_DB, SNAPSHOT_SEED_DB, _resolve_seed_db

from .conftest import requires_db, requires_test_db


def test_snapshot_seed_db_exists_in_repo():
    """Snapshot D-62 có trong repo (deploy tự chứa seed)."""
    assert SNAPSHOT_SEED_DB.exists(), f"snapshot seed thiếu: {SNAPSHOT_SEED_DB}"
    assert SNAPSHOT_SEED_DB.name == "shb-132.db"


def test_resolve_seed_db_prefers_lab_when_present(monkeypatch):
    """LAB sibling tồn tại → dùng LAB (dev — nguồn sự thật, hành vi cũ)."""
    monkeypatch.setattr(Path, "exists", lambda self: True)  # giả LAB tồn tại
    assert _resolve_seed_db() == LAB_SEED_DB


def test_resolve_seed_db_falls_back_to_snapshot(monkeypatch):
    """LAB sibling KHÔNG tồn tại → rơi vào snapshot (deploy VM clone-trần)."""
    # chỉ LAB_SEED_DB.exists() False; snapshot vẫn thật
    orig = Path.exists
    monkeypatch.setattr(Path, "exists", lambda self: False if self == LAB_SEED_DB else orig(self))
    assert _resolve_seed_db() == SNAPSHOT_SEED_DB


@requires_test_db  # seed (TRUNCATE+INSERT) → test-db riêng (siết assessments-write pattern)
def test_seed_if_empty_skips_when_data_present():
    """DB đã seed (assumptions>0) → seed_if_empty SKIP (không wipe — gate session-bền)."""
    from app.db.seed_if_empty import _has_business_data, seed_if_empty

    # conftest đã seed shb_test2 → có nghiệp vụ
    assert _has_business_data() is True
    assert seed_if_empty() is False  # SKIP


@requires_db
def test_has_business_data_false_on_bad_db(monkeypatch):
    """DB lỗi/không kết nối → _has_business_data False (để seed thử, không crash entrypoint)."""
    import app.db.seed_if_empty as sie

    assert sie._has_business_data("postgresql://bad:bad@localhost:1/nope") is False
