from __future__ import annotations

import json

from .conftest import requires_db


def _payload(sdk_result: dict) -> dict:

    return json.loads(sdk_result["content"][0]["text"])


def test_retrieval_pack_registry_and_schema_shape():
    from roles._retrieval import functions as R

    names = {"wiki_lookup", "wiki_search", "wiki_related_docs", "notes_search", "legal_related_exposure"}
    assert set(R.REGISTRY_RETRIEVAL) == names
    assert set(R.SCHEMAS_RETRIEVAL) == names
    assert set(R.ANNOTATIONS_RETRIEVAL) == names

    assert all(a["readOnlyHint"] for a in R.ANNOTATIONS_RETRIEVAL.values())

    for spec in R.SCHEMAS_RETRIEVAL.values():
        assert "m\u00f4 t\u1ea3" in spec and "params" in spec


def test_common_server_mounts_wiki_notes_not_legal_exposure():

    from app.orch.common_tools import COMMON_ALLOWED

    for n in ("wiki_lookup", "wiki_search", "wiki_related_docs", "notes_search"):
        assert f"mcp__common__{n}" in COMMON_ALLOWED
    assert "mcp__common__legal_related_exposure" not in COMMON_ALLOWED


def test_legal_toolpack_mounts_related_exposure_readonly():

    from roles.legal import functions as L

    assert "legal_related_exposure" in L.REGISTRY
    assert L.SCHEMAS["legal_related_exposure"]["m\u00f4 t\u1ea3"]
    assert L.ANNOTATIONS["legal_related_exposure"]["readOnlyHint"] is True
    assert "legal_related_exposure" not in L.WRITE_TOOLS
    assert L.WRITE_TOOLS == {"legal_classify_profile"}


def test_mount_legal_exposes_exposure_as_sdk_tool():
    from app.mount.mount_role import mount_role

    _, _, allowed = mount_role("legal")
    assert "mcp__banking_legal__legal_related_exposure" in allowed


@requires_db
def test_seam_missing_table_4field_not_crash():

    import inspect

    from app.mount.mount_role import _text, run_labpack_fn

    def _probe(conn, page: str):
        return {
            "rows": [dict(r) for r in conn.execute("SELECT * FROM __no_such_table__ WHERE x=?", (page,)).fetchall()]
        }

    known = set(inspect.signature(_probe).parameters) - {"conn"}
    out = _payload(_text(run_labpack_fn(_probe, "_probe", {"page": "x"}, known, "", apply_read_scope=False)))
    assert set(out) >= {"code", "message", "hint", "retryable"}
    assert out["code"] == "db_error"
    assert out["retryable"] is True


@requires_db
def test_wiki_lookup_returns_real_data_after_t122_seed():

    import inspect

    from roles._retrieval import functions as R

    from app.mount.mount_role import _sig_hint, _text, run_labpack_fn

    fn = R.REGISTRY_RETRIEVAL["wiki_lookup"]
    known = set(inspect.signature(fn).parameters) - {"conn"}
    hint = _sig_hint(R.SCHEMAS_RETRIEVAL, "wiki_lookup")
    out = _payload(
        _text(run_labpack_fn(fn, "wiki_lookup", {"page": "tran-cho-vay"}, known, hint, apply_read_scope=False))
    )
    assert out.get("found") is True
    assert out["citation"]["page"] == "tran-cho-vay"
    assert out.get("body")


@requires_db
def test_bad_param_blocked_4field():

    import inspect

    from roles._retrieval import functions as R

    from app.mount.mount_role import _sig_hint, _text, run_labpack_fn

    fn = R.REGISTRY_RETRIEVAL["wiki_search"]
    known = set(inspect.signature(fn).parameters) - {"conn"}
    hint = _sig_hint(R.SCHEMAS_RETRIEVAL, "wiki_search")
    out = _payload(
        _text(run_labpack_fn(fn, "wiki_search", {"q": "x", "bogus": 1}, known, hint, apply_read_scope=False))
    )
    assert out["code"] == "bad_param"
    assert "bogus" in out["message"]


def test_notes_search_env_missing_when_no_numpy(monkeypatch):

    from roles._retrieval import functions as R

    monkeypatch.setattr(R, "np", None)
    out = R.notes_search(None, query="cash-flow difficulties")
    assert out["code"] == "env_missing"
    assert out["retryable"] is False
