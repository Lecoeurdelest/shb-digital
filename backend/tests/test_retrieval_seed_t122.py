from __future__ import annotations

import inspect

import numpy as np
import psycopg2

from app.db.config import DATABASE_URL
from app.mount.mount_role import _sig_hint, _text, run_labpack_fn
from app.mount.pg_adapter import PGConnAdapter, acquire, release

from .conftest import requires_db, requires_embed


def _payload(sdk_result: dict) -> dict:
    import json

    return json.loads(sdk_result["content"][0]["text"])


def _call(name: str, args: dict, apply_read_scope: bool = False) -> dict:
    from roles._retrieval import functions as R

    fn = R.REGISTRY_RETRIEVAL[name]
    known = set(inspect.signature(fn).parameters) - {"conn"}
    hint = _sig_hint(R.SCHEMAS_RETRIEVAL, name)
    return _payload(_text(run_labpack_fn(fn, name, args, known, hint, apply_read_scope=apply_read_scope)))


@requires_db
def test_seed_counts_present():

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM wiki_pages")
            assert cur.fetchone()[0] == 82
            cur.execute("SELECT count(*) FROM wiki_links")
            assert cur.fetchone()[0] == 309
            cur.execute("SELECT count(*) FROM interaction_notes")
            assert cur.fetchone()[0] == 2215
            cur.execute("SELECT count(*) FROM interaction_notes WHERE embedding IS NOT NULL")
            assert cur.fetchone()[0] == 2215
            cur.execute("SELECT count(*) FROM party_relations")
            assert cur.fetchone()[0] == 8
    finally:
        conn.close()


@requires_db
def test_wiki_lookup_real_page():
    out = _call("wiki_lookup", {"page": "tran-cho-vay"})
    assert out.get("found") is True
    assert out["citation"]["page"] == "tran-cho-vay"
    assert out.get("body")


@requires_db
def test_wiki_related_docs_inactive_graph_trap():

    out = _call("wiki_related_docs", {"page": "uu-dai-tet-68", "depth": 2})
    assert out.get("found") is True
    assert "uu-dai-tet-68" in out["inactive_in_graph"]


@requires_db
def test_embedding_bytea_coerced_to_bytes_via_adapter():

    pg = acquire()
    ad = PGConnAdapter(pg)
    try:
        rows = ad.execute("SELECT embedding FROM interaction_notes WHERE embedding IS NOT NULL LIMIT 5").fetchall()
        embs = [r["embedding"] for r in rows]
        assert all(isinstance(e, bytes) for e in embs), "Expected invariant was not satisfied at source line 75."
        mat = np.frombuffer(b"".join(embs), np.float32).reshape(len(embs), -1)  # op notes_search
        assert mat.shape[1] == 768
        norms = np.linalg.norm(mat, axis=1)
        assert all(abs(float(n) - 1.0) < 0.01 for n in norms)  # normalized embeddings
        pg.commit()
    finally:
        ad.close_cursors()
        release(pg)


@requires_db
def test_legal_related_exposure_c013_group_cap_breach():

    out = _call("legal_related_exposure", {"owner_id": "C013", "new_loan_vnd": 5_000_000_000_000})
    assert out["found"] is True
    assert sorted(m["id"] for m in out["group_members"]) == ["B002", "B004"]
    assert out["group_outstanding_vnd"] == 8_000_000_000_000
    assert out["verdict"]["group_ok"] is False
    assert out["verdict"]["single_ok"] is True


@requires_db
def test_legal_related_exposure_readscope_blocks_cross_customer():

    from app.orch import registry

    cid = _mk_conv("c001")
    token = registry.CTX_CONV.set(cid)
    try:
        # apply_read_scope=True (role path) → owner_id='C013' != C001 → not_your_data
        out = _call("legal_related_exposure", {"owner_id": "C013"}, apply_read_scope=True)
        assert out["code"] == "not_your_data"
    finally:
        registry.CTX_CONV.reset(token)
        _rm_conv(cid)


def _mk_conv(user_id: str) -> str:
    import uuid

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cid = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO conversations (id, user_id, title, status, created_at) VALUES (%s,%s,'t','idle',now())",
            (cid, user_id),
        )
    conn.close()
    return cid


def _rm_conv(cid: str) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    conn.cursor().execute("DELETE FROM conversations WHERE id::text=%s", (cid,))
    conn.close()


async def _run_notes_tool(query: str) -> dict:
    from app.orch.common_tools import _build_retrieval_tools

    tools = _build_retrieval_tools()
    notes_tool = next(t for t in tools if t.name == "notes_search")
    return _payload(await notes_tool.handler({"query": query}))


@requires_db
async def test_notes_search_refused_for_customer_conv():

    from app.orch import registry

    cid = _mk_conv("c001")  # c001 = customer seed
    token = registry.CTX_CONV.set(cid)
    try:
        out = await _run_notes_tool("cash flow")
        assert out["code"] == "internal_only"
        assert out["retryable"] is False
    finally:
        registry.CTX_CONV.reset(token)
        _rm_conv(cid)


@requires_db
async def test_notes_search_allowed_for_bank_conv():

    from app.orch import registry

    cid = _mk_conv("admin")  # admin = bank
    token = registry.CTX_CONV.set(cid)
    try:
        out = await _run_notes_tool("cash flow")
        assert out.get("code") != "internal_only"
    finally:
        registry.CTX_CONV.reset(token)
        _rm_conv(cid)


@requires_db
@requires_embed
def test_notes_search_semantic_ground_truth():

    r = _call("notes_search", {"query": "buy a house", "limit": 10})
    assert r.get("found") is True
    owners = {x["owner_id"] for x in r["results"]}
    assert len({"C002", "C008", "C019"} & owners) >= 2

    r2 = _call("notes_search", {"query": "business cash flow difficulty", "owner_id": "C005", "limit": 3})
    assert r2.get("found") is True
    assert all(x["owner_id"] == "C005" for x in r2["results"])
    assert r2["results"][0]["score"] > 0.4
