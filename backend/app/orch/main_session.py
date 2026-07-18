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
        ToolUseBlock,
    )

    from app.orch.providers import server_provider_env

    brief = task.input or task.title
    client = ClaudeSDKClient(options=_build_sub_options(task, server_provider_env()))
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    try:
        await client.connect()
        await client.query(brief)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        tool_calls.append({"tool": block.name.split("__")[-1], "input": block.input})
            elif isinstance(msg, ResultMessage):
                pass  # sub không resume → không cần giữ session_id
    finally:
        try:
            await client.disconnect()
        except Exception as e:  # noqa: BLE001
            log.warning("sub disconnect lỗi: %s", e)
    return {"text": "".join(text_parts), "tool_calls": tool_calls}


def _build_main_options(conv_id: str, resume: str | None, provider_env: dict[str, str] | None = None) -> Any:
    """Options MAIN: skill điều phối + orch_* + common. model=sonnet. resume phiên bền.

    provider_env (D-45): xem _build_sub_options. subscription → rỗng → SDK dùng CLI auth.
    """
    from claude_agent_sdk import ClaudeAgentOptions

    from app.orch.common_tools import COMMON_ALLOWED, COMMON_SERVER
    from app.orch.orch_tools import ORCH_ALLOWED, build_orch_server

    return ClaudeAgentOptions(
        system_prompt=MAIN_SKILL,
        model=MAIN_MODEL,
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

    from app.orch.providers import server_provider_env

    penv = server_provider_env()  # resolve MỘT lần/lượt — resume + fresh dùng CÙNG provider
    expected = await store.get_conv_session_id(conv_id)
    try:
        client = ClaudeSDKClient(options=_build_main_options(conv_id, resume=expected, provider_env=penv))
        await client.connect()
    except ProcessError:
        if not expected:
            raise
        log.warning("resume %s chết → fresh (conv %s)", expected, conv_id)
        await store.set_conv_session_id(conv_id, None)
        client = ClaudeSDKClient(options=_build_main_options(conv_id, resume=None, provider_env=penv))
        await client.connect()

    registry.main_clients[conv_id] = client  # cho interrupt (§7) — pop trong finally
    text_parts: list[str] = []
    session_id: str | None = None
    is_error = False
    try:
        await client.query(prompt)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                        if on_text is not None:
                            await on_text(block.text)
            elif isinstance(msg, ResultMessage):
                session_id = getattr(msg, "session_id", None)
                is_error = bool(getattr(msg, "is_error", False))
    finally:
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


async def _turn_runner(conv_id: str, event: str, data: dict) -> None:
    """Nối handle_room_event → run_main_turn + SSE stream (T1-3). Vỏ đưa dữ kiện, não quyết (N1).

    Stream chat.delta chunk qua on_text; MỌI kết lượt (xong/lỗi) bắn chat.delta done (Gap1) +
    persist message assistant/system + conversation.status. Lỗi main → message sender='system'
    (Gap2 — user thấy lịch sử). uuid turn_id cho seq per-turn (streaming-sse §3)."""
    import uuid

    from app.sse.emit import emit_chat_delta, emit_chat_done, emit_conversation_status

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
