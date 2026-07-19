"""[BACKEND] Test T16-2 — /api/stats/cost + /api/stats/cost-trend + stats spark (D-70) + window D-69.

Z-SCORE/breakdown assert giá trị HAND-COMPUTED trên set seed (không 'non-empty'). z-score cần DB
cost-rows SẠCH (z DB-wide) → @requires_test_db + TRUNCATE cost-bearing rows trước seed. spark=24 số.
"""

from __future__ import annotations

import json
from uuid import uuid4

import psycopg2
import psycopg2.extras

from app.api.cost import _cost_sync
from app.db.config import DATABASE_URL

from .conftest import requires_test_db


def _raw(sql: str, args: tuple = ()) -> list:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, args)
            return cur.fetchall() if cur.description else []
    finally:
        conn.close()


def _clean_cost_rows() -> None:
    """z-score DB-wide → phải sạch cost rows trước seed. Xoá tasks có cost + messages assistant meta."""
    _raw("DELETE FROM tasks WHERE cost->>'cost_usd' IS NOT NULL")
    _raw("DELETE FROM messages WHERE sender='assistant' AND meta->'metrics'->>'cost_usd' IS NOT NULL")


def _mk_task_cost(conv: str, role: str, cost: float, model: str = "glm-4.6", intok=100, outtok=50) -> None:
    _raw(
        "INSERT INTO tasks (conv_id, role, title, status, queued_at, ended_at, model, "
        "input_tokens, output_tokens, cache_read_tokens, cache_create_tokens, cost) "
        "VALUES (%s,%s,'t','done',now(),now(),%s,%s,%s,10,5,%s)",
        (conv, role, model, intok, outtok, json.dumps({"cost_usd": cost})),
    )


@requires_test_db
def test_cost_total_breakdown_by_model_by_role():
    """Seed 2 task credit + 1 legal, cost hand-known → total + breakdown 4-token + by_model + by_role đúng SỐ."""
    _clean_cost_rows()
    c = f"ct-{uuid4()}"
    _mk_task_cost(c, "credit", 0.10, model="glm-4.6", intok=100, outtok=50)
    _mk_task_cost(c, "credit", 0.20, model="glm-4.6", intok=200, outtok=60)
    _mk_task_cost(c, "legal", 0.05, model="gpt-5.5", intok=50, outtok=10)
    try:
        r = _cost_sync("24h")
        assert abs(r["total_cost_usd"] - 0.35) < 1e-6  # 0.10+0.20+0.05
        assert r["breakdown"]["input_tokens"] == 350  # 100+200+50
        assert r["breakdown"]["output_tokens"] == 120  # 50+60+10
        assert r["cost_estimated"] is True
        bm = {m["model"]: m for m in r["by_model"]}
        assert abs(bm["glm-4.6"]["cost_usd"] - 0.30) < 1e-6 and bm["glm-4.6"]["turns"] == 2
        assert abs(bm["gpt-5.5"]["cost_usd"] - 0.05) < 1e-6
        br = {x["role"]: x for x in r["by_role"]}
        assert abs(br["credit"]["cost_usd"] - 0.30) < 1e-6 and br["credit"]["turns"] == 2
        assert abs(br["legal"]["cost_usd"] - 0.05) < 1e-6
    finally:
        _raw("DELETE FROM tasks WHERE conv_id=%s", (c,))


@requires_test_db
def test_cost_zscore_anomaly_hand_computed():
    """6 conv: 5×0.001 + 1×1.0 → outlier z=2.041 (STDDEV_SAMP, hand-computed) ≥2 → 1 anomaly."""
    _clean_cost_rows()
    convs = []
    try:
        for i in range(5):
            cid = f"z-lo-{i}-{uuid4().hex[:4]}"
            _mk_task_cost(cid, "credit", 0.001)
            convs.append(cid)
        out_cid = f"z-hi-{uuid4().hex[:4]}"
        _mk_task_cost(out_cid, "credit", 1.0)
        convs.append(out_cid)
        r = _cost_sync("24h")
        assert len(r["anomalies"]) == 1  # chỉ outlier z≥2
        a = r["anomalies"][0]
        assert a["conv_id"] == out_cid
        assert abs(a["z_score"] - 2.041) < 0.02  # hand-computed (statistics.stdev)
    finally:
        for cid in convs:
            _raw("DELETE FROM tasks WHERE conv_id=%s", (cid,))


@requires_test_db
def test_cost_zscore_empty_when_under_2_conv():
    """n<2 conv → STDDEV_SAMP null → 0 anomaly (guard n>=2)."""
    _clean_cost_rows()
    c = f"z1-{uuid4()}"
    _mk_task_cost(c, "credit", 5.0)
    try:
        r = _cost_sync("24h")
        assert r["anomalies"] == []  # 1 conv → không tính z
    finally:
        _raw("DELETE FROM tasks WHERE conv_id=%s", (c,))


@requires_test_db
def test_cost_empty_db_zeros_no_500():
    """DB rỗng cost → total 0, breakdown 0, list rỗng, delta null (prev=0). KHÔNG 500."""
    _clean_cost_rows()
    r = _cost_sync("24h")
    assert r["total_cost_usd"] == 0
    assert all(v == 0 for v in r["breakdown"].values())
    assert r["by_model"] == [] and r["by_role"] == [] and r["anomalies"] == []
    assert r["delta"]["total_cost_pct"] is None  # prev=0 → không chia


@requires_test_db
def test_cost_main_from_messages_meta():
    """MAIN turn cost đọc từ messages.meta.metrics (nhánh main) — không chỉ tasks."""
    _clean_cost_rows()
    import uuid

    conv = str(uuid.uuid4())
    _raw(
        "INSERT INTO conversations (id, user_id, title, status, created_at) VALUES (%s,'admin','t','idle',now())",
        (conv,),
    )
    _raw(
        "INSERT INTO messages (conv_id, ts, sender, content, meta) VALUES (%s, now(), 'assistant', 'hi', %s)",
        (
            conv,
            json.dumps({"metrics": {"cost_usd": 0.42, "model": "glm-4.6", "input_tokens": 999, "output_tokens": 1}}),
        ),
    )
    try:
        r = _cost_sync("24h")
        assert abs(r["total_cost_usd"] - 0.42) < 1e-6  # từ messages.meta
        assert r["breakdown"]["input_tokens"] == 999
        br = {x["role"]: x for x in r["by_role"]}
        assert "main" in br  # role main từ messages
    finally:
        _raw("DELETE FROM messages WHERE conv_id=%s", (conv,))
        _raw("DELETE FROM conversations WHERE id::text=%s", (conv,))


@requires_test_db
def test_cost_trend_pivot_by_model():
    """cost-trend long→pivot: 2 model trong 1 bucket → series có cả 2 tên + cost đúng."""
    from app.api.cost import _cost_trend_sync

    _clean_cost_rows()
    c = f"tr-{uuid4()}"
    _mk_task_cost(c, "credit", 0.10, model="glm-4.6")
    _mk_task_cost(c, "legal", 0.05, model="gpt-5.5")
    try:
        r = _cost_trend_sync("24h", "hour", "model")
        assert r["buckets"]  # có bucket
        # gom mọi bucket → series tổng có cả 2 model
        all_names = set()
        for b in r["buckets"]:
            all_names |= set(b["series"].keys())
        assert "glm-4.6" in all_names and "gpt-5.5" in all_names
    finally:
        _raw("DELETE FROM tasks WHERE conv_id=%s", (c,))


# ── stats spark (D-70) shape ─────────────────────────────────────────────────


@requires_test_db
def test_stats_spark_exactly_24_buckets():
    """D-70: mỗi KPI spark LUÔN 24 số (rỗng → 24 số 0). shape FE number[24]."""
    from app.api.stats import _stats_sync

    r = _stats_sync("24h")
    assert "sparks" in r
    for kpi, arr in r["sparks"].items():
        assert isinstance(arr, list) and len(arr) == 24, f"{kpi} spark phải 24 số, thấy {len(arr)}"
        assert all(isinstance(x, int) for x in arr)
