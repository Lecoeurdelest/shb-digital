"""retrieval_* — 4 tầng truy vấn tri thức (wiki + document-graph + entity-graph + vector notes).
Contract như mọi tool: fn(conn, **kwargs) -> dict, error 4-field, asOf, SQL portable (chỉ thêm
WITH RECURSIVE — SQLite/PG đều có). Vector = numpy cosine TRONG tool (embedding BLOB trong DB,
không phụ thuộc pgvector — swap PG chỉ đổi placeholder).

Ranh: wiki là VĂN BẢN DIỄN GIẢI + căn cứ — kết luận nghiệp vụ vẫn phải dẫn từ tool nghiệp vụ
(credit_assess/legal_*/product_*); tool wiki trả trang + citation, không phán verdict.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

# numpy CHỈ cần cho notes_search (cosine) — lazy import để env trơn vẫn chạy trọn tool wiki/graph
# (cùng bài học lazy-import của seed_retrieval 18/7; np=None → notes_search trả error 4-field)
try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

# benchmark 18/7: vietnamese-bi-encoder (+pyvi segment) thắng e5-small/MiniLM trên note
# tiếng Việt ngắn (11/15 vs 8-9/15, phổ điểm phân biệt rõ) — PHẢI khớp seed_retrieval.EMB_MODEL
EMB_MODEL = "bkai-foundation-models/vietnamese-bi-encoder"
_model = None  # lazy singleton — load 1 lần cho cả process


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rows(c: sqlite3.Connection, sql: str, args: tuple = ()) -> list[dict]:
    return [dict(r) for r in c.execute(sql, args).fetchall()]


def _one(c: sqlite3.Connection, sql: str, args: tuple) -> dict | None:
    r = c.execute(sql, args).fetchone()
    return dict(r) if r else None


def _int(v, default: int, lo: int, hi: int) -> int:
    """Coerce an toàn ngay trong tool body (QA 18/7 BUG-1: int('abc') raise trần qua CLI) —
    kiểu lạ → default, rồi clamp. Fix ở body = fix chung mọi điểm mount."""
    try:
        return max(lo, min(int(v), hi))
    except (TypeError, ValueError):
        return max(lo, min(default, hi))


def _cite(p: dict) -> dict:
    out = {"page": p["id"], "title": p["title"], "legal_basis": p.get("legal_basis"),
           "status": p.get("status"), "effective_from": p.get("effective_from"),
           "effective_to": p.get("effective_to"), "source_file": p.get("source_file")}
    # NHIỆM VỤ 3 (18/7): anchor máy-kiểm tới đúng điều luật thật khi frontmatter có so_hieu+dieu
    # (trang QPPL cào từ wiki/phap-luat/*.md) — trang cũ (gia-thuyet-lab, không có 2 field này)
    # trả None, KHÔNG vỡ contract cũ (mọi field _cite vẫn có mặt, chỉ thêm "anchor").
    if p.get("so_hieu") and p.get("dieu"):
        out["anchor"] = {"so_hieu": p["so_hieu"], "dieu": p["dieu"]}
    else:
        out["anchor"] = None
    return out


# ─────────────────────────── wiki (tầng văn bản) ───────────────────────────

def wiki_lookup(conn: sqlite3.Connection, page: str) -> dict[str, Any]:
    """Đọc MỘT trang wiki theo id (slug) hoặc topic. Trả nguyên văn + citation + cạnh liên quan.
    Trang expired/replaced vẫn đọc được — status nói rõ để agent không áp bản chết."""
    p = _one(conn, "SELECT * FROM wiki_pages WHERE id=?", (page,)) or \
        _one(conn, "SELECT * FROM wiki_pages WHERE topic=?", (page,))
    if not p:
        hits = _rows(conn, "SELECT id, title FROM wiki_pages WHERE id LIKE ? OR topic LIKE ?",
                     (f"%{page}%", f"%{page}%"))
        return {"found": False, "asOf": _now(),
                "hint": f"Không có trang '{page}'. Gần đúng: {[h['id'] for h in hits[:5]]}"
                        " — hoặc xem INDEX role bằng wiki_lookup(page='index-legal'...)."}
    out_links = [r["to_page"] for r in _rows(conn,
                 "SELECT to_page FROM wiki_links WHERE from_page=?", (p["id"],))]
    in_links = [r["from_page"] for r in _rows(conn,
                "SELECT from_page FROM wiki_links WHERE to_page=?", (p["id"],))]
    return {"found": True, "asOf": _now(), "citation": _cite(p), "body": p["body"],
            "links": out_links, "backlinks": in_links,
            **({"warning": f"trang status={p['status']} — KHÔNG áp làm căn cứ hiện hành"}
               if p["status"] != "active" else {})}


def wiki_search(conn: sqlite3.Connection, q: str, role: str | None = None,
                limit: int = 5) -> dict[str, Any]:
    """Tìm trang wiki theo từ khoá (title/topic/tags/body — keyword, KHÔNG semantic; văn bản
    có khoá tự nhiên nên keyword đủ và trace được). Trả lean row + snippet, đọc trọn bằng wiki_lookup."""
    if not q or not q.strip():
        return {"found": False, "asOf": _now(), "hint": "q rỗng — đưa từ khoá, vd 'trần cho vay'"}
    pat = f"%{q.strip().lower()}%"
    sql = ("SELECT * FROM wiki_pages WHERE (lower(title) LIKE ? OR lower(topic) LIKE ?"
           " OR lower(tags) LIKE ? OR lower(body) LIKE ?)")
    args: list = [pat, pat, pat, pat]
    if role:
        sql += " AND role=?"; args.append(role)
    hits = _rows(conn, sql + " LIMIT ?", (*args, _int(limit, 5, 1, 20)))
    def snip(body: str) -> str:
        i = body.lower().find(q.strip().lower())
        return (" ".join(body[max(0, i - 60):i + 120].split()) if i >= 0 else body[:120]) + "…"
    return {"found": bool(hits), "asOf": _now(),
            "results": [{"page": h["id"], "title": h["title"], "role": h["role"],
                         "status": h["status"], "snippet": snip(h["body"]),
                         "anchor": ({"so_hieu": h["so_hieu"], "dieu": h["dieu"]}
                                    if h["so_hieu"] and h["dieu"] else None)} for h in hits],
            **({} if hits else {"hint": "không trang nào khớp — thử từ khoá khác hoặc wiki_lookup(index-<role>)"})}


def wiki_related_docs(conn: sqlite3.Connection, page: str, depth: int = 1) -> dict[str, Any]:
    """Đi CẠNH document-graph từ một trang (căn cứ / thay thế / dẫn chiếu), tối đa depth bậc.
    Dùng để soát PHẢ HỆ CĂN CỨ: trang tựa văn bản nào, văn bản đó còn hiệu lực không."""
    root = _one(conn, "SELECT * FROM wiki_pages WHERE id=?", (page,))
    if not root:
        return {"found": False, "asOf": _now(), "hint": f"Không có trang '{page}' — wiki_search trước."}
    depth = _int(depth, 1, 1, 3)
    edges = _rows(conn, """
        WITH RECURSIVE walk(frm, tgt, lvl) AS (
            SELECT from_page, to_page, 1 FROM wiki_links WHERE from_page = ?
            UNION
            SELECT wl.from_page, wl.to_page, walk.lvl + 1
            FROM wiki_links wl JOIN walk ON wl.from_page = walk.tgt
            WHERE walk.lvl < ?
        ) SELECT frm, tgt, lvl FROM walk""", (page, depth))
    ids = {page} | {e["tgt"] for e in edges} | {e["frm"] for e in edges}
    nodes = {p["id"]: p for p in _rows(
        conn, f"SELECT * FROM wiki_pages WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))}
    dead = [i for i, p in nodes.items() if p["status"] != "active"]
    return {"found": True, "asOf": _now(), "root": _cite(root),
            "edges": [{"from": e["frm"], "to": e["tgt"], "level": e["lvl"]} for e in edges],
            "nodes": [_cite(p) for p in nodes.values()],
            "inactive_in_graph": dead,
            **({"warning": f"trong phả hệ có văn bản KHÔNG còn hiệu lực: {dead} — mọi thứ tựa"
                           " lên chúng phải soát lại"} if dead else {})}


# ───────────────────────── notes (tầng vector) ─────────────────────────

def _embedder():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMB_MODEL)
    return _model


def notes_search(conn: sqlite3.Connection, query: str, owner_id: str | None = None,
                 limit: int = 5) -> dict[str, Any]:
    """Tìm SEMANTIC trên sổ tay tương tác RM (ghi chú tự do, có viết tắt). Hybrid: filter
    owner_id TRƯỚC (nếu có) rồi mới cosine. Dùng cho: tóm khách trước khi gặp · dò dấu hiệu
    rủi ro mềm · quét chân dung nhu cầu ("ai quan tâm vay mua nhà")."""
    if np is None:
        return {"code": "env_missing", "message": "notes_search cần numpy/sentence-transformers/pyvi",
                "hint": "Chạy bằng env có embedding (vd .venv_embed) — tool wiki/graph không bị ảnh hưởng.",
                "retryable": False, "asOf": _now()}
    if not query or not query.strip():
        return {"found": False, "asOf": _now(), "hint": "query rỗng — mô tả điều cần tìm bằng lời"}
    sql = "SELECT note_id, owner_id, ts, channel, rm, note_text, embedding FROM interaction_notes"
    args: tuple = ()
    if owner_id:
        sql += " WHERE owner_id=?"; args = (owner_id,)
    rows = _rows(conn, sql, args)
    if not rows:
        return {"found": False, "asOf": _now(),
                "hint": f"owner '{owner_id}' không có ghi chú nào" if owner_id else "kho notes trống"}
    from pyvi.ViTokenizer import tokenize
    qv = _embedder().encode([tokenize(query.strip())], normalize_embeddings=True)[0]
    mat = np.frombuffer(b"".join(r["embedding"] for r in rows), np.float32).reshape(len(rows), -1)
    scores = mat @ qv
    top = np.argsort(-scores)[: _int(limit, 5, 1, 20)]
    return {"found": True, "asOf": _now(), "scope": owner_id or "all",
            "results": [{"note_id": rows[i]["note_id"], "owner_id": rows[i]["owner_id"],
                         "ts": rows[i]["ts"], "channel": rows[i]["channel"],
                         "score": round(float(scores[i]), 3), "text": rows[i]["note_text"]}
                        for i in top],
            "hint": "score = cosine; mọi trích dẫn ghi kèm note_id làm nguồn"}


# ──────────────────────── entity graph (nhóm liên quan) ────────────────────────

def legal_related_exposure(conn: sqlite3.Connection, owner_id: str,
                           new_loan_vnd: float = 0) -> dict[str, Any]:
    """Nhóm khách hàng LIÊN QUAN (đi quan hệ 2 bậc, vô hướng) + tổng dư nợ nhóm, đối chiếu
    trần một-khách (15%) và trần NHÓM (25% — assumptions related_group_cap_pct). Truyền
    new_loan_vnd để kiểm 'nếu cấp thêm khoản này thì nhóm còn trong trần không'."""
    try:
        new_loan_vnd = float(new_loan_vnd or 0)
    except (TypeError, ValueError):
        return {"code": "bad_type", "message": f"new_loan_vnd '{new_loan_vnd}' không phải số",
                "hint": "truyền số VND, vd 5000000000", "retryable": False, "asOf": _now()}
    if new_loan_vnd < 0:
        return {"code": "bad_param", "message": "new_loan_vnd âm — không có khoản vay âm",
                "hint": "truyền số VND ≥ 0", "retryable": False, "asOf": _now()}
    ent = _one(conn, "SELECT id FROM customers WHERE id=?", (owner_id,)) or \
          _one(conn, "SELECT id FROM businesses WHERE id=?", (owner_id,))
    if not ent:
        return {"found": False, "asOf": _now(),
                "hint": f"Không có owner '{owner_id}'. Lấy id: cust_search(q=...)."}
    edges = _rows(conn, """
        WITH RECURSIVE grp(node, via, lvl) AS (
            SELECT ?, '', 0
            UNION
            SELECT CASE WHEN pr.from_id = grp.node THEN pr.to_id ELSE pr.from_id END,
                   pr.relation, grp.lvl + 1
            FROM party_relations pr
            JOIN grp ON pr.from_id = grp.node OR pr.to_id = grp.node
            WHERE grp.lvl < 2
        ) SELECT DISTINCT node, MIN(via) AS via, MIN(lvl) AS lvl FROM grp WHERE node != ? GROUP BY node""",
        # DEVIATION vs LAB (T12-2, architect duyệt): sqlite bare-column `via` trong GROUP BY = chọn row
        # TUỲ Ý (không xác định); PG bắt aggregate. `MIN(via)` = bản XÁC ĐỊNH cùng ngữ nghĩa, KHÔNG đổi
        # logic — LAB cần re-sync upstream (D-68c). Ground-truth C013→B002/B004 + exposure giữ y hệt LAB.
        (owner_id, owner_id))
    members = [owner_id] + [e["node"] for e in edges]
    q = ",".join("?" * len(members))
    loans = _rows(conn, f"SELECT owner_id, loan_id, outstanding FROM loans"
                        f" WHERE owner_id IN ({q}) AND status='active'", tuple(members))
    group_outstanding = sum(l["outstanding"] for l in loans)
    a = {r["key"]: r["value"] for r in _rows(
        conn, "SELECT key, value FROM assumptions WHERE key IN"
              " ('single_customer_cap_pct','related_group_cap_pct','bank_equity_bil_vnd')")}
    equity = float(a.get("bank_equity_bil_vnd", 0)) * 1e9
    single_cap = float(a.get("single_customer_cap_pct", 0.15)) * equity
    group_cap = float(a.get("related_group_cap_pct", 0.25)) * equity
    own = sum(l["outstanding"] for l in loans if l["owner_id"] == owner_id)
    total_if = group_outstanding + float(new_loan_vnd or 0)
    return {"found": True, "asOf": _now(), "owner": owner_id,
            "group_members": [{"id": e["node"], "relation": e["via"], "level": e["lvl"]}
                              for e in edges],
            "loans_in_group": loans,
            "own_outstanding_vnd": own,
            "group_outstanding_vnd": group_outstanding,
            "new_loan_vnd": float(new_loan_vnd or 0),
            "caps": {"single_customer_vnd": single_cap, "related_group_vnd": group_cap,
                     "basis": "wiki: tran-cho-vay · nhom-khach-lien-quan"},
            "verdict": {
                "single_ok": (own + float(new_loan_vnd or 0)) <= single_cap,
                "group_ok": total_if <= group_cap},
            "hint": ("NHÓM vượt trần dù từng khoản riêng có thể đạt — đối chiếu group_ok"
                     if total_if > group_cap else
                     "trong trần — ghi rõ đã soát cả trần nhóm khi kết luận")}


# ─────────────────────────── registry + schemas ───────────────────────────

REGISTRY_RETRIEVAL = {
    "wiki_lookup": wiki_lookup,
    "wiki_search": wiki_search,
    "wiki_related_docs": wiki_related_docs,
    "notes_search": notes_search,
    "legal_related_exposure": legal_related_exposure,
}

ANNOTATIONS_RETRIEVAL = {n: {"readOnlyHint": True} for n in REGISTRY_RETRIEVAL}

SCHEMAS_RETRIEVAL: dict[str, Any] = {
    "wiki_lookup": {
        "mô tả": "Đọc MỘT trang tri thức (quy định/chính sách/gói) theo slug hoặc topic — trả"
                 " nguyên văn + citation (gồm anchor={so_hieu,dieu} khi trang là QPPL thật cào"
                 " từ wiki/phap-luat/, null cho trang nghiệp vụ gia-thuyet-lab) + cạnh liên quan."
                 " Mục lục: page='index-legal'/'index-credit'/'index-products'/'index-phap-luat'.",
        "params": {"page": {"type": "string", "required": True,
                            "desc": "slug trang (vd 'tran-cho-vay') hoặc topic (vd 'dscr_ltv')"}},
    },
    "wiki_search": {
        "mô tả": "Tìm trang tri thức theo TỪ KHOÁ (title/topic/tags/body). Lean row + snippet +"
                 " anchor={so_hieu,dieu} khi có (trang QPPL thật); đọc trọn trang bằng wiki_lookup."
                 " KHÔNG dùng cho ghi chú khách (notes_search).",
        "params": {"q": {"type": "string", "required": True, "desc": "từ khoá tiếng Việt"},
                   "role": {"type": "string", "values": ["legal", "credit", "products"],
                            "desc": "lọc theo kho role (tuỳ chọn)"},
                   "limit": {"type": "integer", "default": 5}},
    },
    "wiki_related_docs": {
        "mô tả": "Đi CẠNH đồ thị văn bản từ một trang (căn cứ/thay thế/dẫn chiếu) — soát phả hệ"
                 " căn cứ + cảnh báo văn bản trong phả hệ đã hết hiệu lực.",
        "params": {"page": {"type": "string", "required": True, "desc": "slug trang gốc"},
                   "depth": {"type": "integer", "default": 1, "desc": "số bậc đi cạnh (1-3)"}},
    },
    "notes_search": {
        "mô tả": "Tìm SEMANTIC trên sổ tay tương tác RM (ghi chú tự do, viết tắt). Dùng khi: tóm"
                 " khách trước khi gặp (kèm owner_id) · dò dấu hiệu rủi ro mềm · quét chân dung nhu"
                 " cầu toàn danh mục (bỏ owner_id). Trích dẫn kèm note_id.",
        "params": {"query": {"type": "string", "required": True,
                             "desc": "mô tả bằng lời điều cần tìm, vd 'khó khăn dòng tiền'"},
                   "owner_id": {"type": "string", "desc": "giới hạn 1 khách (tuỳ chọn)"},
                   "limit": {"type": "integer", "default": 5}},
    },
    "legal_related_exposure": {
        "mô tả": "Nhóm khách hàng LIÊN QUAN (quan hệ sở hữu/điều hành/bảo lãnh, 2 bậc) + tổng dư"
                 " nợ nhóm, đối chiếu trần một-khách và trần NHÓM. BẮT BUỘC với khoản vay lớn —"
                 " từng khoản đạt trần đơn vẫn có thể vỡ trần nhóm.",
        "params": {"owner_id": {"type": "string", "required": True},
                   "new_loan_vnd": {"type": "number", "default": 0,
                                    "desc": "khoản xin vay mới để kiểm 'nếu cấp thêm'"}},
    },
}
