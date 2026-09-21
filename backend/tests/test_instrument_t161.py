from __future__ import annotations

import logging
from types import SimpleNamespace
from uuid import uuid4

import psycopg2

from app.db.config import DATABASE_URL
from app.orch import instrument

from .conftest import requires_db


def _fake_result(**over):

    base = {
        "usage": {
            "input_tokens": 6479,
            "output_tokens": 40,
            "cache_read_input_tokens": 1088,
            "cache_creation_input_tokens": 0,
        },
        "model_usage": {"glm-4.6": {"inputTokens": 6479, "costUSD": 0.038}},
        "total_cost_usd": 0.038,
        "duration_ms": 2145,
    }
    base.update(over)
    return SimpleNamespace(**base)


def test_extract_metrics_maps_real_sdk_keys():

    m = instrument.extract_metrics(_fake_result())
    assert m["input_tokens"] == 6479
    assert m["output_tokens"] == 40
    assert m["cache_read_tokens"] == 1088
    assert m["cache_create_tokens"] == 0
    assert m["duration_ms"] == 2145
    assert m["model"] == "glm-4.6"
    assert m["cost_usd"] == 0.038


def test_extract_metrics_defensive_missing_usage():

    m = instrument.extract_metrics(SimpleNamespace(usage=None, model_usage=None, total_cost_usd=None, duration_ms=None))
    assert m["input_tokens"] is None and m["model"] is None and m["cost_usd"] is None


def test_extract_metrics_multi_model_joins_keys():

    m = instrument.extract_metrics(_fake_result(model_usage={"glm-4.6": {}, "glm-4.5": {}}))
    assert "glm-4.6" in m["model"] and "glm-4.5" in m["model"]


@requires_db
async def test_save_task_metrics_round_trip():

    from app.orch import store

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    tid = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tasks (conv_id, role, title, status, queued_at) "
                "VALUES (%s,'credit','t','done',now()) RETURNING id",
                (f"instr-{uuid4()}",),
            )
            tid = str(cur.fetchone()[0])
        m = instrument.extract_metrics(_fake_result())
        await store.save_task_metrics(tid, m)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT input_tokens, output_tokens, cache_read_tokens, duration_ms, model, cost "
                "FROM tasks WHERE id=%s",
                (tid,),
            )
            row = cur.fetchone()
        assert row[0] == 6479 and row[1] == 40 and row[2] == 1088
        assert row[3] == 2145 and row[4] == "glm-4.6"
        assert row[5]["cost_usd"] == 0.038  # cost jsonb
    finally:
        if tid:
            conn.cursor().execute("DELETE FROM tasks WHERE id=%s", (tid,))
        conn.close()


@requires_db
async def test_save_task_metrics_null_safe():

    from app.orch import store

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    tid = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tasks (conv_id, role, title, status, queued_at) "
                "VALUES (%s,'legal','t','done',now()) RETURNING id",
                (f"instr-n-{uuid4()}",),
            )
            tid = str(cur.fetchone()[0])
        await store.save_task_metrics(tid, {k: None for k in ("input_tokens", "output_tokens", "cost_usd")})
        with conn.cursor() as cur:
            cur.execute("SELECT input_tokens FROM tasks WHERE id=%s", (tid,))
            assert cur.fetchone()[0] is None
    finally:
        if tid:
            conn.cursor().execute("DELETE FROM tasks WHERE id=%s", (tid,))
        conn.close()


def test_log_turn_carries_base_url_evidence(caplog):

    with caplog.at_level(logging.INFO, logger="orch.turn"):
        instrument.log_turn(
            conv_id="c1",
            actor="main",
            provider="wrap",
            model="gpt-5.5",
            base_url="https://wrap.example/v1",
            metrics=instrument.extract_metrics(_fake_result()),
        )
    rec = [r.getMessage() for r in caplog.records if "turn conv=" in r.getMessage()]
    assert rec and "base_url=https://wrap.example/v1" in rec[0]
    assert "provider=wrap" in rec[0] and "duration_ms=2145" in rec[0]
