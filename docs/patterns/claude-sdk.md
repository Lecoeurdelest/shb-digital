# Pattern: claude-agent-sdk (Python) cho hệ Digital Expert Guild (#132)

> Tài liệu TỰ CHỨA: người build đọc doc này + `SPEC.md` là code được phần runtime SDK,
> không cần mở repo nào khác. Mọi snippet là pattern viết cho CHÍNH hệ này — tên domain theo spec:
> `conversation` (1 ca = 1 phòng), `main` (MAIN điều phối), `sub` (SUB chuyên gia), `role`
> (credit/legal/products/operations). 3 server tool theo spec §5: `orch` (điều phối, CHỈ main) ·
> `banking_<role>` (nghiệp vụ) · `common` (calc + present, mọi role).
> Doc này giữ phần THUẦN SDK; cơ chế lượt/queue/hủy → `multi-agent.md`; mount/schema → `lab-joint.md`.

**Ánh xạ nhanh spec → SDK:**

| Khái niệm spec | Hiện thực SDK |
|---|---|
| MAIN = session BỀN per conversation (§3, §8 spec) | `ClaudeSDKClient` + `options.resume=<session_id>` — transcript SDK tự lưu trên disk |
| SUB = client TƯƠI mỗi task (§3 spec) | `ClaudeSDKClient` mới mỗi lần `orch_dispatch`, chạy xong disconnect, KHÔNG resume |
| SKILL = text thô (§7 spec) | `options.system_prompt` |
| Toolpack role + tool chung (§5, §7 spec) | in-process MCP server (`@tool` + `create_sdk_mcp_server`) mount qua `options.mcp_servers`, scope bằng `allowed_tools` |
| 1 lượt/phòng (§4.2 spec) | slot + hàng đợi phòng — cơ chế đầy đủ: `multi-agent.md` §2 |
| Hủy per-agent (§4.3 spec) | `client.interrupt()` (main) / cancel task nền của sub — cơ chế đầy đủ: `multi-agent.md` §7 |
| Cost meter (§9 spec, SSE `toolcall`) | `usage` + `total_cost_usd` đọc từ `ResultMessage` mỗi lượt |
| Đa provider (§12 spec) | `options.env` per-session (base-url + key), routing model theo `providers.yaml` |

---

## 1. ClaudeSDKClient lifecycle — connect → query → receive → disconnect

### Nguyên lý

Mỗi `ClaudeSDKClient` khi `connect()` **spawn một subprocess CLI ngầm** (~300MB RAM + pipe + vòng
đọc stream). Client không phải object nhẹ — nó là một PROCESS. Hệ quả:

- **Quên `disconnect()` = leak process + RAM.** Mỗi lượt main + mỗi sub đều mở client; một ca demo
  vài chục lượt mà rò là server OOM giữa buổi thi.
- **`connect()` và `disconnect()` PHẢI nằm trong CÙNG một asyncio task.** Transport bên dưới dùng
  anyio cancel-scope gắn vào task đã mở nó — gọi `disconnect()` từ task khác (background cleaner,
  handler của lượt sau…) không ném lỗi mà **treo im lặng**. Đây là loại bug khó debug nhất: không
  stacktrace, chỉ thấy phòng đứng hình.

Từ hai ràng buộc trên suy ra pattern chuẩn của hệ: **close-on-done** — MỘT lượt = MỘT coroutine
trọn gói `connect → query → receive → disconnect`, tự đóng ngay cuối lượt trong chính task đó.
Tính liên tục KHÔNG đến từ việc giữ client sống, mà đến từ **resume** ở lượt sau (§3).

`receive_response()` là async iterator, **tự kết thúc sau `ResultMessage`** — không cần break tay.
Các message type cần xử trong loop:

| Message / Block | Chứa gì | Hệ mình dùng làm gì |
|---|---|---|
| `AssistantMessage` | list content blocks | bóc từng block bên dưới |
| ├ `TextBlock` | `.text` | câu trả lời chat (stream ra SSE `chat.delta`) |
| ├ `ThinkingBlock` | `.thinking` | trace (hiện trong sub trace view, không ra chat) |
| └ `ToolUseBlock` | `.name`, `.input`, `.id` | SSE `toolcall` + sổ `tool_calls` |
| `ResultMessage` | `.session_id`, `.usage`, `.total_cost_usd`, `.is_error` | chốt lượt: lưu session_id (§3) + ghi cost (§6) |

### Pattern

```python
from claude_agent_sdk import (
    ClaudeSDKClient, AssistantMessage, TextBlock, ThinkingBlock,
    ToolUseBlock, ResultMessage,
)

async def run_turn(options, prompt: str) -> TurnResult:
    """MỘT lượt trọn gói trong MỘT coroutine — connect/disconnect cùng task."""
    client = ClaudeSDKClient(options=options)
    text, session_id, usage, cost, is_error = "", None, None, 0.0, False
    try:
        await client.connect()
        await client.query(prompt)
        async for message in client.receive_response():   # tự dừng sau ResultMessage
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text += block.text
                        await sse.chat_delta(block.text)
                    elif isinstance(block, ThinkingBlock):
                        await trace.thinking(block.thinking)
                    elif isinstance(block, ToolUseBlock):
                        await trace.toolcall(block.name, block.input)
            elif isinstance(message, ResultMessage):
                session_id = message.session_id           # CÓ ở mọi kết cục, kể cả error
                usage = message.usage
                cost = message.total_cost_usd or 0.0
                is_error = bool(message.is_error)
    finally:
        try:
            await client.disconnect()                     # close-on-done: MỌI nhánh thoát
        except Exception:
            log.warning("disconnect failed", exc_info=True)
    return TurnResult(text=text, session_id=session_id,
                      usage=usage, cost=cost, is_error=is_error)
```

Bọc timeout ngoài loop khi cần trần cứng (sub mặc định có timeout — spec §4.1):

```python
async with asyncio.timeout(SUB_TIMEOUT_SECONDS):
    result = await run_turn(options, prompt)
# TimeoutError → vẫn phải disconnect (finally trong run_turn đã lo) + PHÁT EVENT
# "task timeout" báo main — invariant spec §4.2: không có đường chết im lặng.
```

### Lưu ý

| Bẫy | Rule |
|---|---|
| Quên `disconnect()` (return sớm, exception, timeout) | `disconnect()` trong `finally`, bọc try/except riêng — leak ~300MB/client tới OOM |
| Giữ client sống giữa các lượt, lượt sau (task khác) mới disconnect | cross-task disconnect = **treo im lặng** (anyio cancel-scope đòi cùng task). Close-on-done + revive bằng resume |
| `break` khỏi `receive_response()` trước `ResultMessage` | mất session_id + cost. Để iterator tự kết thúc; muốn cắt sớm dùng `interrupt()` (§5) |
| Coi timeout là "xong việc rồi thôi" | timeout cũng là MỘT kết cục → disconnect + phát đúng 1 event báo main (spec §4.2) |
| Đọc `.text` trên mọi block không phân loại | ThinkingBlock không có `.text` — phân nhánh theo isinstance, đừng duck-type |

---

## 2. ClaudeAgentOptions — cấu hình một agent của hệ

### Nguyên lý

`ClaudeAgentOptions` là toàn bộ "hộ chiếu" của một agent: nó là AI nào (model), biết gì
(system_prompt = SKILL), được cầm tool gì (mcp_servers + allowed_tools), sống ở đâu (cwd), tiêu
bao nhiêu (max_turns/max_budget_usd), gọi provider nào (env). Vỏ build options **từ config role**,
không hardcode — đúng N3 (vỏ mù nội dung) và §12 (không hardcode model).

Ba quyết định quan trọng riêng của hệ:

1. **Harness sạch**: `setting_sources=[]` — không nạp settings/CLAUDE.md/skill của máy host vào
   agent. Thiếu dòng này, agent production nuốt config developer local → hành vi lệch không tái lập.
2. **Tắt built-in tools**: `tools=[]` rồi chỉ mở qua `allowed_tools`. Sub Credit không có lý do gì
   được cầm Bash/Read/Write — mọi năng lực đi qua toolpack MCP đã audit (N2: gate ở tầng tool).
3. **`cwd` PHẢI ổn định per conversation**: SDK lưu transcript theo cwd; `resume` tìm transcript
   **trong cwd hiện tại**. Lượt 1 chạy cwd A, lượt 2 chạy cwd B → resume không thấy transcript →
   **im lặng mở phiên mới** — main "mất trí nhớ" mà không có lỗi nào báo. Chuẩn hệ:
   `data/conversations/<conversation_id>/` tạo lúc mở ca, dùng suốt đời ca.

### Pattern

```python
from claude_agent_sdk import ClaudeAgentOptions

def build_options(*, skill_text: str, role_kind: str, conversation,
                  mcp_servers: dict, allowed_tools: list[str],
                  resume: str | None) -> ClaudeAgentOptions:
    route = routing_for(role_kind)            # §7: providers.yaml — model + env theo vai
    return ClaudeAgentOptions(
        system_prompt=skill_text,             # SKILL.md nguyên văn — vỏ không parse (N3)
        model=route.model,                    # main = model mạnh, sub = model rẻ
        mcp_servers=mcp_servers,              # dict in-process (§4)
        tools=[],                             # TẮT built-in (Bash/Read/Write/...)
        allowed_tools=allowed_tools,          # scope đúng role — SDK cưỡng chế cứng
        permission_mode="dontAsk",            # headless: không có người bấm approve tool
        setting_sources=[],                   # harness sạch — không nạp config máy host
        max_turns=route.max_turns,            # trần lượt agentic
        max_budget_usd=route.max_budget_usd,  # trần tiền — SDK tự cắt
        cwd=conversation.workdir,             # ỔN ĐỊNH per conversation — neo transcript resume
        env=route.provider_env,               # per-session base-url + key (§7)
        resume=resume,                        # None = phiên mới; main truyền session_id đã lưu
    )
```

Phân vai cụ thể:

```python
# MAIN — skill mỏng vỏ tự viết + tool điều phối + tool chung, resume phiên bền
main_opts = build_options(
    skill_text=MAIN_SKILL, role_kind="main", conversation=conv,
    mcp_servers={"orch": ORCH_SERVER, "common": COMMON_SERVER},
    allowed_tools=["mcp__orch__orch_dispatch", "mcp__orch__orch_status",
                   "mcp__common__present", "mcp__common__calc"],
    resume=conv.sdk_session_id,
)
# SUB credit — SKILL role + toolpack role (mount qua lab-joint §2) + tool chung, KHÔNG resume.
# Sub KHÔNG mount server `orch` — ranh quyền cắt từ tầng mount: sub vật lý không giao việc được.
sub_opts = build_options(
    skill_text=role.skill_text, role_kind="sub", conversation=conv,
    mcp_servers={f"banking_{role.name}": role.server, "common": COMMON_SERVER},
    allowed_tools=[*role.allowed_tools, "mcp__common__present", "mcp__common__calc"],
    resume=None,
)
```

### Lưu ý

| Bẫy | Rule |
|---|---|
| `cwd` trôi giữa các lượt (cwd process, tmp dir mới mỗi lượt) | resume **im lặng mở phiên mới** — mất trí nhớ không báo lỗi. Cwd cố định `data/conversations/<id>/`, tạo 1 lần lúc mở ca |
| Quên `setting_sources=[]` | agent nuốt settings/CLAUDE.md máy host — hành vi lệch giữa dev và deploy, không tái lập |
| Để built-in tools mặc định | sub cầm được Bash/Write ngoài mọi audit — vỡ N2. `tools=[]` + chỉ mở qua `allowed_tools` |
| Quên `permission_mode="dontAsk"` | agent headless dừng chờ người bấm approve — treo phòng |
| Không đặt `max_turns`/`max_budget_usd` cho sub | sub loop vô hạn đốt tiền — spec §4.1 bắt buộc giới hạn |
| Set env provider vào `os.environ` thay vì `options.env` | race giữa các session đa provider (§7) — env là per-client, không đụng process env |

---

## 3. Session resume từ disk — MAIN bền, SUB tươi

### Nguyên lý

SDK/CLI **tự lưu transcript** mỗi phiên xuống disk (dưới cwd). Continuity của hệ = chính transcript
này (spec §8: "DB KHÔNG phải nguồn resume"). Chu trình:

1. Lượt chạy xong → `ResultMessage.session_id` là **id có thẩm quyền** (kể cả lượt lỗi
   `is_error=True` vẫn có ResultMessage kèm session_id — bắt ở MỌI kết cục).
2. Lưu id vào `conversations.sdk_session_id` (DB chỉ là chỗ CẤT id, không phải nguồn context).
3. Lượt sau: `options.resume = id` → SDK nạp lại nguyên ngữ cảnh — qua các lượt và qua cả restart
   server.

Hai kiểm tra bắt buộc quanh resume:

- **Verify id khớp**: khi đã truyền `resume=X`, id trong ResultMessage phải là `X`. Trả về id khác
  = resume đã hỏng (transcript không tìm thấy / cwd lệch) và SDK đã lặng lẽ mở phiên mới. Ghi vết
  `resume_mismatch`, **không đè id gốc** — id gốc còn cơ hội cứu (sửa cwd, điều tra), đè là mất dấu.
- **Resume chết cứng** (`ProcessError` lúc connect — transcript bị xoá/hỏng): fallback connect
  fresh đúng 1 lần. Mất context nhưng phiên còn sống — tốt hơn chết hẳn. Ghi sự kiện
  `resume_failed` vào audit để biết ca này đã mất trí nhớ từ lượt nào.

**Ánh xạ hệ mình:** MAIN = session bền, resume mỗi lượt. SUB = disposable, client tươi mỗi task,
nhận ngữ cảnh qua `input` của task, **không resume** — xong là hết đời (spec §3). Đừng "tối ưu"
cho sub nhớ giữa các lần dispatch: thêm state, thêm đường hỏng, không đổi lại được gì vì ngữ cảnh
task đã nằm trong input.

### Pattern

```python
from claude_agent_sdk import ProcessError

async def run_main_turn(conv, prompt: str) -> TurnResult:
    expected = conv.sdk_session_id                     # None = ca mới
    opts = build_main_options(conv, resume=expected)
    try:
        result = await run_turn(opts, prompt)          # §1
    except ProcessError:
        if not expected:
            raise                                      # phiên mới mà chết = lỗi thật, nổi lên
        audit("resume_failed", conv_id=conv.id, session_id=expected)
        conv.sdk_session_id = None                     # từ nay chạy đời session mới
        opts = build_main_options(conv, resume=None)
        result = await run_turn(opts, prompt)          # fallback fresh: mất context, phiên sống

    sid = result.session_id                            # có ở MỌI kết cục, kể cả is_error
    if sid:
        if expected and sid != expected:
            # resume hỏng ngầm — KHÔNG đè id gốc, ghi vết để điều tra (thường do cwd lệch)
            audit("resume_mismatch", conv_id=conv.id, expected=expected, got=sid)
        else:
            await db.save_session_id(conv.id, sid)     # lượt sau resume bằng id này
            conv.sdk_session_id = sid
    return result
```

Sống qua restart (spec §8): server sập → sống lại, `sdk_session_id` còn trong DB, cwd còn trên
disk → user chat tiếp là lượt sau resume bình thường. Không build máy cứu-ca — chỉ việc đang chạy
dở phải làm lại.

### Lưu ý

| Bẫy | Rule |
|---|---|
| Chỉ bắt session_id khi lượt thành công | lượt lỗi vẫn có ResultMessage + session_id — bắt ở MỌI kết cục, nếu không lượt sau resume id cũ đã stale |
| Id trả về ≠ id chờ mà cứ lưu đè | đó là dấu hiệu resume hỏng (cwd lệch là thủ phạm số 1) — ghi `resume_mismatch`, GIỮ id gốc |
| `ProcessError` → chết luôn lượt | fallback fresh 1 lần + `resume_failed` vào audit — phiên sống quan trọng hơn context |
| Fallback fresh lặp vô hạn | retry-fresh đúng 1 lần; fresh mà vẫn chết = lỗi hạ tầng, nổi lên cho user |
| Cho SUB resume "để nó nhớ" | sub là disposable theo spec — ngữ cảnh đi qua input task; resume sub = thêm state vô ích |
| Tin DB làm nguồn context | DB chỉ cất id + render UI; nguồn context duy nhất là transcript SDK trên disk (spec §8) |

---

## 4. In-process MCP server — @tool, create_sdk_mcp_server, mount_role

### Nguyên lý

Toàn bộ tool của hệ (điều phối `orch_*`, nghiệp vụ `banking_<role>_*`, chung `calc`/`present`)
chạy **in-process** — không server ngoài, không network hop: handler là coroutine Python trong
chính process FastAPI, được SDK gọi khi model phát tool_use. Ba bước:

1. `@tool(name, description, input_schema)` bọc một handler
   `async def handler(args: dict) -> dict` — return **bắt buộc đúng envelope MCP**:
   `{"content": [{"type": "text", "text": <chuỗi>}]}`.
2. `create_sdk_mcp_server(name=<server>, version=..., tools=[...])` gom các tool thành 1 server.
3. Mount vào `options.mcp_servers = {"<server>": server_obj}` → tên tool mà model thấy (và tên
   phải khai trong `allowed_tools`) là **`mcp__<server>__<tool>`**. Quên khai trong allowed_tools
   = tool bị harness chặn im lặng — model gọi mãi không được.

**Bẫy schema — quan trọng nhất mục này.** SDK nhận `input_schema` 2 dạng: shorthand
`{param: type}` hoặc full JSON Schema. **Cấm shorthand trong hệ này**: shorthand ép MỌI param
thành required → tool có param optional sẽ vỡ — SDK validate và **reject tool_use TRƯỚC KHI
handler chạy**, model không thấy lý do thật, kẹt vòng retry gọi đi gọi lại rồi bỏ cuộc. Luật
(khớp spec §7): build **full JSON Schema**, `required` / `enum` / `default` nằm **TRONG schema**
(không chỉ ghi trong description). Và **enum phải khớp KIỂU phần tử**: `{"type": "string",
"enum": [1, 2, 3]}` là schema **bất khả** — không giá trị nào thoả cả hai → mọi tool_use bị
reject trước handler. Suy `type` từ chính phần tử của `values`.

### Pattern

Tool viết tay (tool điều phối của vỏ):

```python
import json
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool(
    name="orch_dispatch",
    description="Giao việc cho 1 SUB chuyên gia theo role. Trả {role, status} NGAY, sub chạy "
                "nền — KHÔNG chờ; dispatch tiếp hoặc kết thúc lượt. Trùng role đang chạy "
                "→ báo đang chạy, không spawn con thứ hai. KHÔNG dùng để hỏi tình hình đội "
                "— đó là việc của orch_status.",
    input_schema={
        "type": "object",
        "properties": {
            # enum SINH ĐỘNG từ roles/ đã mount — thêm phòng ban không sửa tool (spec §3)
            "role":  {"type": "string", "enum": sorted(discovered_roles())},
            "title": {"type": "string", "description": "tên việc, hiện trên bảng việc"},
            "input": {"type": "string", "description": "ngữ cảnh + yêu cầu cho sub"},
        },
        "required": ["role", "title", "input"],
    },
)
async def orch_dispatch(args: dict) -> dict:
    result = await dispatch_task(ctx_conversation_id.get(),   # attribution qua ContextVar
                                 args["role"], args["title"], args["input"])
    return {"content": [{"type": "text",
                         "text": json.dumps(result, ensure_ascii=False)}]}

# 3 server đúng spec §5 — tên chốt 1 lần, allowed_tools khớp string tuyệt đối:
ORCH_SERVER   = create_sdk_mcp_server(name="orch", version="1.0.0",
                                      tools=[orch_dispatch, orch_status])   # CHỈ main mount
COMMON_SERVER = create_sdk_mcp_server(name="common", version="1.0.0",
                                      tools=[present, calc])                # mọi role mount
```

**Mount tool nghiệp vụ từ LAB (`mount_role` + schema builder): chủ nhà là `lab-joint.md` §2 —
không copy về đây.** Bản đó là bản DUY NHẤT (xử đủ `list[str]`, enum khớp kiểu, `default`/
`maximum` vào schema, chặn `bad_param`); mount và `allowed_tools` sinh từ cùng một vòng lặp.

Lưu ý phanh (spec §4.4): wrapper gated trả error 4-field `approval_required` là **kết quả tool
bình thường** dưới góc nhìn SDK — handler return envelope text như thường, không raise. Não đọc
`hint` và tự kết thúc lượt chờ duyệt.

### Lưu ý

| Bẫy | Rule |
|---|---|
| Schema shorthand `{param: type}` | ép MỌI param required — tool có optional vỡ, SDK reject trước handler, model kẹt retry. Luôn full JSON Schema |
| `required`/`enum`/`default` chỉ ghi trong description | model đọc được nhưng validator không — hai nguồn sự thật lệch nhau. Tất cả nằm TRONG schema |
| Enum không khớp kiểu (`type: string` + `enum: [1,2,3]`) | schema bất khả → MỌI tool_use bị reject trước handler. Suy type từ phần tử values; check bool trước int |
| Property key non-ASCII (dấu tiếng Việt) | API reject 400. Key ASCII `^[a-zA-Z0-9_.-]`; values/description tiếng Việt thoải mái |
| Mount server nhưng quên thêm `mcp__<server>__<tool>` vào allowed_tools | tool bị harness chặn IM LẶNG — model gọi hoài không được. Mount và allowed sinh từ CÙNG một vòng lặp |
| Handler return dict thường / raise exception | phải return envelope `{"content":[{"type":"text","text":...}]}`; lỗi nghiệp vụ → error 4-field TRONG envelope, không raise |
| Handler sync hoặc gọi HTTP sync trong handler | block event loop — N phòng song song đứng dây chuyền. Handler async, I/O async |

---

## 5. Interrupt & ranh cancel — 4 fact thuần SDK

> Cơ chế lượt/hàng đợi/hủy per-agent ĐẦY ĐỦ (slot, queue, drain, registry, đường hủy sub):
> **chủ nhà là `multi-agent.md` §2 + §7** — doc này chỉ giữ các fact thuộc về SDK mà cơ chế
> đó phải tôn trọng.

1. **`interrupt()` gọi cross-task ĐƯỢC** — đây là cách duy nhất cắt lượt đang chạy từ bên
   ngoài (handler API hủy). Loop `receive_response` kết thúc, task gốc tự close-on-done.
2. **`disconnect()` cross-task CẤM** — anyio cancel-scope đòi cùng task với `connect()`
   (bẫy #2 §8). Handler hủy chỉ interrupt; disconnect vẫn thuộc task gốc.
3. **`interrupt()` kết thúc ÊM, không raise** trong task gốc — vòng đời sub bị hủy phải TỰ
   đánh dấu kết cục `failed("user hủy")` và phát event báo main (không có exception nào làm
   hộ việc đó — invariant spec §4.2).
4. **Registry client sống đăng ký SAU `connect()`, gỡ trong `finally`** — đăng ký trước
   connect là hủy được client chưa mở (no-op sai); quên gỡ là `orch_status` nói dối "đang chạy".

---

## 6. Usage & cost — sổ cost meter

### Nguyên lý

Mỗi lượt kết thúc bằng `ResultMessage` mang `usage` (input/output/cache tokens) và
`total_cost_usd`. Đây là **nguồn duy nhất** của cost meter (SSE `toolcall` có trường `cost`,
cột `cost` trong `tasks`/`tool_calls`). Ghi **per lượt, per actor** (main hay sub nào) —
fire-and-forget như audit (spec §5): sổ lỗi không được fail lượt chính.

Chạy qua proxy đa provider (§7), `total_cost_usd` có thể là 0/None (proxy không báo giá) —
fallback tự tính từ tokens × bảng giá trong `providers.yaml`. Không để cost meter câm chỉ vì
đổi provider.

### Pattern

```python
def extract_cost(result_message) -> dict:
    u = result_message.usage or {}
    return {
        "input_tokens": u.get("input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "cache_read_tokens": u.get("cache_read_input_tokens", 0),
        "cost_usd": result_message.total_cost_usd,      # None/0 nếu proxy không báo
    }

async def record_turn_cost(conv_id: str, actor: str, task_id: str | None,
                           result: TurnResult, route) -> None:
    cost = dict(result.cost_record)                     # extract_cost từ ResultMessage
    if not cost["cost_usd"]:                            # proxy câm giá → tự tính
        price = route.pricing                           # providers.yaml: giá/token của model
        cost["cost_usd"] = round(cost["input_tokens"] * price.input_per_token
                                 + cost["output_tokens"] * price.output_per_token, 6)
        cost["estimated"] = True                        # đánh dấu số ước tính, không giấu
    spawn(db.append_cost(conv_id=conv_id, actor=actor, task_id=task_id, **cost))
    spawn(sse.emit(conv_id, "toolcall", {"task_id": task_id, "cost": cost["cost_usd"]}))
    # fire-and-forget: sổ cost lỗi KHÔNG fail lượt chính (spec §5 — như audit)
```

### Lưu ý

| Bẫy | Rule |
|---|---|
| Chỉ ghi cost khi lượt thành công | lượt lỗi/interrupt vẫn đốt token — ResultMessage vẫn có usage, ghi mọi kết cục |
| `await` ghi sổ trong đường chính | sổ chậm/lỗi kéo chết lượt — fire-and-forget, sổ là phụ |
| Tin `total_cost_usd` luôn có | proxy có thể trả 0/None — fallback tokens × bảng giá, đánh dấu `estimated` |
| Cost không gắn actor/task | cost meter per-agent trên Control Tower cần biết CON NÀO tiêu — ghi kèm actor + task_id |

---

## 7. Đa provider & model routing theo vai

### Nguyên lý

Spec §12: main = model mạnh, sub = model rẻ, fallback nhiều provider — **không hardcode**. SDK
nhận provider qua biến env (`ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`)
của **subprocess CLI**. Điểm mấu chốt: truyền qua `options.env` — **per-session**, mỗi client một
bộ — tuyệt đối không set `os.environ` (mutation toàn process: 2 session 2 provider chạy song song
sẽ giẫm key của nhau, bug chỉ lộ khi có tải).

Routing đọc từ `providers.yaml` — một nguồn sự thật cho model + base_url + key-env + giá:

```yaml
routing:
  main: {provider: primary,  model: claude-sonnet-x, max_turns: 50, max_budget_usd: 2.0}
  sub:  {provider: cheap,    model: claude-haiku-x,  max_turns: 30, max_budget_usd: 0.5}
providers:
  primary: {base_url: "https://proxy-a/...", api_key_env: PROVIDER_A_KEY,
            pricing: {input_per_token: 3.0e-6, output_per_token: 1.5e-5}}
  cheap:   {base_url: "https://proxy-b/...", api_key_env: PROVIDER_B_KEY,
            pricing: {input_per_token: 8.0e-7, output_per_token: 4.0e-6}}
```

### Pattern

```python
def routing_for(role_kind: str) -> Route:
    """role_kind ∈ {"main", "sub"} → model + env + trần chi phí. Nguồn: providers.yaml."""
    r = CONFIG["routing"][role_kind]
    p = CONFIG["providers"][r["provider"]]
    api_key = os.environ[p["api_key_env"]]        # key đọc từ env server, không nằm trong yaml
    env = {k: v for k, v in {
        "ANTHROPIC_BASE_URL":  p.get("base_url"),
        "ANTHROPIC_API_KEY":   api_key,
        "ANTHROPIC_AUTH_TOKEN": api_key,          # một số proxy đọc AUTH_TOKEN thay API_KEY
    }.items() if v}                               # env đòi dict[str, str] — lọc sạch None
    return Route(model=r["model"], provider_env=env,
                 max_turns=r["max_turns"], max_budget_usd=r["max_budget_usd"],
                 pricing=Pricing(**p["pricing"]))

# Dùng trong build_options (§2): model=route.model, env=route.provider_env.
# Đổi provider / hạ giá sub = sửa providers.yaml, KHÔNG sửa code.
```

Lưu ý resume khi đổi provider: transcript nằm trên disk local nên đổi `base_url` **không** phá
resume — nhưng đổi **model** giữa chừng một session main thì lượt sau chạy model mới trên context
cũ; chấp nhận được (fallback lúc provider chết) nhưng ghi vết `model_switched` vào audit.

### Lưu ý

| Bẫy | Rule |
|---|---|
| Set provider vào `os.environ` lúc runtime | race giữa các session đa provider — chỉ `options.env`, per-client |
| `env` chứa value None | `ClaudeAgentOptions.env` đòi `dict[str, str]` — lọc None trước khi truyền |
| Hardcode model trong code | routing đọc `providers.yaml` theo vai (main/sub) — spec §12 cấm hardcode |
| Chỉ set `ANTHROPIC_API_KEY` | một số proxy đọc `ANTHROPIC_AUTH_TOKEN` — set cả hai cùng giá trị |
| Key nằm thẳng trong providers.yaml commit vào repo | yaml chỉ giữ TÊN biến env (`api_key_env`), giá trị đọc từ env server |

---

## 8. Bảng tổng — BẪY CHẾT NGƯỜI (gom toàn bộ)

| # | Bẫy | Triệu chứng | Rule |
|---|---|---|---|
| 1 | Quên `disconnect()` | RAM tăng ~300MB/client bị bỏ rơi → OOM giữa demo | `disconnect()` trong `finally` mọi nhánh, tự bọc try/except (§1) |
| 2 | `disconnect()` khác task với `connect()` | **treo im lặng**, không stacktrace | close-on-done: 1 lượt = 1 coroutine trọn gói; lượt sau revive bằng resume (§1) |
| 3 | `cwd` không ổn định per conversation | resume **im lặng mở phiên mới** — main mất trí nhớ không báo lỗi | cwd cố định `data/conversations/<id>/` suốt đời ca (§2) |
| 4 | Schema shorthand `{param: type}` | tool có param optional bị SDK reject TRƯỚC handler, model kẹt retry | full JSON Schema, required/enum/default nằm TRONG schema (§4) |
| 5 | Enum không khớp kiểu phần tử | schema bất khả — MỌI tool_use bị reject trước handler | suy `type` từ phần tử `values`; check bool trước int (§4) |
| 6 | Mount server nhưng quên `allowed_tools` | tool bị harness chặn IM LẶNG, model gọi hoài không được | mount + allowed sinh từ cùng một vòng lặp trong `mount_role` (§4) |
| 7 | Chỉ bắt session_id lượt thành công | lượt sau resume id stale | ResultMessage có ở MỌI kết cục kể cả error — bắt hết (§3) |
| 8 | Đè id gốc khi id trả về lệch id chờ | mất dấu phiên thật, không điều tra được | verify khớp; lệch = `resume_mismatch`, GIỮ id gốc (§3) |
| 9 | `ProcessError` lúc resume → chết lượt / retry vô hạn | phòng chết hoặc loop | fallback fresh đúng 1 lần + audit `resume_failed` (§3) |
| 10 | Quên `setting_sources=[]` / để built-in tools | agent nuốt config máy host / cầm Bash ngoài audit | harness sạch + `tools=[]`, chỉ mở qua allowed_tools (§2) |
| 11 | Quên `permission_mode="dontAsk"` | agent headless treo chờ người approve | luôn set cho cả main lẫn sub (§2) |
| 12 | Set provider env vào `os.environ` | race key giữa session đa provider, chỉ lộ khi có tải | `options.env` per-session; lọc None (§7) |
| 13 | Tin `total_cost_usd` luôn có / chỉ ghi cost lượt thành công | cost meter câm hoặc thiếu | fallback tokens × bảng giá (đánh dấu `estimated`); ghi mọi kết cục, fire-and-forget (§6) |
| 14 | Handler tool sync / I/O sync trong handler | block event loop, N phòng đứng dây chuyền | handler async + I/O async (§4) |
| 15 | Cho SUB resume giữa các dispatch | state thừa, thêm đường hỏng | SUB tươi mỗi task, ngữ cảnh qua input; chỉ MAIN resume (§3) |

Bẫy CƠ CHẾ (2 lượt đâm nhau, event bị nuốt, sub chết im lặng, hủy ngoài băng, cờ giả sau
restart) → bảng Lưu ý của `multi-agent.md`. Bẫy CONTRACT mount/schema (param-nuốt, shorthand,
enum kiểu, phanh 4 nhánh) → `lab-joint.md`.
