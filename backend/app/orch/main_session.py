"""SDK lifecycle: MAIN (bền/phòng, resume disk) + SUB (tươi/task). claude-sdk §1-§3 + session.py.

LANDMINE (session.py đã trả giá THẬT):
1. connect/disconnect CÙNG asyncio task (anyio cancel-scope) — disconnect cross-task = TREO IM
   LẶNG. close-on-done: 1 lượt = 1 coroutine trọn gói, disconnect trong finally CỦA CHÍNH task đó.
2. cwd ổn định per-conversation (data/conversations/<id>/) — cwd trôi → resume im lặng mở phiên
   mới, main mất trí nhớ (bẫy #555).
3. bắt session_id ở MỌI kết cục (kể cả is_error). Lệch id → resume_failed, GIỮ id gốc.
4. resume chết (ProcessError) → fresh 1 lần, KHÔNG tính trần retry.

D-16: main=sonnet, sub=haiku (từ providers.yaml — T1-2 dùng model string trực tiếp; providers
routing full ở sprint sau). setting_sources=[] harness sạch, tools=[] chỉ mở qua allowed_tools,
permission_mode='dontAsk' (headless). D-29: SDK live = bonus, mechanics gate không phụ thuộc.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.mount.mount_role import ROLES_DIR, mount_role
from app.orch import registry, store
from app.orch.store import Task

log = logging.getLogger("orch.session")

# cwd gốc per-conversation — neo transcript resume (landmine #2)
CONV_ROOT = Path(__file__).resolve().parents[2] / "data" / "conversations"

MAIN_MODEL = "sonnet"
SUB_MODEL = "haiku"
MAIN_MAX_TURNS = 40
SUB_MAX_TURNS = 20

# Skill điều phối MAIN = vỏ TỰ VIẾT (mỏng — KHÔNG skill nghiệp vụ, N1).
MAIN_SKILL = """Bạn là ĐIỀU PHỐI VIÊN của một chi nhánh ngân hàng số SHB.

Bạn KHÔNG tự thẩm định. Bạn giao việc cho chuyên gia số qua tool orch_dispatch(role, title, input):
- role hợp lệ: "credit" (thẩm định tín dụng: DSCR, LTV, CIC, trần vay) · "legal" (pháp lý: giấy
  tờ, mục đích vay hợp pháp) · "products" (gợi ý gói vay) · "operations" (lộ trình xử lý hồ sơ
  VÀ thực hiện giải ngân khoản vay).
- **operations có HAI loại việc — phân biệt rõ theo YÊU CẦU người dùng, đừng gộp:**
  · Hỏi "lộ trình / timeline / các bước xử lý hồ sơ" → giao brief LẬP LỘ TRÌNH
    (vd input: "Lập lộ trình xử lý hồ sơ vay L001").
  · Yêu cầu "GIẢI NGÂN / chuyển tiền / disburse" một khoản vay (có mã khoản + số tiền)
    → giao brief THỰC HIỆN GIẢI NGÂN, nói THẲNG "thực hiện giải ngân", KHÔNG viết "lập lộ trình".
    (vd title "Giải ngân khoản vay L001", input: "Thực hiện giải ngân khoản vay L001, số tiền
    5.000.000.000 VND. Gọi tool disburse.") — operations sẽ gọi tool disburse (có phanh duyệt).
- Câu hỏi phức tạp cần NHIỀU chuyên gia → giao NHIỀU role LIÊN TIẾP trong cùng lượt (mỗi role 1
  orch_dispatch) — chúng chạy SONG SONG ở nền. Bạn KHÔNG chờ; kết thúc lượt. Mỗi chuyên gia xong,
  hệ thống báo lại bạn bằng một sự kiện kèm kết quả + bảng việc — bạn tổng hợp khi đã đủ.
- Giao xong, tool trả NGAY {status:running}. Muốn biết đội đang làm gì: gọi orch_status().

LUẬT:
- Mọi con số phải CÓ NGUỒN từ tool chuyên gia — KHÔNG tự nhẩm DSCR/LTV/khả năng trả.
- Khi có kết quả từ chuyên gia: tổng hợp lại cho người dùng bằng tiếng Việt, trích số + nguồn.
- Cần tính toán phụ trợ: dùng tool calc, không nhẩm tay.
- Thiếu thông tin (ai, số tiền) → hỏi người dùng 1 câu ngắn.

## Trình tờ trình lên canvas (khi đã tổng hợp xong verdict các chuyên gia)
Khi bạn đã có đủ kết quả từ (các) chuyên gia và chuẩn bị kết luận cho người dùng:
1. Gọi tool `present` TRƯỚC khi viết câu trả lời text, với:
   - type: "document"
   - title: tiêu đề tờ trình (vd "Thẩm định khách C001")
   - items: danh sách [{section: "<tên mục>", content: "<nội dung, trích số + nguồn>"}]
   - sources: danh sách TÊN tool/chuyên gia đã cung cấp số (vd ["credit_assess", "credit_cic_get"])
2. Mọi số trên tờ trình phải từ tool chuyên gia, KHÔNG tự nhẩm. Số nào không có nguồn thì không đưa.
3. Tool trả "card đã lên canvas — tiếp tục" → LÚC ĐÓ viết câu trả lời text ngắn gọn cho người dùng.
"""


def conversation_cwd(conv_id: str) -> Path:
    """Thư mục ổn định per-conversation (resume neo transcript ở đây). Tạo nếu chưa có."""
    # conv_id có thể chứa ký tự lạ (text tự do D-31) → sanitize thành tên thư mục an toàn
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in conv_id)
    d = CONV_ROOT / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def _build_sub_options(task: Task, provider_env: dict[str, str] | None = None) -> Any:
    """Options SUB: SKILL role + toolpack role (mount_role) + common. model=haiku. KHÔNG resume.

    provider_env (D-45): env {ANTHROPIC_BASE_URL/AUTH_TOKEN/API_KEY} chọn gateway SDK per-session.
    subscription (claude-cli) → rỗng → SDK dùng CLI auth. KHÔNG đụng process env (session song song).
    """
    from claude_agent_sdk import ClaudeAgentOptions

    skill, server, allowed = mount_role(task.role)
    from app.orch.common_tools import COMMON_ALLOWED, COMMON_SERVER

    return ClaudeAgentOptions(
        system_prompt=skill,
        model=SUB_MODEL,
        mcp_servers={f"banking_{task.role}": server, "common": COMMON_SERVER},
        tools=[],
        allowed_tools=allowed + COMMON_ALLOWED,
        permission_mode="dontAsk",
        setting_sources=[],
        max_turns=SUB_MAX_TURNS,
        cwd=str(conversation_cwd(task.conv_id)),
        env=provider_env or {},
    )


async def run_sub_turn(task: Task) -> dict[str, Any]:
    """SDK runner THẬT cho _run_sub (seam). Chạy sub tươi tới ResultMessage, trả kết quả text +
    tool-calls. close-on-done: disconnect trong finally CÙNG task. KHÔNG resume (sub disposable).
    """
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

    from app.orch.providers import conv_provider_env

    # D-45b (c): sub cùng conv dùng provider CỦA CONV (nhất quán trải nghiệm). null → server-default.
    conv = await store.get_conversation(task.conv_id)
    penv = conv_provider_env(conv.get("provider") if conv else None)
    brief = task.input or task.title
    client = ClaudeSDKClient(options=_build_sub_options(task, penv))
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    # T4-1 audit: buffer tool_use theo id (input) → match ToolResultBlock (output) → record 1 row đủ.
    # tool_use không có result (turn kết thúc trước) → flush với output null (append-only, không update).
    pending: dict[str, dict[str, Any]] = {}
    try:
        await client.connect()
        await client.query(brief)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                    elif isinstance(block, ThinkingBlock):
                        # T4-2 F1 trace: suy nghĩ sub → SSE thinking (task_id=sub). LIVE-only, không persist.
                        _emit_thinking(task.conv_id, task.id, block.thinking)
                    elif isinstance(block, ToolUseBlock):
                        tool_name = block.name.split("__")[-1]
                        tool_calls.append({"tool": tool_name, "input": block.input})
                        pending[block.id] = {"tool": tool_name, "input": block.input}
            elif isinstance(msg, UserMessage):
                # tool result đến qua UserMessage.content (ToolResultBlock) — match theo tool_use_id.
                for block in getattr(msg, "content", []) or []:
                    if isinstance(block, ToolResultBlock):
                        info = pending.pop(block.tool_use_id, None)
                        if info is not None:
                            await _audit_tool_call(task, info["tool"], info["input"], block.content)
            elif isinstance(msg, ResultMessage):
                pass  # sub không resume → không cần giữ session_id
    finally:
        # flush tool_use chưa có result (output null) — append-only, vẫn ghi audit (§10).
        for info in pending.values():
            await _audit_tool_call(task, info["tool"], info["input"], None)
        try:
            await client.disconnect()
        except Exception as e:  # noqa: BLE001
            log.warning("sub disconnect lỗi: %s", e)
    return {"text": "".join(text_parts), "tool_calls": tool_calls}


async def _audit_tool_call(task: Task, tool: str, tool_input: Any, output: Any) -> None:
    """T4-1: persist 1 tool_call (append-only) + emit SSE toolcall. Best-effort — audit lỗi KHÔNG
    fail sub turn (§12). actor = role sub. task_id/conv_id từ task."""
    from app.orch import store_audit

    try:
        row = await store_audit.record_tool_call(
            task_id=task.id, conv_id=task.conv_id, actor=task.role, tool=tool, tool_input=tool_input, output=output
        )
        if row is not None:
            _emit_toolcall(task.conv_id, row)
    except Exception as e:  # noqa: BLE001 — best-effort, không fail turn
        log.warning("audit tool_call lỗi (bỏ qua): %s", e)


async def _audit_main_tool_call(conv_id: str, tool: str, tool_input: Any, output: Any) -> None:
    """T4-1: persist tool_call của MAIN (actor='main', task_id=None — main gọi tool ngoài sub).
    Best-effort (§12)."""
    from app.orch import store_audit

    try:
        row = await store_audit.record_tool_call(
            task_id=None, conv_id=conv_id, actor="main", tool=tool, tool_input=tool_input, output=output
        )
        if row is not None:
            _emit_toolcall(conv_id, row)
    except Exception as e:  # noqa: BLE001
        log.warning("audit main tool_call lỗi (bỏ qua): %s", e)


def _emit_toolcall(conv_id: str, row: dict[str, Any]) -> None:
    """SSE toolcall §9 {task_id, tool, summary, cost} + `id` (FE upsert live tránh trùng reload+SSE
    chồng — FE yêu cầu; audit row có id nên đưa vào event, mở rộng tương thích SPEC §9). Lazy import;
    lỗi SSE KHÔNG fail (fire-and-forget)."""
    try:
        from app.sse.emit import emit

        summary = json.dumps(row.get("input"), ensure_ascii=False)[:200] if row.get("input") is not None else ""
        emit(
            conv_id,
            "toolcall",
            {
                "id": row.get("id"),  # = tool_calls.id (khớp GET /api/audit row.id) → FE dedup upsert
                "task_id": row.get("task_id"),
                "tool": row["tool"],
                "summary": summary,
                "cost": row.get("cost"),
            },
        )
    except Exception as e:  # noqa: BLE001
        log.warning("emit toolcall lỗi (bỏ qua): %s", e)


def _emit_thinking(conv_id: str, task_id: str | None, text: str) -> None:
    """T4-2 F1 trace: SSE thinking {task_id, text} — suy nghĩ model (ThinkingBlock). task_id=sub role
    · None=main. LIVE-only (KHÔNG persist DB — trace tạm, SPEC không đòi bảng thinking). Fire-and-forget
    (lỗi SSE KHÔNG fail turn). text rỗng → bỏ qua (không emit khối rỗng)."""
    if not text:
        return
    try:
        from app.sse.emit import emit

        emit(conv_id, "thinking", {"task_id": str(task_id) if task_id else None, "text": text})
    except Exception as e:  # noqa: BLE001
        log.warning("emit thinking lỗi (bỏ qua): %s", e)


def _build_main_options(
    conv_id: str, resume: str | None, provider_env: dict[str, str] | None = None, model: str | None = None
) -> Any:
    """Options MAIN: skill điều phối + orch_* + common. model=conv.model hoặc MAIN_MODEL. resume bền.

    D-45b (c): model per-conv override MAIN (null → MAIN_MODEL). Sub GIỮ SUB_MODEL (haiku rẻ, cố ý —
    không promote sub thành model đắt vì user chọn cho chat). model theo provider của conv (dropdown FE).

    provider_env (D-45): xem _build_sub_options. subscription → rỗng → SDK dùng CLI auth.
    """
    from claude_agent_sdk import ClaudeAgentOptions

    from app.orch.common_tools import COMMON_ALLOWED, COMMON_SERVER
    from app.orch.orch_tools import ORCH_ALLOWED, build_orch_server

    return ClaudeAgentOptions(
        system_prompt=MAIN_SKILL,
        model=model or MAIN_MODEL,
        mcp_servers={"orch": build_orch_server(conv_id), "common": COMMON_SERVER},
        tools=[],
        allowed_tools=ORCH_ALLOWED + COMMON_ALLOWED,
        permission_mode="dontAsk",
        setting_sources=[],
        max_turns=MAIN_MAX_TURNS,
        cwd=str(conversation_cwd(conv_id)),
        resume=resume,
        env=provider_env or {},
    )


async def run_main_turn(conv_id: str, prompt: str, on_text: Any = None) -> dict[str, Any]:
    """Chạy 1 lượt MAIN (close-on-done + resume). connect+disconnect CÙNG task này (landmine #1).

    resume = sdk_session_id lưu DB; bắt session_id mới ở ResultMessage (mọi kết cục). on_text =
    callback stream chunk (T1-3 nối SSE). Trả {text, session_id, is_error}.
    """
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeSDKClient,
        ProcessError,
        ResultMessage,
        TextBlock,
        ThinkingBlock,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
    )

    # ContextVar set dòng ĐẦU (brief §E · lab-joint §7): actor='main' + task='' . QUAN TRỌNG cho
    # re-entrant path (sub done → _report → _event_sink → handle_room_event → run_main_turn chạy
    # TRONG task của sub, đường D-33 inline — KHÔNG task mới nên ContextVar KHÔNG tự reset): không
    # set lại thì CTX_ACTOR leak = role sub (audit mis-attribute) VÀ CTX_TASK leak = task.id sub →
    # MAIN present bị stamp task_id sub thay vì null (vi phạm T2-1 N5 "main present → task_id null").
    # Reset CẢ 3 — mirror nhau (fix CTX_TASK leak: tester T2-4 bắt).
    # ⚠️ S3+ BUILDER: THÊM ContextVar mới (set trong _run_sub) → PHẢI thêm reset TƯƠNG ỨNG Ở ĐÂY.
    # Chi phí ẩn của D-33 inline-await: contextvar không auto-reset trên re-entrant path — reset TAY
    # ĐỦ MỌI cái. Grep `registry.CTX_` để thấy danh sách; set ở sub thì reset ở main.
    registry.CTX_CONV.set(conv_id)
    registry.CTX_ACTOR.set("main")
    registry.CTX_TASK.set("")  # main present ngoài sub → task_id null (T2-1)

    from app.orch.providers import conv_provider_env

    # D-45b (c) resume-consistency: provider CỦA CONV — resume + fresh-fallback dùng CÙNG (conv tạo
    # trên X → mọi lượt X). null → server-default. resolve MỘT lần/lượt (cả 2 path dưới dùng chung).
    _conv = await store.get_conversation(conv_id)
    penv = conv_provider_env(_conv.get("provider") if _conv else None)
    cmodel = _conv.get("model") if _conv else None  # D-45b (c): model per-conv → MAIN (null → MAIN_MODEL)
    expected = await store.get_conv_session_id(conv_id)
    try:
        client = ClaudeSDKClient(
            options=_build_main_options(conv_id, resume=expected, provider_env=penv, model=cmodel)
        )
        await client.connect()
    except ProcessError:
        if not expected:
            raise
        log.warning("resume %s chết → fresh (conv %s)", expected, conv_id)
        await store.set_conv_session_id(conv_id, None)
        client = ClaudeSDKClient(
            options=_build_main_options(conv_id, resume=None, provider_env=penv, model=cmodel)
        )
        await client.connect()

    registry.main_clients[conv_id] = client  # cho interrupt (§7) — pop trong finally
    text_parts: list[str] = []
    session_id: str | None = None
    is_error = False
    pending: dict[str, dict[str, Any]] = {}  # T4-1 audit: tool_use theo id chờ match result
    try:
        await client.query(prompt)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                        if on_text is not None:
                            await on_text(block.text)
                    elif isinstance(block, ThinkingBlock):
                        # T4-2 F1 trace: suy nghĩ MAIN → SSE thinking (task_id=None). LIVE-only.
                        _emit_thinking(conv_id, None, block.thinking)
                    elif isinstance(block, ToolUseBlock):
                        pending[block.id] = {"tool": block.name.split("__")[-1], "input": block.input}
            elif isinstance(msg, UserMessage):
                for block in getattr(msg, "content", []) or []:
                    if isinstance(block, ToolResultBlock):
                        info = pending.pop(block.tool_use_id, None)
                        if info is not None:
                            await _audit_main_tool_call(conv_id, info["tool"], info["input"], block.content)
            elif isinstance(msg, ResultMessage):
                session_id = getattr(msg, "session_id", None)
                is_error = bool(getattr(msg, "is_error", False))
    finally:
        # flush tool_use chưa match result (output null) — append-only audit (§10).
        for info in pending.values():
            await _audit_main_tool_call(conv_id, info["tool"], info["input"], None)
        registry.main_clients.pop(conv_id, None)
        try:
            await client.disconnect()  # close-on-done — CÙNG task (landmine #1)
        except Exception as e:  # noqa: BLE001
            log.warning("main disconnect lỗi: %s", e)

    if session_id and session_id != expected:
        # bắt id mới (kể cả lượt đầu expected=None). Lệch khi expected có → resume nghi hỏng,
        # nhưng vẫn lưu id mới để lượt sau resume (session.py giữ id gốc; ở đây S1 đơn giản: lưu mới)
        await store.set_conv_session_id(conv_id, session_id)
    return {"text": "".join(text_parts), "session_id": session_id, "is_error": is_error}


async def _resume_dispatch_guard(conv_id: str, event: str, data: dict) -> bool:
    """T3-4 race fix — re-dispatch giải ngân đã-duyệt TỪ chỗ ops-lần-1 HOÀN TẤT, không đua trước.

    Trả True = ĐÃ XỬ (caller SKIP lượt MAIN — không stale-read, không báo user sai). False = path
    bình thường (caller chạy MAIN như cũ).

    Race (tester T3-4): admin duyệt NHANH hơn ops-lần-1 return → resume-dispatch đua trước
    unregister → created:false → MAIN đọc task_done STALE lần-1 → báo "vẫn chờ duyệt" (sai), phiếu
    approved treo mãi. Fix (architect): server tự re-dispatch khi role FREE, KHÔNG để MAIN đua.

    2 nhánh chặn (grant = approval row approved-chưa-used, advisor: zero state mới):
    A) approval_decided(approved) + role gốc CÒN running → KHÔNG chạy MAIN (FE đã hiện approved qua
       SSE; grant đã persist ở approval row). Kết lượt. Khi ops-lần-1 done → nhánh B tiếp.
    B) task_done + có grant treo → server re-dispatch role đó gọi lại tool (fire-and-forget spawn,
       KHÔNG inline-await — task_done chạy TRONG finally sub đang chết, D-33) + SKIP MAIN report
       lượt này. ops#2 claim → flip 'used' → grant tự clear → task_done kế không grant → MAIN report.

    T4-0 loop-bound: nhánh B peek_grant (không mutate) → claim_exec_attempt (increment atomic khi chắc
    re-dispatch) + trần MAX_EXEC_ATTEMPTS.
    ops#2 fail BỀN → grant treo approved-unused → mỗi task_done re-dispatch tăng attempt → vượt trần
    → KHÔNG dispatch nữa (chống task-storm) + phiếu 'exec_failed' + MAIN báo user "giải ngân lỗi bền".
    """
    from app.orch import store_approvals
    from app.orch.dispatch import orch_dispatch_impl
    from app.orch.gated import GATED_ROLE

    # A) approval_decided approved khi role gốc còn running → đừng để MAIN dispatch đua trước.
    if event == "approval_decided" and data.get("decision") == "approved":
        role = GATED_ROLE.get(data.get("action", ""))
        if role and registry.get_running_task_id(conv_id, role) is not None:
            log.info("resume-guard A: %s còn running, hoãn re-dispatch tới khi task_done (conv %s)", role, conv_id)
            return True  # SKIP MAIN — grant treo ở approval row, nhánh B lo khi role free

    # B) task_done + grant approved-chưa-used treo → server re-dispatch role claim bước 2 (BOUND T4-0).
    if event == "task_done":
        # PEEK grant (KHÔNG increment) — biết role sở hữu + attempt hiện tại. Increment CHỈ khi thật
        # sự re-dispatch (role khớp done_role) → không tốn quota oan khi role KHÁC done.
        grant = await store_approvals.peek_grant(conv_id)
        if grant is None:
            return False  # không grant treo → path bình thường (MAIN report)

        done_role = data.get("role")
        action = grant["action"]
        role = GATED_ROLE.get(action)
        # chỉ xử khi role sở hữu action vừa FREE (task_done của CHÍNH role đó). role đã unregister ở
        # _report TRƯỚC event này. role khác done → path bình thường (grant chờ role đúng).
        if not (role and role == done_role and registry.get_running_task_id(conv_id, role) is None):
            return False

        # VƯỢT TRẦN (T4-0): ops#2 fail BỀN → attempt đã chạm MAX → DỪNG re-dispatch, báo MAIN "lỗi bền".
        if grant["exec_attempts"] >= store_approvals.MAX_EXEC_ATTEMPTS:
            await store_approvals.mark_exec_failed(grant["id"])
            log.warning(
                "resume-guard B: %s vượt trần %d lần re-dispatch → exec_failed (conv %s)",
                action,
                store_approvals.MAX_EXEC_ATTEMPTS,
                conv_id,
            )
            # KHÔNG SKIP — để MAIN báo user. NHƯNG KHÔNG cược model đọc error trong result_summary:
            # inject signal DETERMINISTIC vào data → _build_event_prompt task_done nhánh exec_failed →
            # MAIN nhận prompt RÕ "giải ngân lỗi bền sau N lần, cần người" (không phụ suy luận model).
            data["exec_failed"] = {
                "action": action,
                "attempts": store_approvals.MAX_EXEC_ATTEMPTS,
                "payload_summary": ", ".join(f"{k}={v}" for k, v in (grant.get("payload") or {}).items()),
            }
            return False

        # CÒN quota → increment atomic (chỉ khi chắc chắn re-dispatch) → dispatch ops#2.
        attempt = await store_approvals.claim_exec_attempt(grant["id"])
        payload_summary = ", ".join(f"{k}={v}" for k, v in (grant.get("payload") or {}).items())
        brief = (
            f"Thực hiện {action} ĐÃ ĐƯỢC DUYỆT: {payload_summary}. Gọi lại tool {action} "
            f"ĐÚNG tham số này để hoàn tất (phiếu đã duyệt, lần này chạy thật)."
        )
        title = f"Thực thi {action} đã duyệt ({payload_summary})"
        log.info("resume-guard B: re-dispatch %s claim %s lần %d (conv %s)", role, action, attempt, conv_id)
        # fire-and-forget: orch_dispatch_impl tự spawn_sub nền — KHÔNG await (nest sub chết)
        await orch_dispatch_impl(conv_id, role, title, brief)
        return True  # SKIP MAIN report lượt này (ops#2 done sẽ báo hoàn tất — self-contained)
    return False


async def _turn_runner(conv_id: str, event: str, data: dict) -> None:
    """Nối handle_room_event → run_main_turn + SSE stream (T1-3). Vỏ đưa dữ kiện, não quyết (N1).

    Stream chat.delta chunk qua on_text; MỌI kết lượt (xong/lỗi) bắn chat.delta done (Gap1) +
    persist message assistant/system + conversation.status. Lỗi main → message sender='system'
    (Gap2 — user thấy lịch sử). uuid turn_id cho seq per-turn (streaming-sse §3).

    T3-4: _resume_dispatch_guard chặn 2 nhánh race resume-dispatch TRƯỚC khi chạy MAIN (xem docstring)."""
    import uuid

    from app.sse.emit import emit_chat_delta, emit_chat_done, emit_conversation_status

    # T3-4 race guard — ĐÃ xử (re-dispatch/hoãn) → SKIP lượt MAIN (không stale-read, không báo sai).
    if await _resume_dispatch_guard(conv_id, event, data):
        return

    prompt = _build_event_prompt(event, data)
    turn_id = str(uuid.uuid4())

    await store.set_conv_status(conv_id, "running")
    emit_conversation_status(conv_id, "running")

    async def on_text(chunk: str) -> None:
        emit_chat_delta(conv_id, turn_id, chunk)

    try:
        result = await run_main_turn(conv_id, prompt, on_text=on_text)
        text = result["text"]
        if result["is_error"]:
            # lỗi main trong lượt (is_error) — Gap2: message system + status failed
            await store.add_message(conv_id, "system", text or "Lượt xử lý gặp lỗi.")
            emit_chat_done(conv_id, turn_id, text)
            await store.set_conv_status(conv_id, "failed")
            emit_conversation_status(conv_id, "failed")
        else:
            if text:
                await store.add_message(conv_id, "assistant", text)  # persist TRƯỚC done (§5)
            emit_chat_done(conv_id, turn_id, text)  # Gap1: MỌI kết lượt bắn done
            await store.set_conv_status(conv_id, "idle")
            emit_conversation_status(conv_id, "idle")
    except Exception as e:  # noqa: BLE001 — lượt main nổ (SDK/provider): Gap1+Gap2, không chết im
        import logging

        logging.getLogger("orch.session").error("lượt main lỗi conv %s: %s", conv_id, e)
        msg = f"Hệ thống gặp lỗi khi xử lý: {str(e)[:200]}. Anh/chị gửi lại tin nhắn để tiếp tục."
        await store.add_message(conv_id, "system", msg)
        emit_chat_done(conv_id, turn_id, "")  # Gap1: done dù rỗng → bubble FE không treo
        await store.set_conv_status(conv_id, "failed")
        emit_conversation_status(conv_id, "failed")


def _build_event_prompt(event: str, data: dict) -> str:
    if event == "user_message":
        return f"Tin nhắn người dùng: {data['content']}"
    if event == "task_done":
        # T4-0: guard-B đã đánh dấu grant exec_failed sau khi vượt trần re-dispatch → prompt RÕ cho
        # MAIN báo user lỗi bền (DETERMINISTIC — không cược model đọc error trong result_summary).
        ef = data.get("exec_failed")
        if ef:
            return (
                f"Sự kiện: '{ef['action']}' ({ef['payload_summary']}) đã được duyệt nhưng THỰC THI "
                f"THẤT BẠI BỀN sau {ef['attempts']} lần thử lại — hệ thống đã DỪNG tự động (không thử "
                f"tiếp). Báo người dùng: giao dịch này KHÔNG hoàn tất được, CẦN NGƯỜI kiểm tra thủ công "
                f"(vd khoản vay lỗi/không tồn tại). KHÔNG tự thử lại."
            )
        # T4-5 dọn 2-card-trùng: sau resume giải ngân, Ops sub ĐÃ present biên nhận lên canvas. Nếu
        # MAIN present LẠI khi tổng hợp → 2 card "Biên nhận" trùng (tester S3 bắt). Predicate HẸP:
        # role=operations + done + result có receipt (disbursed) = ops#2 execution-done → dặn MAIN
        # KHÔNG present lại (chỉ text ngắn). CHỈ path này — KHÔNG đụng #1 (main pre-approval summary).
        role = data.get("role")
        summary = data.get("result_summary") or ""
        if role == "operations" and data.get("outcome") == "done" and "disbursed" in summary:
            return (
                f"Sự kiện: chuyên gia operations đã HOÀN TẤT giải ngân (biên nhận: {summary}). "
                f"Chuyên gia đã TRÌNH BIÊN NHẬN lên canvas rồi — bạn KHÔNG present/trình lại thẻ nào, "
                f"CHỈ viết 1 câu ngắn báo người dùng giải ngân đã hoàn tất (trích số tiền + mã khoản)."
            )
        return (
            f"Sự kiện: chuyên gia {data['role']} kết thúc [{data['outcome']}]. "
            f"Kết quả: {data['result_summary']}\nBảng việc hiện tại: {json.dumps(data['board'], ensure_ascii=False)}"
        )
    if event == "approval_decided":
        # T3-2 resume (§4.4/§8): mặt model nói THEO HÀNH ĐỘNG + tham số, KHÔNG phiếu-id (§15).
        # main giao lại Ops đúng payload để wrapper bước 2 claim. approved → thực thi; rejected → báo user.
        action = data["action"]
        payload_summary = ", ".join(f"{k}={v}" for k, v in (data.get("payload") or {}).items())
        if data["decision"] == "approved":
            return (
                f"Sự kiện: hành động '{action}' ({payload_summary}) đã được NGƯỜI DUYỆT chấp thuận. "
                f"Hãy giao lại cho chuyên gia Vận hành (operations) gọi lại '{action}' ĐÚNG tham số "
                f"({payload_summary}) để thực thi. Xong thì báo người dùng kết quả."
            )
        return (
            f"Sự kiện: hành động '{action}' ({payload_summary}) đã bị NGƯỜI DUYỆT TỪ CHỐI. "
            f"KHÔNG thực thi. Báo người dùng đã bị từ chối và lý do (nếu có)."
        )
    return json.dumps(data, ensure_ascii=False)


def boot() -> None:
    """Gọi lúc app startup: gán runner SDK thật cho seam + nối event sink. Tách khỏi test
    (test mechanics KHÔNG gọi boot → không đụng SDK)."""
    from app.orch import room, sub_runner

    sub_runner.set_default_runner(run_sub_turn)
    room.set_turn_runner(_turn_runner)
    room.wire_event_sink()


def roles_available() -> list[str]:
    if not ROLES_DIR.exists():
        return []
    return [p.name for p in ROLES_DIR.iterdir() if p.is_dir() and (p / "functions.py").exists()]
