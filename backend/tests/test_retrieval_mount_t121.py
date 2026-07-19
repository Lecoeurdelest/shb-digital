"""[BACKEND] Test T12-1 — port retrieval toolpack (mount + shape, bảng CHƯA seed).

T12-1 chỉ CODE tool + mount (bảng = T12-2). Verify mức: (1) import sạch (server start không
crash/chậm — lazy embed import) · (2) mount đúng server (wiki/notes → common; legal_related_exposure
→ legal, read-only) · (3) schema hợp lệ · (4) bảng chưa có → error 4-field SẠCH (KHÔNG 500/crash).
run_labpack_fn seam CHUNG (KHÔNG copy-paste mount_role). read-scope OFF cho common (T12-2 lo).
"""

from __future__ import annotations

import json

from .conftest import requires_db


def _payload(sdk_result: dict) -> dict:
    """SDK tool trả {content:[{type:text,text:<json>}]} — bóc payload dict."""
    return json.loads(sdk_result["content"][0]["text"])


# ── (1) import + registry/schema shape (không cần DB) ────────────────────────


def test_retrieval_pack_registry_and_schema_shape():
    from roles._retrieval import functions as R

    names = {"wiki_lookup", "wiki_search", "wiki_related_docs", "notes_search", "legal_related_exposure"}
    assert set(R.REGISTRY_RETRIEVAL) == names
    assert set(R.SCHEMAS_RETRIEVAL) == names
    assert set(R.ANNOTATIONS_RETRIEVAL) == names
    # mọi tool read-only (retrieval toàn ĐỌC)
    assert all(a["readOnlyHint"] for a in R.ANNOTATIONS_RETRIEVAL.values())
    # schema mỗi tool có mô tả + params
    for spec in R.SCHEMAS_RETRIEVAL.values():
        assert "mô tả" in spec and "params" in spec


def test_common_server_mounts_wiki_notes_not_legal_exposure():
    """wiki_*/notes_search → common; legal_related_exposure KHÔNG ở common (thuộc legal)."""
    from app.orch.common_tools import COMMON_ALLOWED

    for n in ("wiki_lookup", "wiki_search", "wiki_related_docs", "notes_search"):
        assert f"mcp__common__{n}" in COMMON_ALLOWED
    assert "mcp__common__legal_related_exposure" not in COMMON_ALLOWED  # → toolpack legal, không common


def test_legal_toolpack_mounts_related_exposure_readonly():
    """legal_related_exposure vào REGISTRY legal, read-only, KHÔNG mở WRITE (assessments-only giữ)."""
    from roles.legal import functions as L

    assert "legal_related_exposure" in L.REGISTRY
    assert L.SCHEMAS["legal_related_exposure"]["mô tả"]
    assert L.ANNOTATIONS["legal_related_exposure"]["readOnlyHint"] is True
    assert "legal_related_exposure" not in L.WRITE_TOOLS  # read-only → WRITE whitelist KHÔNG đổi
    assert L.WRITE_TOOLS == {"legal_classify_profile"}  # duy nhất (D-55b)


def test_mount_legal_exposes_exposure_as_sdk_tool():
    from app.mount.mount_role import mount_role

    _, _, allowed = mount_role("legal")
    assert "mcp__banking_legal__legal_related_exposure" in allowed


# ── (4) bảng CHƯA seed → 4-field SẠCH, KHÔNG 500 (T12-1 bar) ─────────────────


@requires_db
def test_seam_missing_table_4field_not_crash():
    """Seam run_labpack_fn: query bảng KHÔNG tồn tại → db_error 4-field, KHÔNG 500/raise.

    T12-1 bar (bảng chưa seed → graceful). Sau T12-2 wiki_pages ĐÃ có, nên test seam bằng 1 fn
    truy vấn bảng chắc-chắn-không-tồn-tại (UndefinedTable = psycopg2.Error → db_error). Chứng minh
    cửa except psycopg2.Error của seam đỡ mọi bảng-thiếu, KHÔNG chỉ wiki."""
    import inspect

    from app.mount.mount_role import _text, run_labpack_fn

    def _probe(conn, page: str):
        return {
            "rows": [dict(r) for r in conn.execute("SELECT * FROM __no_such_table__ WHERE x=?", (page,)).fetchall()]
        }

    known = set(inspect.signature(_probe).parameters) - {"conn"}
    out = _payload(_text(run_labpack_fn(_probe, "_probe", {"page": "x"}, known, "", apply_read_scope=False)))
    assert set(out) >= {"code", "message", "hint", "retryable"}
    assert out["code"] == "db_error"  # UndefinedTable → db_error 4-field, không stacktrace
    assert out["retryable"] is True


@requires_db
def test_wiki_lookup_returns_real_data_after_t122_seed():
    """T12-2: wiki_pages ĐÃ seed → wiki_lookup('tran-cho-vay') trả found=True + citation + body thật."""
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
    assert out.get("body")  # nội dung thật


@requires_db
def test_bad_param_blocked_4field():
    """param lạ → bad_param 4-field (lab-joint §2 param-nuốt) — không lọt vào fn."""
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
    """notes_search KHÔNG có numpy → env_missing 4-field (LAB behavior giữ nguyên). Không cần DB —
    guard np is None chạy TRƯỚC mọi query."""
    from roles._retrieval import functions as R

    monkeypatch.setattr(R, "np", None)
    out = R.notes_search(None, query="khó khăn dòng tiền")  # conn không dùng tới (np None trả sớm)
    assert out["code"] == "env_missing"
    assert out["retryable"] is False
