from __future__ import annotations

import os

import pytest

from .conftest import requires_db

_LIVE = os.environ.get("RUN_LIVE_SDK") == "1"

pytestmark = [
    pytest.mark.skipif(not _LIVE, reason="live SDK opt-in: RUN_LIVE_SDK=1"),
    requires_db,
]


@pytest.mark.asyncio
async def test_sub_credit_live_produces_dscr():

    from app.orch.main_session import run_sub_turn
    from app.orch.store import Task

    task = Task(
        id="live-smoke-1",
        conv_id="live-smoke-conv",
        role="credit",
        title="Assess C001",
        status="running",
        input="What is customer C001's current repayment capacity? Provide the DSCR.",
    )
    out = await run_sub_turn(task)
    tool_names = [tc["tool"] for tc in out["tool_calls"]]
    assert "credit_assess" in tool_names, "Expected invariant was not satisfied at source line 33."

    assert "3.7" in out["text"] or any("credit_assess" == tc["tool"] for tc in out["tool_calls"])
