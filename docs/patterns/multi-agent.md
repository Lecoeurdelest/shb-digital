# Pattern: Điều phối multi-agent MAIN–SUB (event-driven wake/sleep)

> Tài liệu "cách build" chi tiết cho **§3 (kiến trúc phòng), §4 (bốn cơ chế lõi), §5 (tool điều phối)**
> của `SPEC.md`. Tự chứa: đọc doc này + spec là build được phần cơ khí điều phối.
> Mọi snippet là pseudo-code viết theo domain của hệ (conversation / main / sub / role / task / phiếu) —
> đủ sát để chuyển thẳng thành code, đủ gọn để đọc hiểu cơ chế.

**Thuật ngữ**: `phòng` / `MAIN` / `SUB` / `phiếu` — định nghĩa ở spec §3 + §4.4. Riêng của doc này:

| Từ | Nghĩa |
|---|---|
| **event** | thứ đánh thức MAIN: `user_message` · `task_done` (mọi kết cục của sub) · `approval_decided`. |
| **bảng việc** | snapshot tasks của phòng: ai done / running / failed — vỏ đưa, não đọc. |

---

## 1. Vòng đời một event: wake → work → sleep

### Nguyên lý

**MAIN không phải process thường trực.** Không có vòng `while True`, không có worker loop đứng chờ.
MAIN là một **hàm xử-lý-sự-kiện**: nhận event → dựng context → chạy ĐÚNG MỘT lượt SDK → persist → **ngủ**
(disconnect, không giữ process nào sống). "Trí nhớ" của MAIN không nằm trong process — nằm ở SDK session
trên disk (resume qua `sdk_session_id`). Nhờ vậy:

- **Rẻ**: giữa hai event, phòng tốn 0 tài nguyên (không process treo, không poll).
- **Sống qua restart**: mỗi lần thức dậy đều load lại từ disk/DB — không có state chỉ-tồn-tại-trong-RAM
  mà mất là hỏng ca (trừ slot/queue, cố ý ephemeral — xem §8 spec).
- **Đợi = ngủ**: MAIN "chờ Credit" không phải là block một coroutine — là kết thúc lượt và ngủ;
  Credit xong thì event tự đánh thức. Không ai poll "xong chưa?".

Mọi kênh vào phòng đều quy về event: user gõ chat → `user_message`; sub kết thúc → `task_done`;
admin duyệt phiếu → `approval_decided`. **Một handler duy nhất** xử cả ba — chỉ khác prompt dựng ra.

### Pattern

Sequence đầy đủ 1 ca: user hỏi → main dispatch Credit → main ngủ → Credit xong → event → main thức
tổng hợp → trả user.

```
USER              API/FE          PHÒNG (slot + queue)       MAIN (SDK session)        SUB Credit
 │ "DN X vay 5 tỷ    │
 │  mở xưởng được k?"│
 │──────────────────▶│ POST /chat: lưu message
 │                   │──── event user_message ──▶ try_acquire ✓ (phòng rảnh)
 │                   │                              │ WAKE: connect(resume=sdk_session_id)
 │                   │                              │ prompt = tin nhắn user
 │                   │                              │──────────────────▶│
 │                   │                              │                   │ orch_dispatch("credit",…)
 │                   │                              │                   │───── spawn nền ─────────▶│ (chạy NỀN)
 │                   │                              │                   │◀─{role,"running"} NGAY   │
 │                   │                              │                   │ "Đã giao Credit thẩm     │
 │◀── SSE chat.delta ─────────────────────────────────────────────────── │  định, có kết quả em    │
 │  (stream chữ main)│                              │                   │  tổng hợp báo ngay ạ."  │
 │                   │                              │ persist + disconnect  ── MAIN NGỦ ──         │
 │                   │              release slot ◀──┘ (queue rỗng → phòng rảnh)                    │
 │                   │                                                            … sub chạy 40s … │
 │                   │◀───────────────── event task_done {task_id, done, result, bảng việc} ───────│
 │                   │──── task_done ───────────▶ try_acquire ✓
 │                   │                              │ WAKE: resume cùng session (nhớ nguyên ca)
 │                   │                              │ prompt = "sự kiện: SUB credit done, kết quả:
 │                   │                              │  DSCR=1.42 (nguồn calc)…, bảng việc: …"
 │                   │                              │──────────────────▶│ (NÃO quyết: đủ dữ liệu
 │                   │                              │                   │  → tổng hợp, không đợi thêm)
 │◀── SSE chat.delta ─────────────────────────────── │ present(tờ trình) + trả lời text
 │ "DSCR 1.42, đạt   │                              │ persist + disconnect ── MAIN NGỦ ──
 │  ngưỡng ≥1.2 …"   │              release slot ◀──┘
```

Handler — khung một lượt (đây là hàm trung tâm của cả vỏ):

```python
async def handle_room_event(conv_id: str, event: str, data: dict) -> None:
    if not await try_acquire(conv_id, event, data):      # §2: phòng bận → đã xếp hàng
        return
    try:
        conv = await db.get_conversation(conv_id)
        prompt = build_event_prompt(event, data)         # dựng context theo loại event
        client = ClaudeSDKClient(options=main_options(resume=conv.sdk_session_id))
        try:
            await client.connect()                       # WAKE
            main_registry[conv_id] = client              # cho interrupt per-agent (§7)
            await client.query(prompt)
            result = await stream_main_turn(client, conv_id)   # SSE chat.delta / toolcall
            await db.persist_turn(conv_id, result)       # message + sdk_session_id mới
            _main_retries.pop(conv_id, None)             # lượt ok → reset đếm retry (§9)
        finally:
            main_registry.pop(conv_id, None)
            await client.disconnect()                    # SLEEP — không giữ process
    except Exception as e:
        await handle_main_failure(conv_id, event, data, e)     # §9: retry ≤2, không nuốt
    finally:
        nxt = await release(conv_id)                     # §2: nhả slot + DRAIN
        if nxt:
            spawn(handle_room_event(conv_id, nxt[0], nxt[1]))
```

Dựng prompt theo event — vỏ chỉ ĐƯA THÔNG TIN, không ra lệnh điều phối (nguyên lý N1):

```python
def build_event_prompt(event: str, data: dict) -> str:
    if event == "user_message":
        return f"Tin nhắn user: {data['content']}"
    if event == "task_done":                             # mọi kết cục sub đi đường này (§5)
        # TÊN cho model, ID cho code: prompt chỉ nói role — task_id ở lại payload nội bộ/DB
        return (f"Sự kiện: SUB {data['role']} "
                f"kết cục [{data['outcome']}]. Kết quả: {data['result_summary']}\n"
                f"Bảng việc hiện tại: {data['board']}")
    if event == "approval_decided":                      # §8 — nói theo HÀNH ĐỘNG, không phiếu-id
        # (§4.4/§15 spec): khớp phiếu là việc của wrapper qua payload_hash — model không cần id
        verdict = "DUYỆT" if data["approved"] else "TỪ CHỐI"
        return (f"Sự kiện: hành động {data['action']} ({data['payload_summary']}) "
                f"đã được {verdict}. Lý do: {data['reason']}\n"
                f"Tham số đã duyệt: {data['payload']}\n"  # main (kể cả fresh-session) giao lại ĐÚNG tham số này
                f"Bảng việc hiện tại: {data['board']}")
```

### Lưu ý

| Bẫy | Vì sao chết | Rule |
|---|---|---|
| Prompt event kèm lệnh "đợi đủ N con rồi hãy tổng hợp" | vỏ cướp quyết định của não (vi phạm N1) | vỏ đưa kết quả + bảng việc; đợi hay tổng hợp là não quyết |

Bẫy vòng đời client SDK (disconnect trong `finally`, resume từ disk — DB không phải nguồn resume,
không giữ process sống): claude-sdk §1/§3 — chủ nhà.

---

## 2. Hàng đợi phòng + luật "1 lượt/phòng"

### Nguyên lý

Tại một thời điểm, **mỗi phòng chỉ có 1 lượt MAIN chạy**. Vì sao bắt buộc: 4 sub chạy song song có thể
báo `task_done` gần như cùng lúc, đúng lúc user cũng gõ chat — nếu mỗi event tự spawn 1 lượt thì 2-3
bản MAIN cùng ghi vào MỘT SDK session → transcript nát, trả lời chồng nhau. Giải pháp: **slot**
per-conversation. Ai lấy được slot thì chạy; ai không lấy được thì event vào **queue** của phòng, và
được **drain** (xử tuần tự) khi slot nhả.

Theo N4 spec (1 worker, in-process): slot + queue là **dict/set + `asyncio.Lock` trong process** —
không Redis, không distributed lock. Đánh đổi có chủ đích: state này ephemeral (restart là mất — xem
§7 boot-cleanup), và chỉ đúng khi chạy 1 worker. Đường mở đa worker (lock/queue ngoài process) vẽ sẵn
nhưng KHÔNG build trước khi cần.

**Tin user cũng XẾP HÀNG — vỏ không auto-interrupt** (§4.3 spec): main đang trong lượt mà user gõ
"khoan, đổi thành 4 tỷ" → tin vào queue như mọi event; FE hiện trạng thái đang bận + **nút hủy**.
Cắt lượt là một HÀNH ĐỘNG riêng, tường minh của user (nút hủy → `POST /interrupt`, §7) — không phải
side-effect của việc gửi tin. Và **hàng đợi không nuốt lệnh người** (§4.2 spec): dedup CHỈ áp cho
event máy có khoá tự nhiên (`task_done`, khoá theo `role`); `user_message` và `approval_decided`
KHÔNG BAO GIỜ bị dedup/gộp/drop — mỗi tin user, mỗi phiếu được quyết là MỘT entry riêng, tới tay
main đủ từng cái. Phiếu không nằm trong bảng việc — nuốt 1 phiếu là phòng kẹt vĩnh viễn, không có
lưới đỡ thứ hai.

### Pattern

```python
# room_slots.py — TOÀN BỘ state điều phối, in-process (1 worker — N4)
_busy_rooms: set[str] = set()                            # phòng đang chạy lượt main
_event_queues: dict[str, list[tuple[str, dict]]] = {}    # conv_id -> [(event, data)]
_lock = asyncio.Lock()
MAX_QUEUE = 50                                           # cap chống phình

async def try_acquire(conv_id: str, event: str, data: dict) -> bool:
    """True = caller chạy lượt. False = đã xếp hàng. KHÔNG interrupt hộ ai (§4.3 spec —
    hủy lượt là hành động riêng của user qua endpoint interrupt, §7)."""
    async with _lock:
        if conv_id not in _busy_rooms:
            _busy_rooms.add(conv_id)
            return True
        q = _event_queues.setdefault(conv_id, [])
        q.append((event, data))
        while len(q) > MAX_QUEUE:                        # đầy → CHỈ drop task_done cũ nhất:
            i = next((i for i, (e, _) in enumerate(q) if e == "task_done"), None)
            if i is None:                                #   task_done còn lưới đỡ (bảng việc ở event
                break                                    #   kế — result đã persist DB trước khi bắn, §6);
            q.pop(i)                                     #   user_message/approval_decided: KHÔNG BAO GIỜ drop
        return False
```

```python
async def release(conv_id: str) -> tuple[str, dict] | None:
    """Nhả slot HẲN rồi trả event kế — handler mới TỰ acquire lại từ đầu."""
    async with _lock:
        _busy_rooms.discard(conv_id)                     # nhả trước, không re-acquire
        q = _event_queues.pop(conv_id, [])
        if not q:
            return None
        # Dedup CHỈ áp cho task_done — khoá tự nhiên là ROLE (§4.2 spec), giữ bản MỚI nhất.
        # user_message / approval_decided KHÔNG BAO GIỜ dedup: mỗi tin, mỗi phiếu 1 entry riêng
        # (chung một khoá rỗng kiểu f"{evt}:" là nuốt tin user/phiếu → phòng kẹt vĩnh viễn).
        seen_roles, deduped = set(), []
        for evt, data in reversed(q):
            if evt == "task_done":
                if data["role"] in seen_roles:
                    continue
                seen_roles.add(data["role"])
            deduped.append((evt, data))
        deduped.reverse()
        if len(deduped) > 1:
            _event_queues[conv_id] = deduped[1:]         # phần còn lại chờ vòng drain kế
        return deduped[0]
```

Vòng drain tự khép: `handle_room_event` (§1) trong `finally` gọi `release`; có event kế thì spawn
handler mới; handler mới `try_acquire` sạch → chạy → lại `release`… tới khi queue rỗng.

### Lưu ý

| Bẫy | Vì sao chết | Rule |
|---|---|---|
| `release` re-acquire slot rồi mới trả event kế | handler được spawn thấy slot ĐANG GIỮ → tự xếp hàng lại → **ghost-slot, drain kẹt vĩnh viễn** | release nhả HẲN; handler mới tự `try_acquire` như mọi event thường |
| Không cap queue | event máy dồn (sub retry, SSE bắn lặp) → queue phình vô hạn | cap 50; đầy CHỈ drop `task_done` cũ nhất (còn lưới đỡ bảng việc); `user_message`/`approval_decided` không bao giờ drop |
| Dedup mọi loại event chung một khoá | `user_message`/`approval_decided` không có khoá tự nhiên → cùng loại chung khoá rỗng → tin user/phiếu bị NUỐT, phòng kẹt vĩnh viễn (§4.2 spec) | dedup CHỈ `task_done` theo `role`, giữ bản mới nhất, làm TRONG lock; event người giữ đủ từng cái |
| Auto-interrupt lượt khi `user_message` tới | tự đổi luật §4.3 spec; kéo theo hàm interrupt xóa queue → tin user vừa xếp tự xóa chính nó | tin user XẾP HÀNG; hủy là hành động riêng qua nút/endpoint interrupt (§7) |
| Debounce cửa chat "gom tin cho tiết kiệm" | thêm delay + thêm state race, spec CẤM (§14) | mỗi tin user = 1 event; queue đã xử đúng mọi ca gõ liên tiếp |

---

## 3. Dispatch fire-and-forget

### Nguyên lý

`orch_dispatch(role, title, input)` trả về **NGAY** `{role, status:"running", hint}` — nghĩa là trả
**trước khi kết quả tồn tại**. Đây không phải tối ưu, là **bắt buộc vật lý**:

1. MAIN là một LLM đang chạy TRONG vòng stream của chính nó. Nếu tool handler `await` sub chạy xong
   (hàng phút), cả stream của MAIN treo — không token nào về, timeout của lượt tự bắn.
2. Song song chỉ khả thi khi non-blocking: MAIN gọi `orch_dispatch` 4 lần liên tiếp trong 1 lượt →
   4 sub chạy song song tự nhiên. Nếu mỗi dispatch block thì thành tuần tự.
3. Sub có thể sống LÂU HƠN lượt main hiện tại — main kết lượt, ngủ; sub vẫn chạy nền; xong thì tự
   đánh thức main. Vòng đời tách rời hoàn toàn.

**Hệ quả cốt lõi:** tool-result đã bị "tiêu" để trả `running` → kết quả vật lý **không thể cưỡi trên
tool-result**. Con đường duy nhất còn lại là **event** (§5). Hai mảnh này là một cặp không tách được:
đã fire-and-forget thì PHẢI có report-back qua event.

SUB được spawn là **SDK client tươi** (disposable): `system_prompt` = SKILL của role, `allowed_tools` =
toolpack role + tool chung (`calc`, `present`) + KHÔNG gì khác — SDK hard-enforce ở tầng process, sub
Credit vật lý không thấy tool của Legal. Ngữ cảnh nghiệp vụ truyền qua `input` của task (sub không đọc
transcript của main). Chạy đồng thời có **cap PER-PHÒNG** (Semaphore theo conversation) để 1 lượt
main hăng máu dispatch 10 việc không đè chết máy — scope cap khớp đúng lý do cap (bài toán là
per-phòng; cap toàn hệ sẽ để ca này bóp cổ ca kia).

### Pattern

```python
_sub_semas: dict[str, asyncio.Semaphore] = {}            # cap đồng thời PER-PHÒNG (không phải toàn hệ)
def _sub_sema(conv_id: str) -> asyncio.Semaphore:
    return _sub_semas.setdefault(conv_id, asyncio.Semaphore(4))

sub_tasks: dict[str, asyncio.Task] = {}                  # task_id -> asyncio task chạy sub — đường hủy §7
                                                         # (đăng ký NGAY lúc spawn: hủy được cả sub còn chờ sema)

async def orch_dispatch(role: str, title: str, input: str) -> dict:
    """`input` = brief tự do cho sub (ngữ cảnh + yêu cầu) — string, không phải dict."""
    conv_id = ctx.conversation_id                        # ContextVar, set trước mỗi tool-call
    if role not in discovered_roles():                   # roles/ quét động — thêm phòng ban
        return err("bad_role", f"role phải thuộc {discovered_roles()}",
                   hint="đổi sang role hợp lệ rồi gọi lại", retryable=False)

    task, existing = await create_task_guarded(conv_id, role, title, input)   # §4 — bản DUY NHẤT
    if task is None:                                     # trùng: role này đang chạy → trả existing
        return {"created": False, "role": role, "status": "running", "title": existing.title,
                "hint": "Sub role này đang chạy — xem orch_status, KHÔNG giao lại."}

    await sse.emit(conv_id, "task.created", {"task": task})   # FE/DB dùng task.id — model thì không
    sub_tasks[task.id] = spawn(_run_sub(task), name=f"sub-{role}-{task.id}")  # FIRE-AND-FORGET

    # TÊN cho model, ID cho code: role là enum đóng — task_id không lên mặt tool (spec §4.1)
    return {"created": True, "role": role, "status": "running",   # trả NGAY, chưa có kết quả
            "hint": "Sub chạy nền, xong sẽ có sự kiện báo lại. "
                    "KHÔNG chờ — giao việc khác hoặc kết thúc lượt."}
```

Options dựng SUB client (SKILL làm system_prompt, toolpack role, model rẻ, trần lượt/budget):
claude-sdk §2 — chủ nhà, không chép lại ở đây. Điểm chốt namespace (spec §5): sub mount đúng
2 server `banking_<role>` + `common` (tool chung: `mcp__common__calc`, `mcp__common__present`),
**KHÔNG mount `orch`** — sub không được giao việc. `allowed_tools` khớp string tuyệt đối:
cho phép tool mà quên mount server chứa nó là tool biến mất im lặng với model.

Hint trong kết quả tool là một nửa cơ chế: SDK không có "ép model đừng đợi" — chính chuỗi
`"KHÔNG chờ — giao việc khác hoặc kết thúc lượt"` là affordance dạy main hành xử đúng ngay tại chỗ
(Trụ 6). Nửa còn lại là vật lý: có ngồi chờ cũng không có gì để chờ, kết quả không về đường này.

### Lưu ý

| Bẫy | Vì sao chết | Rule |
|---|---|---|
| Tool handler `await` sub xong mới return | lượt main treo hàng phút, mất song song, timeout stream | spawn nền + return `{role, running}` trong mili-giây |
| Trả `task_id` trên mặt tool cho main | model chép id = hallucinate; role đã là khoá duy nhất trong phòng | TÊN cho model, ID cho code — id chỉ ở DB/SSE/registry |
| Nhét kết quả sub vào tool-result "cho tiện" | kết quả CHƯA TỒN TẠI lúc tool return — về sau lẻn vào bằng side-channel là phá audit | kết quả CHỈ đi đường event `task_done` (§5) |
| Sub dùng chung session/client với main | tool lộ chéo role, transcript trộn, không kill riêng được | mỗi dispatch = client tươi, tool scoped, registry riêng theo `task_id` |
| Scope tool bằng lời dặn trong SKILL | model quên/bị dụ là gọi lậu tool role khác | scope bằng `allowed_tools` — SDK chặn cứng tầng process (N2) |
| Fan-out không cap | main giao 10 việc → 10 subprocess đồng thời đè máy demo | `asyncio.Semaphore` PER-PHÒNG quanh thân `_run_sub` (cap toàn hệ = ca này bóp cổ ca kia) |
| Ghi task vào DB SAU khi spawn | sub xong trước khi task tồn tại → report-back mồ côi | thứ tự bắt buộc: ghi DB → spawn → return |

---

## 4. Idempotent dispatch — không spawn đôi

### Nguyên lý

Luật + lý do (main retry/compaction → 2 con chạy đè): spec §4.1 + §15. Doc này thêm 2 điểm build:

1. **Khóa idempotency là `(conv_id, role)`** — không phải nội dung task: trong 1 phòng mỗi role tối
   đa 1 việc đang chạy (muốn giao việc mới cho Credit thì đợi/hủy việc cũ). Trùng KHÔNG phải lỗi —
   trả `created:false` + `title` việc đang chạy + hint chỉ đường (`orch_status`).
2. **Check + ghi DB + đăng ký registry trong CÙNG một lock**, và `orch_dispatch` (§3) gọi thẳng hàm
   guarded này — KHÔNG có bản check-rồi-create thứ hai nằm ngoài lock: hai đường drain sát nhau
   lách qua khe `await` giữa check và đăng ký là vẫn spawn đôi.

### Pattern

```python
_running_tasks: dict[tuple[str, str], str] = {}          # (conv_id, role) -> task_id (registry sống)
_dispatch_lock = asyncio.Lock()

async def create_task_guarded(conv_id, role, title, input):
    """Bản DUY NHẤT của check+create — orch_dispatch (§3) gọi thẳng hàm này.
    Trả (task, None) khi tạo mới · (None, existing_task) khi role đang chạy."""
    async with _dispatch_lock:
        tid = _running_tasks.get((conv_id, role))
        if tid:
            return None, await db.get_task(tid)          # đã có con đang chạy → trả existing
        # status="queued" (spec §10 có queued_at/started_at): giờ này task mới XẾP HÀNG;
        # _run_sub (§5) đánh running khi thật sự qua sema — orch_status không báo láo "running"
        task = await db.create_task(conv_id, role, title, input, status="queued")
        _running_tasks[(conv_id, role)] = task.id        # đăng ký NGAY trong lock, trước spawn
        return task, None

# gỡ đăng ký ở đúng MỘT chỗ: _report() (§5) — mọi kết cục đều đi qua đó
def unregister_task(task):
    _running_tasks.pop((task.conv_id, task.role), None)
```

Case đinh khi audit tool (spec §5): *gọi `orch_dispatch` 2 lần liên tiếp cùng role → lần 2 PHẢI trả
`created:false` (kèm `title` việc đang chạy), và registry chỉ có 1 task* — auditor verify bằng gọi
tool thật.

### Lưu ý

| Bẫy | Vì sao chết | Rule |
|---|---|---|
| Không check trùng | retry/compaction của main → 2 sub chạy đè, đôi tiền, 2 event | check `(conv_id, role)` running TRƯỚC spawn — luôn luôn |
| Trả error khi phát hiện trùng | main tưởng dispatch HỎNG → retry tiếp → vòng lặp gọi | trùng KHÔNG phải lỗi: trả `{created:false, role, status, title, hint}` như kết quả bình thường |
| Check bằng cờ `status` trong DB | cờ DB có thể là cờ giả (restart, ghi sót) | tin registry sống in-process; DB chỉ để render (§7 boot-cleanup) |
| Check và create tách 2 đoạn có `await` xen giữa | 2 event drain sát nhau lách qua khe → vẫn spawn đôi | check + đăng ký registry trong CÙNG một lock/đoạn atomic |
| Gỡ đăng ký rải rác nhiều nhánh | quên 1 nhánh (timeout…) → registry kẹt cờ, role đó cấm dispatch vĩnh viễn | gỡ ở đúng 1 chỗ: `_report()` — nơi mọi kết cục hội tụ (§5) |

---

## 5. INVARIANT sống còn: không có kết cục nào chết im lặng

### Nguyên lý

MAIN ngủ chờ event. Nếu một sub kết thúc — bằng BẤT KỲ cách nào — mà không có event báo về, MAIN sẽ
**ngủ vĩnh viễn**: bảng việc kẹt `running`, user nhìn phòng "đang xử lý" mãi mãi, không ai đánh thức.
Đây là mode hỏng tệ nhất của cả kiến trúc, và nó **im lặng** — không exception, không log đỏ, chỉ là
một event không bao giờ tới.

Vì vậy invariant (§4.2 spec): **MỌI kết cục của sub sinh ĐÚNG MỘT event `task_done` báo main.**

- **"MỌI"** — done, failed, timeout, user hủy. Nhánh dễ quên nhất là **timeout**: cám dỗ tự nhiên là
  "timeout thì thôi, notify UI cho người xem quyết" — nhưng hệ này chạy tự trị, KHÔNG có người ngồi
  canh SSE để cứu; timeout không event = phòng treo. **Timeout cũng là một kết cục, cũng phải báo.**
- **"ĐÚNG MỘT"** — không 0 (treo), không 2 (main thức 2 lần xử trùng — dedup §2 là lưới đỡ, không
  phải giấy phép bắn bừa).

Kỹ thuật hiện thực: dồn mọi đường thoát của hàm chạy sub qua **một điểm hội tụ duy nhất** `_report()`,
đặt trong `try/finally` ngoài cùng — Python bảo đảm `finally` chạy trên mọi nhánh (return, raise,
cancel). Không viết emit rải theo từng nhánh — thêm nhánh mới quên emit là thủng invariant.

### Pattern

Bảng kết cục → event (một event name duy nhất, `outcome` nằm trong payload):

| Kết cục của sub | `outcome` | `result` mang gì | Ai gây ra |
|---|---|---|---|
| Hoàn thành bình thường | `done` | verdict/kết quả của sub | sub tự chạy xong |
| Crash / tool nổ / lỗi SDK | `failed` | `{reason: "<lỗi, cắt gọn>"}` | exception trong lúc chạy |
| Idle 120s / hết trần tổng | `timeout` | `{reason: "idle 120s"}` | watchdog của vỏ |
| User hủy sub (§7) | `failed` | `{reason: "user hủy"}` | cancel asyncio task của sub (§7) |
| Server restart (đặc biệt) | `failed` | `{reason: "server restart"}` | boot-cleanup §7 — đánh thẳng DB, KHÔNG event (phòng nào cũng vừa chết theo process; main lượt sau thấy qua bảng việc) |

```python
async def _run_sub(task) -> None:
    """MỌI đường thoát của hàm này ĐỀU đi qua _report(). Không tồn tại exit thứ ba.
    Hủy (§7) = cancel CHÍNH asyncio task này — CancelledError nổ tại await đang chạy;
    finally vẫn chạy TRONG cùng task, shield để cancel không nuốt dọn dẹp lẫn event."""
    outcome, result = "failed", {"reason": "unknown"}
    client = None
    try:
        async with _sub_sema(task.conv_id):              # cap đồng thời per-phòng (§3)
            await db.mark_task_running(task.id)          # queued → running: giờ mới THẬT chạy (§4)
            await sse.emit(task.conv_id, "task.status", {"task": task})
            client = build_sub_client(task.role)
            out = await run_with_idle_watchdog(client, task, idle_s=120)
            outcome, result = "done", out
    except IdleTimeout:
        outcome, result = "timeout", {"reason": "idle 120s"}   # BÁO, không im
    except asyncio.CancelledError:                       # user hủy (§7) — là BaseException:
        outcome, result = "failed", {"reason": "user hủy"}     # `except Exception` KHÔNG bắt được
        raise                                            # re-raise sau khi gán — finally vẫn chạy
    except Exception as e:
        outcome, result = "failed", {"reason": str(e)[:500]}
    finally:                                             # chạy cả trên đường cancel:
        if client is not None:
            await asyncio.shield(client.disconnect())    # dọn subprocess — cancel không nuốt được
        await asyncio.shield(_report(task, outcome, result))
        # INVARIANT (§4.2 spec): shield để `await _report()` không bị cancel theo task —
        # thiếu shield là kết cục "user hủy" có 0 event → main ngủ vĩnh viễn
```

### Lưu ý

| Bẫy | Vì sao chết | Rule |
|---|---|---|
| Đường cancel không shield / bắt bằng `except Exception` | `CancelledError` là BaseException, lọt qua `except Exception`; `await _report()` trong finally của task đang-bị-cancel bị cancel theo → 0 event → phòng treo | bắt riêng `asyncio.CancelledError` (gán kết cục rồi re-raise); disconnect + `_report` trong finally đều bọc `asyncio.shield` |
| Emit rải theo từng nhánh except | thêm nhánh mới (vd cancel) quên emit → thủng invariant | 1 điểm hội tụ `_report()` trong `finally` ngoài cùng |
| `_report` tự nó có thể nổ mà không ai đỡ | persist/emit hỏng = tương đương không emit = treo | `_report` bọc try/except: hỏng thì ít nhất SSE `conversation.status: failed` — không nuốt im (§6) |
| Sub tự quyết "lỗi vặt, khỏi báo" | main không bao giờ biết việc đã chết | sub không có quyền im; vỏ báo hộ trên mọi nhánh |
| Emit 2 lần (nhánh except + finally cùng bắn) | main thức 2 lần xử trùng 1 task | chỉ `finally` ngoài cùng emit; các nhánh trong chỉ GÁN `outcome` |

---

## 6. Report-back payload — vỏ đưa gì cho não

### Nguyên lý

Event `task_done` mang cho MAIN đúng 4 thứ: **việc nào** (`role` — trên prompt; `task_id` chỉ nằm
trong payload nội bộ cho DB/log, không bao giờ vào prompt) — **kết cục gì** (`outcome`) —
**kết quả tóm tắt** (`result_summary`, bản đầy đủ nằm DB/card) — và **bảng việc**
(toàn cảnh: ai done / running / failed).

Bảng việc là mấu chốt của N1 (spec §2/§4.2 — vỏ không quyết "đợi đủ N con"): vỏ đánh thức main MỌI
lần có kết cục, kèm toàn cảnh; **não nhìn bảng tự quyết** — đợi tiếp / tổng hợp luôn / giao lại /
dừng sớm.

### Pattern

```python
async def _report(task, outcome: str, result: dict | None) -> None:
    unregister_task(task)                                # gỡ registry idempotency (§4) — luôn luôn
    sub_tasks.pop(task.id, None)                         # gỡ registry hủy (§3/§7) — luôn luôn
    try:
        await db.finish_task(task.id, status=outcome, result=result)   # persist TRƯỚC khi emit
        await sse.emit(task.conv_id, "task.status", {"task": task})    # FE cập nhật bảng việc

        board = await db.task_board(task.conv_id)
        payload = {
            "task_id": task.id,                          # NỘI BỘ (DB/log) — không vào prompt
            "role": task.role,                           # đây mới là định danh main nhìn thấy
            "outcome": outcome,                          # done | failed | timeout
            "result_summary": summarize(result, max_chars=3000),
            #   summarize khi cắt phải TỰ KHAI ngay trong text: "[đã tóm tắt — chi tiết trên
            #   card của <role>]" — không cắt im lặng: main phải biết mình chưa thấy hết
            "board": board,  # ví dụ: [{"role":"credit","status":"done"},
        }                    #         {"role":"legal","status":"running"}, ...]
        spawn(handle_room_event(task.conv_id, "task_done", payload))
        # spawn hầu như không raise tại chỗ — lỗi THẬT nằm BÊN TRONG handler, và §9 đã đỡ
        # (retry ≤2); retry quanh spawn chỉ là lưới đỡ cảnh, không đỡ được gì
    except Exception:
        # đường đỡ cuối: persist/emit hỏng cũng không được chết im — user + UI phải thấy
        await sse.emit(task.conv_id, "conversation.status",
                       {"status": "failed", "note": f"mất report-back task {task.id}"})
```

`orch_status()` là mặt cắt khác của cùng dữ liệu — main chủ động hỏi giữa lượt (vd khi user chen lời
"tình hình sao rồi?"): đọc **registry sống** đối chiếu DB, kèm `asOf` (Trụ 5 honest — không tin cờ
DB cũ đứng một mình). Shape return chốt 1 lần — mức TÊN (role), không `task_id`, có trần:

```python
{"tasks": [{"role": "credit", "status": "done", "title": "Thẩm định DN X", "ago": "40s"}],
 "count": 1, "asOf": "<ts>", "truncated": False}        # trần theo count server-side;
                                                        # cắt thì truncated=True — không cắt im
```

### Lưu ý

| Bẫy | Vì sao chết | Rule |
|---|---|---|
| Vỏ gom kết quả, "đủ N con" mới đánh thức | luật điều phối chết cứng trong vỏ, cướp quyền não (N1) | đánh thức MỌI kết cục; não nhìn bảng việc tự quyết đợi/tổng hợp/dừng sớm |
| Nhét nguyên result đồ sộ vào payload | prompt event phình, đốt context của main | summary có trần ký tự + cờ "[đã tóm tắt…]" tường minh khi cắt; chi tiết trình bày qua card `present` của chính sub |
| Emit event TRƯỚC khi persist result | main thức dậy, DB chưa có gì để đọc → race | thứ tự bắt buộc: persist → emit |
| Payload thiếu bảng việc | main mù toàn cảnh → hỏi dò hoặc quyết sai | mọi event `task_done` kèm board đầy đủ |
| `orch_status` đọc cờ DB trần | cờ giả sau sự cố → báo láo "đang chạy" | đọc registry sống, đối chiếu DB, kèm `asOf` |

---

## 7. Interrupt per-agent + boot-time cleanup

### Nguyên lý

User phải hủy được **TỪNG con**, không phải nút "dừng tất cả": hủy lượt MAIN đang chạy (nó tổng hợp
lan man) mà vẫn để Credit chạy tiếp; hoặc hủy riêng con Legal (giao nhầm) mà không đụng ai. Spec §4.3
chốt **MỘT cơ chế cho mỗi đích** — và **CẤM hủy ngoài băng**: `disconnect()` gọi từ task khác là treo
im lặng (connect/disconnect phải cùng asyncio task); mở đường báo cáo thứ hai là double-event.

- **Hủy lượt MAIN** = interrupt TRONG chính vòng đời lượt: handler API chỉ gọi `client.interrupt()`
  (cross-task AN TOÀN — khác `disconnect()`); stream của lượt kết thúc, mọi dọn dẹp (disconnect,
  nhả slot, drain) vẫn do `finally` của chính `handle_room_event` (§1) làm. **Queue GIỮ NGUYÊN** —
  tin user/phiếu đang xếp hàng không bị xóa (§4.2). Sub đang chạy KHÔNG bị đụng — chúng xong vẫn
  báo event, main lượt sau xử.
- **Hủy 1 SUB** = cancel ĐÚNG asyncio task đang chạy nó (`sub_tasks[task_id].cancel()`):
  `CancelledError` nổ tại await hiện hành của `_run_sub` (§5) → nhánh `except CancelledError` gán
  kết cục → `finally` (có `asyncio.shield`) vẫn disconnect + `_report()` → đúng MỘT event
  `task_done(failed, reason="user hủy")`. Hủy cũng là một kết cục — invariant §5 không có ngoại lệ.
  Task đăng ký từ lúc spawn (§3) nên cancel được cả sub còn XẾP HÀNG chờ Semaphore — không có
  "khe không hủy được".

**Boot-time cleanup**: registry sống là in-process — restart là trống trơn. Nhưng DB có thể còn task
`status="running"` từ đời trước (process chết giữa chừng). Đó là **cờ giả**: không còn client nào chạy
việc đó, và cũng sẽ không có event nào tới. Không dọn → UI treo spinner vĩnh viễn, main lượt sau đọc
bảng việc tưởng còn con đang chạy nên "đợi". Luật (§8 spec): lúc boot, task nào DB còn `running` mà
registry không có (mà lúc boot registry chắc chắn trống) → đánh `failed("server restart")` thẳng vào
DB. Nguồn sự thật cho "đang chạy" là registry sống, DB chỉ là kho render.

### Pattern

```python
main_registry: dict[str, ClaudeSDKClient] = {}   # conv_id -> main đang TRONG lượt (§1 đăng ký/gỡ)
# sub_tasks: task_id -> asyncio.Task — đăng ký lúc spawn (§3), gỡ trong _report (§6)

async def interrupt(conv_id: str, target: str | None = None) -> dict:
    """POST /conversations/{id}/interrupt — body.target: None = main, task_id = 1 sub.
    Handler này KHÔNG disconnect, KHÔNG report hộ — mọi dọn dẹp/báo cáo nằm trong
    chính vòng đời của lượt (§1) / của sub (§5). Hủy ngoài băng = CẤM (§4.3 spec)."""
    if target is None:                                   # ── hủy lượt MAIN ──
        client = main_registry.get(conv_id)
        if client is None:
            return {"ok": False, "hint": "không có lượt main đang chạy"}
        await client.interrupt()                         # CHỈ interrupt (cross-task an toàn);
        return {"ok": True,                              # disconnect/nhả slot/drain do finally
                "hint": "lượt main đã dừng; queue giữ nguyên, "     # của chính lượt (§1) lo
                        "sub đang chạy không bị ảnh hưởng"}

    t = sub_tasks.get(target)                            # ── hủy 1 SUB ──
    if t is None or t.done():                            # done() chặn race "vừa xong tự nhiên"
        return {"ok": False, "hint": "task không còn chạy (đã xong hoặc đã hủy)"}
    t.cancel()                                           # → CancelledError trong _run_sub (§5)
    return {"ok": True}                                  # → finally có shield → _report
                                                         #   → task_done(failed, "user hủy")

async def on_boot() -> None:
    """Registry sống trống sau restart → mọi cờ `queued`/`running` trong DB là cờ GIẢ."""
    orphans = await db.fetch_tasks(status_in=("queued", "running"))
    for t in orphans:
        await db.finish_task(t.id, status="failed", result={"reason": "server restart"})
        await sse.emit(t.conv_id, "task.status", {"task": t})   # FE đang mở không treo node
    # đánh thẳng DB + SSE, KHÔNG event phòng — main lượt sau tự thấy qua bảng việc (§5)
```

### Lưu ý

| Bẫy | Vì sao chết | Rule |
|---|---|---|
| Chỉ có nút "dừng tất cả" | user muốn sửa 1 nhánh phải giết cả ca, mất việc các sub đang tốt | registry 2 tầng (`main_registry` client / `sub_tasks` asyncio task), hủy đích danh |
| `disconnect()` từ handler API (cross-task) | connect/disconnect phải CÙNG asyncio task — gọi từ task khác treo im lặng, không stacktrace | handler hủy CHỈ `interrupt()` (main) / `task.cancel()` (sub); disconnect luôn nằm trong finally của chính vòng đời |
| Hủy sub bằng `client.interrupt()` | interrupt kết thúc stream ÊM → `_run_sub` rơi nhánh `done` với kết quả cụt — không ra `failed("user hủy")` như spec §4.3 đòi | hủy sub = cancel asyncio task; kết cục gán ở `except CancelledError` (§5) |
| Quên shield `_report`/disconnect trong finally | task đang bị cancel → `await` trong finally bị cancel theo → mất event → phòng treo (§4.2) | `asyncio.shield` quanh disconnect + `_report` — CancelledError không được nuốt event |
| Hủy main kèm xóa queue | tin user / phiếu đang xếp hàng bị NUỐT — vi phạm §4.2 "hàng đợi không nuốt lệnh người" | hủy main chỉ cắt lượt hiện tại; queue giữ nguyên, finally của lượt drain tiếp |
| Boot không dọn cờ `queued`/`running` | UI spinner vĩnh viễn, main "đợi" task không tồn tại | boot quét DB, đánh failed("server restart") mọi task mồ côi + SSE `task.status` |

---

## 8. Approval resume — pause-point sống nhờ event + DB phiếu

### Nguyên lý

Phanh (§4.4 spec) tạo ra một pause có thể kéo dài **hàng giờ** — admin chưa rảnh duyệt. Nếu pause-point
sống nhờ "main đang đứng chờ" thì nó chết theo process đầu tiên restart. Thiết kế đúng: pause-point
sống nhờ **hai thứ bền**: (1) **phiếu trong DB** (`approvals`: action + payload_hash + status) — trạng
thái "đang chờ duyệt cái gì" tồn tại độc lập với mọi process; (2) **đường event** — quyết định duyệt
là một event như mọi event, đánh thức main qua đúng cơ chế §1-§2.

Chuỗi wrapper đầy đủ (biên nhận → claim atomic approved→used → pending idempotent → tạo phiếu mới):
spec §4.4 — chủ nhà, không chép lại. Doc này chỉ lo **đường event**: phiếu tạo xong thì main NGỦ —
không ai đứng chờ; admin quyết → event `approval_decided` đánh thức main → **main tự giao lại việc**
(`orch_dispatch` Ops lần nữa) → wrapper tự khớp phiếu APPROVED qua `payload_hash` → chạy thật.

Chú ý phân vai: vỏ KHÔNG "resume tự động cú gọi tool cũ" — vỏ chỉ báo tin. Việc giao lại Ops, hay xử
lý khi phiếu bị TỪ CHỐI (báo user, đề xuất phương án khác), là quyết định của não. Restart giữa chừng
không mất gì: phiếu nằm DB, session main nằm disk — admin duyệt sau restart thì event vẫn đánh thức
đúng phòng, main resume đúng ngữ cảnh.

### Pattern

```python
@app.post("/api/approvals/{aid}/decide")
async def decide(aid: str, body: Decision, admin=Depends(require_admin)):
    # atomic: chỉ chuyển được pending -> decided ĐÚNG MỘT lần (chống double-decide/re-fire)
    phieu = await db.decide_approval(aid, approved=body.approved,
                                     decided_by=admin.id, reason=body.reason)
    if phieu is None:
        raise HTTPException(409, "Phiếu đã được quyết trước đó")   # REST dùng HTTP status —
                                                                   # envelope 4-field là của TOOL (§5 spec)
    await sse.emit(phieu.conv_id, "approval.decided", {"phieu": phieu})
    spawn(handle_room_event(phieu.conv_id, "approval_decided", {   # đường event chuẩn §1
        "phieu_id": phieu.id,                            # NỘI BỘ (DB/log) — KHÔNG vào prompt (§15 spec)
        "action": phieu.action,                          # vd "disburse" — định danh trên mặt model
        "payload": phieu.payload,                        # main giao lại ĐÚNG tham số đã duyệt
        "payload_summary": summarize_payload(phieu.payload),   # vd "5 tỷ, loan L-042" — lên prompt
        "approved": phieu.status == "approved",
        "reason": phieu.reason,
        "board": await db.task_board(phieu.conv_id),     # main (kể cả fresh sau restart) đủ toàn cảnh
    }))
    return {"ok": True}
```

Main thức dậy với prompt (từ `build_event_prompt` §1): *"Hành động disburse (5 tỷ, loan L-042) đã
được DUYỆT. Tham số đã duyệt: …"* → não giao lại Ops kèm đúng payload → wrapper gated tự khớp phiếu
qua `payload_hash` → thực thi. Mặt model KHÔNG có phiếu-id (§4.4/§15 spec) — khớp phiếu là việc
của wrapper.

### Lưu ý

| Bẫy | Vì sao chết | Rule |
|---|---|---|
| Pause = main/sub đứng `await` chờ duyệt | admin duyệt sau 3 tiếng / sau restart → không còn ai đứng đó | pause-point = phiếu DB + event; main NGỦ, không đứng chờ |
| Vỏ tự replay cú gọi tool cũ khi duyệt xong | vỏ quyết thay não; ngữ cảnh có thể đã đổi (user chen lời hủy kèo) | vỏ chỉ báo tin qua event; não tự quyết giao lại hay không |
| Phiếu khóa theo action, không khóa payload/phòng | duyệt 1 tỷ gọi 5 tỷ vẫn lọt; phiếu ca A mở khóa ca B | phiếu khớp `(conversation, action, payload_hash)` — lookup luôn lọc conv (§4.4 spec); lệch = phiếu mới |
| Phiếu dùng lại / retry-thành-xin-duyệt-lại | 1 lần duyệt → gọi disburse N lần; phiếu used + sub gọi lại → phiếu mới → admin duyệt lần 2 → thực thi ĐÔI | claim atomic `UPDATE…WHERE status='approved'` → used; retry SAU thành công trả BIÊN NHẬN cũ theo key (§4.4 spec) |
| Decide không atomic | admin double-click / event re-fire → 2 event resume | UPDATE có điều kiện `status='pending'`; đã decided → 409, không emit |
| Chỉ xử nhánh DUYỆT | phiếu từ chối → main không được báo → user chờ vô vọng | cả approve lẫn reject đều emit `approval_decided`; não lo phần cư xử |

---

## 9. Retry / failure của chính MAIN

### Nguyên lý

Sub chết đã có invariant §5 đỡ. Nhưng **chính lượt main** cũng chết được: provider chập chờn, SDK
`ProcessError`, stream đứt giữa chừng. Không đỡ → user gửi tin mà phòng im re, event `task_done` bị
"tiêu" mất không ai xử. Nguyên tắc giống hệt invariant của sub, áp lên main: **lượt main lỗi cũng
không được chết im lặng.**

Đối xử: **retry có trần (≤2)** cho lỗi chớp nhoáng — retry lại CHÍNH event đó (idempotent về phía hệ:
lượt trước chưa persist gì thành công). Hết trần thì hai việc bắt buộc: (1) **ghi message lỗi vào DB**
để user thấy trong lịch sử chat — không phải chỉ toast SSE (F5 là mất); (2) SSE `conversation.status:
failed` cho UI đổi trạng thái. Tuyệt đối không retry vô hạn (đốt tiền + phòng kẹt trong vòng lặp) và
không nuốt lỗi (user tưởng agent đang suy nghĩ, thực ra đã chết 5 phút trước).

Đếm retry theo phòng, **reset khi có lượt thành công** (đã cài ở §1). Retry bằng cách đẩy lại event
vào queue rồi để vòng drain (§2) nhặt — không spawn thẳng, tránh giẫm lên slot đang trong pha nhả.

### Pattern

```python
_main_retries: dict[str, int] = {}                       # conv_id -> số lần lỗi liên tiếp
MAIN_MAX_RETRIES = 2

async def handle_main_failure(conv_id: str, event: str, data: dict, err: Exception):
    n = _main_retries.get(conv_id, 0) + 1
    if n <= MAIN_MAX_RETRIES:
        _main_retries[conv_id] = n
        log.warning("lượt main lỗi (%s) — retry %d/%d: %s", event, n, MAIN_MAX_RETRIES, err)
        await requeue(conv_id, event, data)              # vào queue; finally của lượt này
        return                                           # sẽ release → drain → chạy lại

    _main_retries.pop(conv_id, None)                     # hết trần — KHÔNG nuốt im
    await db.add_message(conv_id, sender="system",       # user thấy trong LỊCH SỬ chat
        content=(f"Hệ thống gặp lỗi khi xử lý ({event}) sau {MAIN_MAX_RETRIES} lần thử lại: "
                 f"{str(err)[:300]}. Anh/chị gửi lại tin nhắn để tiếp tục ca làm việc."))
    await sse.emit(conv_id, "conversation.status", {"status": "failed"})
    # ca KHÔNG hỏng: session main còn nguyên trên disk — user chat tiếp là resume bình thường,
    # chỉ event bị rơi phải làm lại (đúng tinh thần "server sập = tạm ngưng, không phải quên")
```

Trường hợp con: `connect(resume=...)` ném lỗi vì session trên disk stale/hỏng — không tính vào trần
retry lượt; xử tại chỗ **một lần**: clear `sdk_session_id`, dựng client fresh, chạy tiếp (mất trí nhớ
ca cũ nhưng phòng sống — vẫn tốt hơn chết hẳn). Chỉ khi fresh cũng lỗi mới rơi vào đường
`handle_main_failure` ở trên.

### Lưu ý

| Bẫy | Vì sao chết | Rule |
|---|---|---|
| Retry vô hạn | đốt token, phòng kẹt vòng lặp, che lỗi thật | trần cứng ≤2; đếm per-phòng, reset khi lượt thành công |
| Hết trần chỉ log server | user nhìn phòng im lặng, tưởng agent còn nghĩ | ghi message lỗi vào DB (lịch sử chat) + SSE `failed` |
| Chỉ báo lỗi qua SSE toast | F5/reconnect là mất dấu vết lỗi | message lỗi PERSIST trong DB, load lại vẫn thấy |
| Retry bằng spawn thẳng handler mới | giẫm pha release slot của lượt đang chết → race | requeue vào queue phòng, để drain chuẩn §2 nhặt |
| Lỗi stale-session tính chung trần retry | 1 lần stale + 1 lỗi thoáng = tuyên bố phòng chết oan | stale-session xử riêng tại chỗ: fallback fresh đúng 1 lần |
| Coi lượt lỗi = ca hỏng, khóa phòng | mất cả ca vì 1 event xui | ca vẫn sống: session trên disk còn, user chat tiếp là resume |

---

## Phụ lục: checklist invariant toàn hệ (soát trước khi ship)

1. **1 lượt/phòng**: không tồn tại đường nào chạy lượt main mà không qua `try_acquire`.
2. **release nhả hẳn**: không chỗ nào re-acquire slot hộ handler kế (ghost-slot).
3. **Dispatch trả ngay + idempotent**: 2 cú gọi liên tiếp cùng role → 1 task, lần 2 `created:false`.
4. **Mọi kết cục sub → đúng 1 event**: done / failed / timeout / user hủy đều hội tụ về `_report()`.
5. **Vỏ không quyết điều phối**: prompt event chỉ chứa dữ kiện + bảng việc, không chứa mệnh lệnh đợi/gom.
6. **Registry sống là nguồn sự thật "đang chạy"**: boot đánh failed mọi task `running` mồ côi trong DB.
7. **Hủy là kết cục, qua chính vòng đời**: hủy sub = cancel asyncio task của nó → `_report` trong
   finally có shield → vẫn đúng 1 event; hủy main = `interrupt()` trong chính vòng đời lượt —
   queue GIỮ NGUYÊN, không nuốt tin user/phiếu.
8. **Phiếu bền hơn process**: duyệt sau restart vẫn resume được ca (phiếu DB + session disk + event).
9. **Main lỗi có trần và có tiếng**: ≤2 retry; hết trần → message lỗi user thấy được + SSE failed.
10. **Mọi client SDK có `disconnect` trong `finally` của CHÍNH task tạo nó** (đường cancel: bọc
    `asyncio.shield`): không nhánh thoát nào leak subprocess, không disconnect cross-task.
11. **Hàng đợi không nuốt lệnh người**: dedup/drop chỉ đụng `task_done`; `user_message` và
    `approval_decided` tới tay main đủ từng cái.
