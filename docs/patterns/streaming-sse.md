# Pattern: SSE realtime FE ↔ BE

> Bản "cách build" cho `SPEC.md` §9 (bảng event) + §8 (DB = kho render).
> Tự chứa: đọc doc này + spec là dựng được cả publisher/endpoint phía BE lẫn hook phía FE.
> Phạm vi: chỉ SSE (spec §14 cấm WebSocket), 1 uvicorn worker, in-process, KHÔNG Redis (spec §12).

---

## 0. Tiên đề: DB là nguồn sự thật, SSE chỉ là thông báo

Mọi quyết định trong doc này suy từ một câu:

> **FE render đúng mà KHÔNG cần nhận đủ event.** Nguồn sự thật để vẽ UI là DB
> (`GET /conversations/{id}` trả full state: messages + tasks + cards + approvals).
> SSE chỉ là kênh "có cái mới, cập nhật đi cho mượt" — lỡ event thì refetch là lành.

Hệ quả trực tiếp:

- **Không cần outbox, không cần replay-cursor, không cần Last-Event-ID** (spec §14 cấm build).
  Reconnect = refetch full state + nghe tiếp. Sự kiện lỡ trong lúc đứt mạng đã nằm trong DB state.
- **Event chỉ được bắn SAU khi ghi DB** (§5 doc này). Bắn trước mà ghi fail → FE thấy thứ
  DB không có → refetch lại "mất" dữ liệu → UI nhảy lùi. Bắn sau thì tệ nhất là FE biết muộn.
- Mất 1 event không phải bug chí mạng; **2 nguồn sự thật lệch nhau mới là bug chí mạng**.

---

## 1. Kiến trúc 1 worker: bus fanout in-process

### Nguyên lý

1 worker uvicorn = 1 process = 1 asyncio event loop. Publisher và mọi SSE connection sống chung
process → fanout chỉ cần **1 dict `{conversation_id: set[asyncio.Queue]}`**. Mỗi client mở SSE
= 1 `Queue` subscriber; publish = put vào từng queue của phòng đó.

Vì sao đủ (spec N4 — đơn giản trước):

- **Không cần Redis pub/sub**: Redis giải bài fanout *xuyên process/worker*. 1 worker thì
  không có process thứ hai để xuyên — thêm Redis là thêm moving part + thêm đường chết
  (Redis rớt, retry, TTL) mà không mua được gì.
- **Không cần atomic sequence phân tán**: seq counter (§3) là dict thường — asyncio
  single-thread, không có race giữa worker.
- **Không cần replay**: đã có tiên đề §0. Queue chỉ giữ event *đang sống* của connection
  *đang mở*; connection chết thì queue bị vứt, không ai cần đọc lại.
- **Đường mở đã vẽ sẵn, không build trước**: nếu sau này lên đa worker, chỉ thay ruột
  `publish()`/`subscribe()` bằng broker ngoài — chữ ký hàm và toàn bộ phần còn lại giữ nguyên.

### Pattern

```python
# app/sse/bus.py — fanout in-process, toàn bộ "hạ tầng realtime" của hệ
import asyncio
from collections import defaultdict

_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
_MAX_QUEUE = 500          # queue đầy = client không đọc (tab treo/mạng nghẽn)
MAX_CONN_PER_CONV = 10    # cap connection mỗi ca (§4)

def subscribe(conversation_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE)
    _subscribers[conversation_id].add(q)
    return q

def unsubscribe(conversation_id: str, q: asyncio.Queue) -> None:
    subs = _subscribers.get(conversation_id)
    if subs is not None:
        subs.discard(q)
        if not subs:                      # phòng hết người nghe → dọn key
            _subscribers.pop(conversation_id, None)

def conn_count(conversation_id: str) -> int:
    return len(_subscribers.get(conversation_id, ()))

def publish(conversation_id: str, event: dict) -> None:
    for q in list(_subscribers.get(conversation_id, ())):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            # CHỈ client này lỡ event — nó sẽ tự lành khi reconnect + refetch (§0).
            # Tuyệt đối không await ở đây: publisher không được chờ client chậm.
            pass
```

`publish` là hàm sync, gọi được từ bất kỳ chỗ nào trong luồng orchestrator mà không block.

### Lưu ý

| Bẫy | Rule |
|---|---|
| `await q.put(...)` trong publish → 1 client treo kéo chết cả luồng orchestrator | publish dùng `put_nowait`, đầy thì bỏ (client tự lành nhờ refetch) |
| Quên `unsubscribe` khi client rời → dict phình queue chết, publish tốn công vô ích | `unsubscribe` nằm trong `finally` của generator SSE (§4) — mọi đường thoát đều qua đó |
| Dùng bus SSE làm cơ chế đánh thức MAIN | SSE bus chỉ nói với FE. Đường đánh thức MAIN (spec §4.2) là hàng đợi phòng riêng — 2 đường độc lập, event FE lỡ không được phép ảnh hưởng orchestration |
| Giữ event trong bus để "replay cho người vào sau" | Không. Người vào sau/reconnect load DB state (§0). Bus không có trí nhớ |
| Lên nhiều worker mà giữ nguyên bus in-process → mỗi worker chỉ thấy event của mình | 1 worker là quyết định KIẾN TRÚC (spec §12). Muốn scale → thay ruột publish/subscribe bằng broker, không chắp vá |

---

## 2. Contract event

### Nguyên lý

Một envelope duy nhất cho mọi event — FE chỉ cần 1 chỗ parse, 1 switch theo `type`:

```jsonc
{
  "type": "chat.delta",           // tên event (bảng dưới)
  "conversation_id": "c_01",      // phòng nào
  "seq": 12,                       // CHỈ có nghĩa với chat.delta (§3); event khác = null
  "ts": "2026-07-17T09:30:00Z",   // ISO-8601 UTC, thời điểm bắn
  "data": { ... }                  // payload theo type
}
```

Truyền frame SSE ở dạng tối giản — **chỉ dòng `data:`**, type nằm trong JSON:

```
data: {"type":"task.created","conversation_id":"c_01","seq":null,"ts":"...","data":{...}}\n\n
```

Không dùng field `event:` của SSE (FE phải addEventListener từng loại — switch trong
`onmessage` gọn hơn) và **không dùng field `id:`** (browser sẽ tự gửi header `Last-Event-ID`
khi reconnect — hệ này không replay, đặt `id:` là gài bẫy dev sau tưởng có).

### Bảng event (tên event chuẩn theo spec §9 — shape chi tiết chuẩn Ở ĐÂY, spec ghi dạng gọn)

| `type` | `data` | UI ăn |
|---|---|---|
| `conversation.status` | `{status: "running" \| "waiting_approval" \| "done" \| "failed"}` | badge trạng thái ở sidebar + header chat |
| `task.created` | `{task}` — full row `tasks` (id, role, title, status, queued_at…) | bảng việc thêm dòng, live map thêm node sub |
| `task.status` | `{task}` — row đã update (status, result, ended_at, cost) | đổi màu node, cập nhật bảng việc, trace |
| `chat.delta` | `{turn_id, chunk, done, full_text?}` — mở rộng có chủ đích so với spec `{chunk}`, phục vụ cơ chế tự lành §3 | stream chữ của MAIN trong khung chat |
| `card` | `{card}` — full row `cards` (id, type, data, task_id, ts) | canvas render theo `card.type` (7 loại, spec §6) |
| `toolcall` | `{task_id, tool, summary, cost}` | trace timeline + cost meter (+ 3D view sau) |
| `approval.pending` | `{phieu}` — full row `approvals`, có `status` theo vòng đời phiếu `pending → approved \| rejected → used` (spec §4.4/§10) | badge chờ duyệt, approval queue admin |
| `approval.decided` | `{phieu}` — row sau decide (status, decided_by, reason). Bước `approved → used` (kèm `used_at`, `receipt`) KHÔNG có event riêng — FE thấy qua refetch | gỡ badge, cập nhật queue, FE biết ca sắp resume |

Khóa payload approval chốt MỘT tên **`phieu`** (ascii-hoá của `{phiếu}` spec §9): BE bắn
`{"phieu": row}`, FE đọc `data.phieu` — mọi chỗ, không nơi nào dùng `approval`/`{phiếu}` khác đi.
`{task}` / `{card}` / `{phieu}` bắn **nguyên row DB** (serialize) chứ không bắn diff —
FE upsert theo `id`, cùng shape với dữ liệu `GET /conversations/{id}` trả về → một codepath
render duy nhất cho cả refetch lẫn realtime.

### Lưu ý

| Bẫy | Rule |
|---|---|
| Bắn diff (`{task_id, status}`) → FE phải vá state, lệch dần với DB | Bắn nguyên row. Upsert theo id — idempotent, nhận trùng vô hại |
| Shape event khác shape REST → FE viết 2 bộ type/2 mapper | 1 serializer dùng chung cho REST + SSE |
| Thêm event mới cho mỗi nhu cầu UI (`clarify`, `thinking`…) | Hỏi-lại là 1 câu chat thường (spec §4.3) — đi qua `chat.delta`. Chỉ thêm type khi có bảng DB tương ứng |
| FE tin `ts` để sort | `ts` chỉ để hiển thị. Thứ tự render lấy từ DB state (created_at/id); trong 1 lượt stream thì theo `seq` |

---

## 3. Ordering + dedup cho streaming text

### Nguyên lý

`chat.delta` là event duy nhất **không có bản ghi DB per-chunk** — message chỉ ghi DB khi
lượt kết thúc. Vì vậy nó cần cơ chế riêng để FE ghép đúng:

- **`seq` tăng dần theo LƯỢT** (`turn_id` = 1 lượt trả lời của MAIN): chunk đầu `seq=1`,
  chunk sau +1. Scope là lượt, KHÔNG phải toàn cuộc hội thoại — hết lượt là reset.
- FE giữ `lastSeq` per-turn: `seq <= lastSeq` → trùng, bỏ; `seq == lastSeq+1` → append +
  flush buffer; `seq > lastSeq+1` → cho vào buffer chờ mảnh khuyết.
- **Cờ `done` kết lượt**, mang `seq` cao nhất (last+1) và **kèm `full_text`** — toàn văn
  message VỪA GHI DB. FE nhận `done` → thay toàn bộ text đã ghép bằng `full_text`.
  Đây là van tự lành: đứt mạng giữa lượt, lỡ chunk, buffer kẹt — `done` đến là text đúng
  100%; `done` cũng lỡ nốt thì refetch-on-reconnect vẫn cứu (message đã nằm trong DB).

1 worker + queue FIFO thì chunk gần như không bao giờ lệch thứ tự — nhưng dedup + buffer
vẫn bắt buộc: reconnect nhanh có thể tạo 2 connection chồng nhau vài giây (connection cũ
chưa kịp chết), event đến trùng.

### Pattern — BE

```python
# app/sse/emit.py — cổng bắn duy nhất + seq per-turn
from datetime import datetime, timezone
from .bus import publish
from .redact import redact_deep   # §4

_turn_seq: dict[str, int] = {}    # 1 worker → dict thường là atomic đủ

def _next_seq(turn_id: str) -> int:
    _turn_seq[turn_id] = _turn_seq.get(turn_id, 0) + 1
    return _turn_seq[turn_id]

def emit(conversation_id: str, type_: str, data: dict, seq: int | None = None) -> None:
    publish(conversation_id, {
        "type": type_, "conversation_id": conversation_id, "seq": seq,
        "ts": datetime.now(timezone.utc).isoformat(), "data": redact_deep(data),
    })

def emit_chat_delta(conversation_id: str, turn_id: str, chunk: str) -> None:
    emit(conversation_id, "chat.delta",
         {"turn_id": turn_id, "chunk": chunk, "done": False},
         seq=_next_seq(turn_id))

def emit_chat_done(conversation_id: str, turn_id: str, full_text: str) -> None:
    # Gọi SAU khi INSERT messages đã commit (§5). pop → done luôn có seq cao nhất.
    seq = _turn_seq.pop(turn_id, 0) + 1
    emit(conversation_id, "chat.delta",
         {"turn_id": turn_id, "chunk": "", "done": True, "full_text": full_text}, seq=seq)
```

### Pattern — FE hook (React, rút gọn)

```tsx
// useConversationSSE.ts — transport + ghép chunk. Handlers do component cấp.
export function useConversationSSE(convId: string, h: Handlers) {
  const turns = useRef(new Map<string, { last: number; done?: number; buf: Map<number, Delta> }>());
  const retry = useRef(0);
  useEffect(() => {
    if (!convId) return;
    let es: EventSource | null = null, timer = 0, dead = false;
    const connect = () => {
      es = new EventSource(`/api/conversations/${convId}/sse`, { withCredentials: true });
      es.onopen = async () => {
        retry.current = 0;
        turns.current.clear();               // lượt dở dang → chờ done.full_text tự lành
        const state = await fetch(`/api/conversations/${convId}`).then(r => r.json());
        h.applyFullState(state);             // refetch-on-(re)connect: DB là nguồn sự thật
      };
      es.onmessage = (m) => {
        const e = JSON.parse(m.data);
        if (e.type !== "chat.delta") { h.dispatch(e); return; }   // upsert theo id — idempotent
        const d = e.data, t = turns.current.get(d.turn_id) ?? { last: 0, buf: new Map() };
        turns.current.set(d.turn_id, t);
        if (e.seq == null || e.seq <= t.last) return;             // trùng/stale → bỏ
        t.buf.set(e.seq, d);
        if (d.done) t.done = e.seq;
        while (t.buf.has(t.last + 1)) {                           // flush đúng thứ tự
          const nx = t.buf.get(++t.last)!; t.buf.delete(t.last);
          if (nx.chunk) h.appendText(d.turn_id, nx.chunk);
        }
        if (t.done && t.last >= t.done) {                         // kết lượt: thay bằng bản DB
          h.turnDone(d.turn_id, t.buf.get(t.done)?.full_text ?? d.full_text);
          turns.current.delete(d.turn_id);
        }
      };
      es.onerror = () => {                                        // auto-reconnect backoff + jitter
        es?.close();
        if (dead) return;
        const delay = Math.min(1000 * 2 ** retry.current++, 30000);
        timer = window.setTimeout(connect, delay + Math.random() * 300);
      };
    };
    connect();
    return () => { dead = true; es?.close(); clearTimeout(timer); };
  }, [convId]);
}
```

### Lưu ý

| Bẫy | Rule |
|---|---|
| Dùng 1 seq toàn cuộc hội thoại "cho tiện" rồi coi nó là replay-cursor | seq scope theo LƯỢT, chỉ để ghép chữ. Cursor replay là thứ hệ này cố tình KHÔNG có (§0, spec §14) |
| Render text lượt chỉ từ chunk ghép | `done.full_text` (bản đã ghi DB) luôn thay thế bản ghép — chunk chỉ là preview mượt mắt |
| Reconnect giữa lượt: lấy seq đầu tiên nhận được làm mốc → hiện text cụt đầu | `onopen` clear turns; chunk mid-turn nằm buffer không flush; chờ `done.full_text` hoặc refetch |
| Quên dọn `_turn_seq` phía BE khi lượt lỗi/interrupt | MỌI đường kết lượt (xong / lỗi / **interrupt**) đều bắn `done` (full_text = phần đã có) + `pop` counter — turn không được treo `lastSeq` lơ lửng phía FE |
| FE new EventSource mỗi render | Chỉ tạo trong `useEffect` theo `convId`; cleanup đóng chắc tay (cờ `dead` chặn timer mồ côi) |

---

## 4. SSE endpoint + chi tiết sống còn phía server

### Nguyên lý

Endpoint chỉ làm đúng 4 việc: check cap → subscribe → vòng lặp `queue.get` (timeout kiêm
heartbeat) → `finally: unsubscribe`. Mọi độ bền còn lại nằm ở header và thói quen dọn dẹp —
đây là những chi tiết **thiếu là chết im lặng**, không nổ exception nào cho mà debug.

### Pattern

```python
# app/api/sse.py
import asyncio, json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.sse import bus

router = APIRouter()
_HEARTBEAT = 15.0  # giây

_SSE_HEADERS = {
    "Cache-Control": "no-cache",        # chặn cache proxy/browser
    "X-Accel-Buffering": "no",          # tắt buffering nginx — THIẾU LÀ SSE CHẾT IM
    "Connection": "keep-alive",
    "Content-Encoding": "identity",     # chặn middleware gzip gom frame
}

@router.get("/api/conversations/{conv_id}/sse")
async def sse(request: Request, conv_id: str):        # + auth dependency như REST khác
    if bus.conn_count(conv_id) >= bus.MAX_CONN_PER_CONV:
        raise HTTPException(429, "Quá số kết nối SSE cho ca này — đóng bớt tab")
    q = bus.subscribe(conv_id)

    async def gen():
        try:
            yield ": connected\n\n"                   # flush frame đầu, mở đường ống ngay
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=_HEARTBEAT)
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"           # comment-line: giữ conn, FE không thấy
        finally:
            bus.unsubscribe(conv_id, q)               # MỌI đường thoát đều dọn subscriber

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)
```

Redact trước khi bắn (gọi trong `emit`, §3) — khẩu vị bank: output agent đi ra FE/trace
không được mang secret:

```python
# app/sse/redact.py
import re
_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "[REDACTED:api-key]"),
    (re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----[\s\S]+?-----END[A-Z ]*PRIVATE KEY-----"),
     "[REDACTED:private-key]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED:aws-key]"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
     "[REDACTED:jwt]"),
    (re.compile(r"[A-Za-z0-9+/=]{400,}"), "[REDACTED:blob]"),
]

def redact_deep(obj):
    if isinstance(obj, str):
        for p, r in _PATTERNS: obj = p.sub(r, obj)
        return obj
    if isinstance(obj, dict):  return {k: redact_deep(v) for k, v in obj.items()}
    if isinstance(obj, list):  return [redact_deep(v) for v in obj]
    return obj
```

### Lưu ý — bảng bẫy sống còn

| Bẫy | Triệu chứng | Rule |
|---|---|---|
| Thiếu `X-Accel-Buffering: no` | Chạy ngon local, deploy sau nginx thì SSE **im lặng tuyệt đối** — event kẹt trong buffer proxy, dồn cục lúc đóng conn | Header này là load-bearing, đặt cứng trong `_SSE_HEADERS`, viết test check response header |
| Thiếu `Cache-Control: no-cache` / dính gzip middleware | Frame bị cache/gom, chữ ra giật cục hoặc không ra | Đủ bộ 4 header; exclude route SSE khỏi GZipMiddleware |
| Không heartbeat | LB/proxy cắt conn idle sau 30–60s; sub chạy 2 phút không chunk nào → FE tưởng chết, reconnect bão | `wait_for(timeout=15s)` → `": heartbeat\n\n"`. Comment-line (bắt đầu `:`) — spec SSE bỏ qua, không lẫn vào data |
| Client rời mà không dọn subscriber | Queue mồ côi tích event tới `_MAX_QUEUE`, memory leak theo giờ demo | `unsubscribe` trong `finally` — cover cả disconnect, shutdown, exception. Client rớt thì `yield` raise → `finally` vẫn chạy |
| Không cap connection | 1 user mở 30 tab / script lỗi loop reconnect → cạn fd của worker duy nhất | Cap per-conversation (10), check TRƯỚC subscribe, trả 429 có message — FE gặp 429 thì backoff dài |
| Bắn payload thô của agent/tool ra FE | Key/JWT/PEM lọt vào trace, audit, screenshot demo — chết điểm bank | `redact_deep` nằm TRONG `emit` — cổng duy nhất, không route nào lách được |
| Auth bằng header `Authorization` | `EventSource` không set được custom header | JWT qua cookie (`withCredentials: true`) — cùng cơ chế các REST call |
| Vòng lặp chỉ chờ `q.get()` vô hạn | Không phát hiện disconnect/shutdown cho tới event kế | Timeout 15s làm 3 việc: heartbeat + poll `is_disconnected` + thoát nhanh khi uvicorn shutdown cancel generator |

---

## 5. Ai bắn event — mapping vào luồng vỏ

### Nguyên lý

**Ghi DB xong mới `emit`.** DB là nguồn sự thật render (§0) — SSE chỉ là thông báo "DB có
cái mới". Thứ tự ngược lại (bắn trước, ghi sau) tạo cửa sổ FE-biết-thứ-DB-chưa-có: ghi fail
hoặc client refetch đúng lúc đó là UI lùi/nhảy. Ngoại lệ duy nhất: `chat.delta` chunk —
không có bản ghi DB per-chunk, nguồn sự thật của nó là message ghi lúc kết lượt (mang về
FE qua `done.full_text`).

Nhắc lại ranh giới: **SSE bus ≠ hàng đợi phòng.** Sub xong việc thì vỏ làm 2 việc độc lập —
(a) đẩy event vào hàng đợi phòng để đánh thức MAIN (spec §4.2, orchestration), (b) `emit`
SSE cho FE (thông báo). Đường (b) lỗi/lỡ không được phép ảnh hưởng đường (a).

### Bảng mapping

| Điểm trong luồng vỏ | Ghi DB (trước) | Emit (sau) |
|---|---|---|
| Trạng thái ca đổi: user gửi lượt / MAIN kết lượt / phiếu chặn / ca lỗi | `UPDATE conversations.status` | `conversation.status {status}` |
| MAIN gọi `orch_dispatch` → vỏ tạo task + spawn sub nền | `INSERT tasks` (status=queued — thành running khi qua semaphore, xem multi-agent §3) | `task.created {task}` |
| Sub kết thúc — MỌI kết cục: done / failed / timeout / user hủy | `UPDATE tasks` (status, result, ended_at, cost) | `task.status {task}` (+ đẩy hàng đợi phòng đánh thức MAIN — đường riêng) |
| Lượt MAIN đang stream, mỗi text chunk từ SDK | — (không ghi per-chunk) | `chat.delta {turn_id, chunk, seq}` |
| Lượt MAIN kết thúc | `INSERT messages` (toàn văn) | `chat.delta {done: true, full_text, seq cuối}` |
| Agent (main/sub) gọi tool `present(card)` — CHỈ 6 loại hiển thị; card `approval` KHÔNG đi đường present (spec §6) | `INSERT cards` | `card {card}` |
| Mỗi tool-call của main/sub trả về (audit hook) | `INSERT tool_calls` (append-only) | `toolcall {task_id, tool, summary, cost}` |
| Wrapper gated — **nhánh 4** (chặn lần đầu, spec §4.4): tạo phiếu + VỎ tự sinh card | `INSERT approvals` (pending) + `INSERT cards` (approval) + `UPDATE conversations.status` | **3 event cùng nguồn**: `approval.pending {phieu}` + `card {card}` + `conversation.status → waiting_approval` (BẮT BUỘC, không phải "thường kèm") |
| Wrapper gated — **nhánh 3** (gọi lại lúc còn pending) | — (không ghi gì — idempotent) | — (không event nào — không spam badge/card) |
| Wrapper gated — **nhánh 2** (claim phiếu approved → thực thi) | `UPDATE approvals` (used, used_at, receipt) | — (không event riêng; FE thấy `used` qua refetch — §0) |
| Wrapper gated — **nhánh 1** (retry sau thành công → trả biên nhận cũ) | — (không ghi) | — (không event) |
| Admin `POST /approvals/{id}/decide` | `UPDATE approvals` (status, decided_by, reason — atomic WHERE pending) | `approval.decided {phieu}` (+ đẩy hàng đợi phòng đánh thức MAIN resume — đường riêng) |

### Lưu ý

| Bẫy | Rule |
|---|---|
| Emit trong transaction, trước commit | Emit SAU commit. Transaction rollback mà event đã bay = FE thấy ma |
| Emit fail làm fail luồng chính | `emit` là fire-and-forget (put_nowait, không raise) — thông báo lỗi không được giết nghiệp vụ; FE tự lành nhờ refetch |
| Dồn emit vào "chỗ nào tiện thì bắn" rải rác | Mỗi dòng bảng trên có đúng 1 điểm bắn, đặt cạnh đúng câu ghi DB tương ứng. Grep `emit(` phải ra được bảng này |
| Sub chết đường nào đó không ra `task.status` | Cùng invariant spec §4.2: MỌI kết cục sub → 1 UPDATE tasks + 1 emit. Timeout cũng là kết cục |
| Boot sau restart còn task `running` mồ côi trong DB | Spec §8: boot chỉ `UPDATE failed ("server restart")` — **KHÔNG emit** (mọi conn SSE đã đứt cùng server; FE mở lại tự lành qua refetch-on-connect §3) |

---

## 6. Checklist build nhanh

1. `bus.py` (subscribe/unsubscribe/publish/cap) → `redact.py` → `emit.py` (envelope + seq per-turn).
2. Route `/api/conversations/{id}/sse` với đủ 4 header + heartbeat 15s + `finally` unsubscribe.
3. Cắm `emit` theo bảng §5 — mỗi điểm ngay SAU câu ghi DB tương ứng (chú ý: nhánh 4 wrapper
   bắn 3 event, nhánh 1/2/3 bắn 0).
4. FE: `useConversationSSE` (hook §3) + handlers upsert-theo-id dùng chung shape với `GET /conversations/{id}`.
5. Test tay 4 kịch bản: (a) `curl -N` thấy heartbeat mỗi 15s; (b) tắt mạng giữa lượt stream →
   mở lại → text đúng nguyên văn (nhờ refetch + `done.full_text`); (c) mở 11 tab → tab 11 nhận 429;
   (d) đứng sau nginx local → event vẫn ra realtime (header §4 sống).
