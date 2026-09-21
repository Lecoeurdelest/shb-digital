from __future__ import annotations

from pathlib import Path

from app.db.seed_from_lab import LAB_SEED_DB, SNAPSHOT_SEED_DB, _resolve_seed_db

from .conftest import requires_db, requires_test_db


def test_snapshot_seed_db_exists_in_repo():

    assert SNAPSHOT_SEED_DB.exists(), "Expected invariant was not satisfied at source line 12."
    assert SNAPSHOT_SEED_DB.name == "shb-132.db"


def test_resolve_seed_db_prefers_lab_when_present(monkeypatch):

    monkeypatch.setattr(Path, "exists", lambda self: True)
    assert _resolve_seed_db() == LAB_SEED_DB


def test_resolve_seed_db_falls_back_to_snapshot(monkeypatch):

    orig = Path.exists
    monkeypatch.setattr(Path, "exists", lambda self: False if self == LAB_SEED_DB else orig(self))
    assert _resolve_seed_db() == SNAPSHOT_SEED_DB


@requires_test_db
def test_seed_if_empty_skips_when_data_present():

    from app.db.seed_if_empty import _has_business_data, seed_if_empty

    assert _has_business_data() is True
    assert seed_if_empty() is False  # SKIP


@requires_db
def test_has_business_data_false_on_bad_db(monkeypatch):

    import app.db.seed_if_empty as sie

    assert sie._has_business_data("postgresql://bad:bad@localhost:1/nope") is False
