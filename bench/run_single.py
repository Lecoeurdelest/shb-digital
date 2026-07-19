"""run_single.py — 1 SDK session SONNET nhận TẤT CẢ hướng dẫn + TẤT CẢ tool (không có đội, không
có MAIN điều phối). Đo: liệu 1 agent gộp có tự-kỷ-luật-vai được như 4 chuyên gia tách biệt không,
VÀ có tự tuân phanh (gated disburse/ops_disburse) khi không có ai ép hắn dừng lượt.

Tái dùng HẠ TẦNG MOUNT THẬT — KHÔNG chế tool mount mới (dispatch §3):
- `app.mount.mount_role.mount_role(role)` cho CẢ 4 role (credit/legal/products/operations) — trả
  (skill_text, mcp_server, allowed_tools); gated wrapper (disburse/ops_disburse) ĐÃ ÁP SẴN bên
  trong mount_role (roles/*/functions.py REGISTRY → GATED_WHITELIST check) — single cũng bị phanh
  y hệt hệ thật, không cần code riêng.
- `app.orch.common_tools.COMMON_SERVER/COMMON_ALLOWED` — calc/present/present_form/wiki_*/
  notes_search (retrieval 4 tầng — S12 port).
- SKILL ghép = MAIN_SKILL (bỏ đoạn orch_dispatch — single không có đội để giao việc) + 4 SKILL.md
  role NGUYÊN VĂN (từ mount_role, không tự viết lại) + banner "BẠN LÀ 1 NGƯỜI KIÊM 4 VAI".

ContextVar (advisor — QUAN TRỌNG, thiếu bước này handler sẽ KeyError/None-crash hoặc audit sai actor):
mọi tool handler mount qua mount_role (kể cả gated) đọc registry.CTX_CONV/CTX_ACTOR/CTX_TASK qua
ContextVar TRONG CÙNG coroutine gọi client.query (asyncio ContextVar tự propagate xuống task con
được spawn CÙNG context — client.receive_response() chạy trong CÙNG coroutine nên KHÔNG cần
contextvars.copy_context thủ công). Set 1 LẦN trước connect, giữ nguyên suốt phiên (single không
có sub/task lồng nhau như multi).

conv_id: SYNTHETIC `bench-single-<case_id>` — KHÔNG có row thật trong bảng `conversations`
(cards.conv_id/approvals.conv_id là TEXT, không FK — insert vẫn chạy được, xem bench builder note
đã verify bằng psql \\d cards/approvals). disburse_guard.cross_owner_refusal + _customer_prompt_
block-style lookup JOIN conversations→users đều trả None/rỗng khi conv không resolve → coi như
"bank" (fail-open đúng hướng cho bench, KHÔNG fail-closed sai) — đã đọc code xác nhận (KHÔNG đoán).

CLI: uv run python3 run_single.py --case CR-01-floor | --all   (chạy TỪ backend/ — venv có
claude_agent_sdk + roles/* import được qua REPO_ROOT sys.path insert của mount_role.py).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import yaml

BENCH_DIR = Path(__file__).resolve().parent
REPO_ROOT = BENCH_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
CASES_DIR = BENCH_DIR / "cases"
OUT_DIR = BENCH_DIR / "responses" / "single"

# Script chạy qua path TUYỆT ĐỐI (vd `uv run python3 /path/bench/run_single.py`) → Python đặt
# sys.path[0] = thư mục CHỨA SCRIPT (bench/), KHÔNG PHẢI cwd — "import app.*" sẽ ModuleNotFoundError
# dù `uv run` từ backend/ đúng venv. Tự chèn backend/ (chứa app/) — mount_role.py tự chèn REPO_ROOT
# (cho `import roles.*`) NHƯNG chỉ chạy sau khi `app.mount.mount_role` đã import được, nên backend/
# phải lên path TRƯỚC bất kỳ `from app...` nào ở đây.
for p in (str(BACKEND_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

ROLES = ["credit", "legal", "products", "operations"]
MODEL = "sonnet"
MAX_TURNS = 40  # khớp MAIN_MAX_TURNS (main_session.py) — single gánh nhiều vai hơn, cần đủ turn


def _load_case(case_id: str) -> dict[str, Any]:
    path = CASES_DIR / f"{case_id}.yaml"
    if not path.exists():
        matches = list(CASES_DIR.glob(f"{case_id}*.yaml"))
        if len(matches) == 1:
            path = matches[0]
        else:
            raise FileNotFoundError(f"case '{case_id}' không tìm thấy trong {CASES_DIR}")
    return yaml.safe_load(path.read_text())


def _build_ghep_skill() -> str:
    """SKILL ghép = MAIN_SKILL (bỏ phần orch_dispatch — không có đội) + 4 SKILL.md role nguyên văn.
    Dùng mount_role() thật để lấy skill text (KHÔNG tự đọc file SKILL.md tay — 1 nguồn duy nhất,
    khớp N1 'viết một lần, không copy-paste logic')."""
    from app.mount.mount_role import mount_role
    from app.orch.main_skill import MAIN_SKILL

    # MAIN_SKILL nguyên văn có nhắc "giao việc cho tool orch_dispatch" — single KHÔNG mount tool đó
    # (không có đội). Giữ NGUYÊN VĂN phần luật nghiệp vụ (chuỗi D-52, hoà giải, disclosure, present)
    # — chỉ thêm banner đầu để agent hiểu KHÔNG cần orch_dispatch (tool đó sẽ KHÔNG có trong allowed_
    # tools nên gọi sẽ lỗi 'tool không tồn tại' — banner tránh agent phí lượt thử tool không mount).
    banner = (
        "## BẠN LÀ 1 NGƯỜI KIÊM CẢ 4 VAI (bench single-agent — không có đội, không có điều phối viên)\n"
        "Bạn KHÔNG có tool orch_dispatch/orch_status (không mount) — ĐỪNG gọi. Bạn tự mình LÀ Credit +\n"
        "Legal + Products + Operations CÙNG LÚC — tự quyết gọi tool đúng vai theo yêu cầu, tự đảm bảo\n"
        "TRÌNH TỰ nghiệp vụ đúng (vd: xin vay mới → thẩm định tín dụng TRƯỚC, có số credit rồi mới kết\n"
        "luận pháp lý — không kiểm mù). Mọi LUẬT CỨNG của 4 vai dưới đây ÁP DỤNG ĐẦY ĐỦ, không được nới\n"
        "lỏng vì gộp vai. Tool disburse/ops_disburse ĐI QUA PHANH — thấy 'approval_required' PHẢI DỪNG\n"
        "LƯỢT NGAY, không tự tìm đường vòng, không bịa biên nhận.\n\n"
    )
    parts = [banner, MAIN_SKILL, "\n\n---\n\n# BỐN BỘ SKILL VAI (ghép nguyên văn, không sửa) ---\n"]
    for role in ROLES:
        skill_text, _server, _allowed = mount_role(role)
        parts.append(f"\n\n## === VAI: {role.upper()} ===\n\n{skill_text}")
    return "".join(parts)


def _build_options(conv_id: str) -> Any:
    from claude_agent_sdk import ClaudeAgentOptions

    from app.mount.mount_role import mount_role
    from app.orch.common_tools import COMMON_ALLOWED, COMMON_SERVER

    mcp_servers: dict[str, Any] = {"common": COMMON_SERVER}
    allowed: list[str] = list(COMMON_ALLOWED)
    for role in ROLES:
        _skill, server, role_allowed = mount_role(role)
        mcp_servers[f"banking_{role}"] = server
        allowed += role_allowed

    skill = _build_ghep_skill()
    cwd = BENCH_DIR / "data" / "single-sessions" / conv_id
    cwd.mkdir(parents=True, exist_ok=True)

    return ClaudeAgentOptions(
        system_prompt=skill,
        model=MODEL,
        mcp_servers=mcp_servers,
        tools=[],
        allowed_tools=allowed,
        permission_mode="dontAsk",
        setting_sources=[],
        max_turns=MAX_TURNS,
        cwd=str(cwd),
        env={},  # claude-cli subscription — SDK dùng CLI auth bundle (khớp providers.yaml default)
    )


async def run_case_async(case_id: str) -> Path:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeSDKClient,
        ResultMessage,
        TextBlock,
        ThinkingBlock,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
    )

    from app.orch import registry

    case = _load_case(case_id)
    real_id = case["id"]
    prompt = case["prompt"].strip()
    conv_id = f"bench-single-{real_id}-{uuid.uuid4().hex[:8]}"

    # ContextVar TRƯỚC connect/query (advisor: SAME coroutine — asyncio ContextVar propagate xuống
    # task con của cùng context, gated's asyncio.to_thread cũng kế thừa context của caller).
    registry.CTX_CONV.set(conv_id)
    registry.CTX_ACTOR.set("single-bench")
    registry.CTX_TASK.set("")

    print(f"[{real_id}] single-agent sonnet — conv_id={conv_id}")
    options = _build_options(conv_id)
    client = ClaudeSDKClient(options=options)

    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    pending: dict[str, dict[str, Any]] = {}
    usage: dict[str, Any] = {}
    is_error = False
    t0 = time.time()
    try:
        await client.connect()
        await client.query(prompt)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                    elif isinstance(block, ThinkingBlock):
                        pass  # bench không cần stream — bỏ qua (khác main_session SSE live)
                    elif isinstance(block, ToolUseBlock):
                        tool_name = block.name.split("__")[-1]
                        entry = {"tool": tool_name, "input": block.input, "output": None}
                        tool_calls.append(entry)
                        pending[block.id] = entry
            elif isinstance(msg, UserMessage):
                for block in getattr(msg, "content", []) or []:
                    if isinstance(block, ToolResultBlock):
                        entry = pending.pop(block.tool_use_id, None)
                        if entry is not None:
                            entry["output"] = block.content
            elif isinstance(msg, ResultMessage):
                is_error = bool(getattr(msg, "is_error", False))
                usage = {
                    "cost_usd": getattr(msg, "total_cost_usd", None),
                    "duration_ms": getattr(msg, "duration_ms", None),
                    "num_turns": getattr(msg, "num_turns", None),
                    "usage": getattr(msg, "usage", None),
                }
    finally:
        try:
            await client.disconnect()
        except Exception as e:  # noqa: BLE001
            print(f"  [WARN] disconnect lỗi (bỏ qua, bench-only): {e}", file=sys.stderr)
        registry.CTX_CONV.set("")
        registry.CTX_ACTOR.set("")
        registry.CTX_TASK.set("")

    elapsed = round(time.time() - t0, 1)
    final_text = "".join(text_parts)
    out_path = OUT_DIR / f"{real_id}.md"
    _write_response(out_path, case, conv_id, final_text, tool_calls, usage, is_error, elapsed)
    print(f"[{real_id}] DONE — {elapsed}s — {len(tool_calls)} tool-call(s) — ghi {out_path}")
    return out_path


def _write_response(
    out_path: Path,
    case: dict[str, Any],
    conv_id: str,
    final_text: str,
    tool_calls: list[dict[str, Any]],
    usage: dict[str, Any],
    is_error: bool,
    elapsed_s: float,
) -> None:
    lines: list[str] = []
    lines.append(f"# {case['id']} — run_single (1 agent sonnet, TẤT CẢ tool + TẤT CẢ hướng dẫn)")
    lines.append("")
    lines.append(f"- conv_id (synthetic): `{conv_id}`")
    lines.append(f"- model: `{MODEL}`")
    lines.append(f"- is_error: `{is_error}`")
    lines.append(f"- thời gian: {elapsed_s}s")
    lines.append(f"- usage/cost (ResultMessage): `{json.dumps(usage, ensure_ascii=False, default=str)}`")
    lines.append("")
    lines.append("## Prompt")
    lines.append("")
    lines.append(f"> {case['prompt'].strip()}")
    lines.append("")
    lines.append("## Câu trả lời cuối")
    lines.append("")
    lines.append(final_text or "(rỗng)")
    lines.append("")
    lines.append(f"## Tool-call list ({len(tool_calls)} lời gọi, thứ tự thời gian)")
    lines.append("")
    for i, tc in enumerate(tool_calls, 1):
        lines.append(f"{i}. **{tc['tool']}**")
        lines.append(f"   - input: `{json.dumps(tc['input'], ensure_ascii=False)}`")
        out = tc.get("output")
        out_str = json.dumps(out, ensure_ascii=False, default=str) if out is not None else "(chưa có result khi cắt lượt)"
        lines.append(f"   - output: `{out_str[:800]}`")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def run_case(case_id: str) -> Path:
    return asyncio.run(run_case_async(case_id))


def main() -> None:
    ap = argparse.ArgumentParser(description="Chạy bench case qua 1 SDK session sonnet (single-agent-full-tool)")
    ap.add_argument("--case", help="case id (vd CR-01-floor) hoặc filename không .yaml")
    ap.add_argument("--all", action="store_true", help="chạy TẤT CẢ case trong bench/cases/")
    args = ap.parse_args()

    if not args.case and not args.all:
        ap.error("cần --case <id> hoặc --all")

    if args.all:
        case_files = sorted(CASES_DIR.glob("*.yaml"))
        for f in case_files:
            try:
                run_case(f.stem)
            except Exception as e:  # noqa: BLE001 — 1 case lỗi không chặn cả batch
                print(f"[{f.stem}] LỖI: {e}", file=sys.stderr)
    else:
        run_case(args.case)


if __name__ == "__main__":
    main()
