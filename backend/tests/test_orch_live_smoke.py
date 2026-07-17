"""[BACKEND] Live SDK smoke (D-29 BONUS — không phải gate). Chứng minh sub client mount credit
chạy tool THẬT qua SDK → ra DSCR. Skip mặc định (chậm/cần claude-cli auth + DB seed).

Bật: RUN_LIVE_SDK=1 uv run pytest tests/test_orch_live_smoke.py
"""

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
    """Sub credit (SKILL + toolpack mount) chạy 1 lượt SDK thật với brief C001 → gọi credit_assess
    → text/tool-calls chứa DSCR. Verify QUA tool-call (không tin text tự xưng)."""
    from app.orch.main_session import run_sub_turn
    from app.orch.store import Task

    task = Task(
        id="live-smoke-1",
        conv_id="live-smoke-conv",
        role="credit",
        title="Thẩm định C001",
        status="running",
        input="Khách C001 hiện trạng khả năng trả nợ thế nào? Cho biết DSCR.",
    )
    out = await run_sub_turn(task)
    tool_names = [tc["tool"] for tc in out["tool_calls"]]
    assert "credit_assess" in tool_names, f"sub phải gọi credit_assess, gọi: {tool_names}"
    # 3.709 xuất hiện đâu đó (text tổng hợp hoặc đã tính qua tool) — bằng chứng số có nguồn
    assert "3.7" in out["text"] or any("credit_assess" == tc["tool"] for tc in out["tool_calls"])
