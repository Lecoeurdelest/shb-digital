# CONTRACT — API + SSE + Envelope (1 nguồn sự thật FE↔BE)

> Chốt ở kickoff S1 (architect, D-30). BE define — FE ăn theo, 1 codepath render.
> Nguồn: SPEC §5 (error) · §9 (SSE) · §10 (data model) · §11 (API). File này = bản THI HÀNH
> gọn cho FE/BE khỏi tự đoán shape. Đổi shape → sửa file này TRƯỚC, báo cả 2 phía.
> Trạng thái S1: role động (chỉ `credit` mount thật; legal/products/ops sau). Card/approval = S3/S4.

---

## 0. Quy ước chung

- **Success = RESOURCE TRẦN** (row/list serialize thẳng — KHÔNG bọc `{success, data}`). SPEC §11.
- **Error = 4-field** `{code, message, hint, retryable}` — MỌI lỗi toàn hệ. SPEC §5.
  `hint` = action kế cụ thể. `retryable` = client thử lại y nguyên có ích không.
- **REST dùng HTTP status** cho phân loại (200/201/202/400/401/404/409/429); body lỗi mới là 4-field.
- **id**: mọi id do BE sinh (uuid string). FE cầm id để tham chiếu; model KHÔNG bao giờ thấy id (SPEC §15).
- Timestamp: ISO-8601 UTC string.

---

## 1. Auth (SPEC §11 · D-19)

2 account seed: `user` (RM) · `admin` (quản lý/compliance). JWT.

| Method | Path | Body | Trả (success) |
|---|---|---|---|
| POST | `/api/auth/login` | `{username, password}` | `{token, user: {username, role}}` — role ∈ `user`\|`admin` |

- JWT qua **cookie** (`withCredentials`) — vì `EventSource` không set custom header (streaming-sse.md §4).
  (S1 có thể bypass auth tạm nếu chưa xong — ghi deviation; nhưng endpoint login + 2 account seed là scope T1-1.)
- 401 khi sai credential / thiếu token → body 4-field `{code:"unauthorized", ...}`.

## 2. Conversations + Chat (SPEC §11)

| Method | Path | Body | Trả (success) | Status |
|---|---|---|---|---|
| GET | `/api/conversations` | — | `Conversation[]` | 200 |
| POST | `/api/conversations` | `{title}` | `Conversation` | 201 |
| GET | `/api/conversations/{id}` | — | `ConversationFullState` | 200 (404 nếu không có) |
| POST | `/api/conversations/{id}/chat` | `{content}` | `{}` hoặc `{queued: bool}` | **202** (ack — main stream qua SSE, KHÔNG chờ) |
| GET | `/api/conversations/{id}/sse` | — | text/event-stream (§4) | 200 |

Main đang bận → tin user XẾP HÀNG (multi-agent §2), vẫn trả 202. FE hiện "đang xử lý" từ `conversation.status`.

## 3. Shape (types) — khớp `frontend/src/types.ts`

```ts
type ConversationStatus = 'running' | 'waiting_approval' | 'done' | 'failed' | 'idle';
interface Conversation { id; user_id?; title; status: ConversationStatus; sdk_session_id?: string|null; created_at; }

type MessageSender = 'user' | 'assistant' | 'system';
interface Message { id; conv_id; ts; sender: MessageSender; content; meta?: object|null; }

type TaskStatus = 'queued' | 'running' | 'done' | 'failed';  // + 'timeout' map về failed ở render
interface OrchTask { id; conv_id; role: string; title; status: TaskStatus;
                     input?; result?: object|null; queued_at?; started_at?; ended_at?; cost?; }

interface ConversationFullState { conversation: Conversation; messages: Message[]; tasks: OrchTask[]; }

interface ApiError { code: string; message: string; hint: string; retryable: boolean; }  // CHỈ error
```

- `OrchTask.role` = string tự do (role động SPEC §3) — FE KHÔNG hardcode enum cứng. S1 chỉ thấy `credit`.
- `outcome` của sub (done/failed/timeout) map vào `tasks.status`: timeout → `failed` (render), result.reason giữ chi tiết.

## 4. SSE (SPEC §9 · streaming-sse.md §2)

**Envelope 1 shape** — FE parse 1 chỗ, switch theo `type`. Frame `data:` only (không `event:`/`id:`):
```
data: {"type":"chat.delta","conversation_id":"c_01","seq":12,"ts":"...","data":{...}}\n\n
```
```ts
interface SSEEnvelope<T> { type: SSEEventType; conversation_id: string; seq: number|null; ts: string; data: T; }
```

| `type` (S1 dùng ✓) | `data` | Ghi chú |
|---|---|---|
| ✓ `chat.delta` | `{turn_id, chunk, done, full_text?}` | seq per-turn; `done:true` mang `full_text` (bản DB) — van tự lành (streaming-sse §3) |
| ✓ `task.created` | `{task: OrchTask}` | full row, FE upsert theo id |
| ✓ `task.status` | `{task: OrchTask}` | full row (status/result/ended_at) |
| ✓ `conversation.status` | `{status: ConversationStatus}` | badge |
| (S3) `card` | `{card}` | canvas — chưa dùng S1 |
| (S4) `approval.pending`/`approval.decided` | `{phieu}` | phanh — chưa dùng S1 |
| (S4) `toolcall` | `{task_id, tool, summary, cost}` | trace/cost — chưa dùng S1 |

- Bắn **nguyên row** (không diff) — FE upsert theo id, cùng shape REST → 1 codepath render.
- **Ghi DB xong mới emit** (trừ chat.delta chunk). Header SSE: `X-Accel-Buffering:no` + `Cache-Control:no-cache` + heartbeat 15s (streaming-sse §4).
- Reconnect: FE `GET /conversations/{id}` full state rồi nghe tiếp — KHÔNG replay-cursor (SPEC §14).

### 4b. Nhánh FAILED — chốt để bubble không treo (architect, 2 gap FE surface trước T1-3)

**Gap 1 — MỌI kết lượt main bắn `chat.delta {done:true}` (khớp streaming-sse §3):** dù lượt
XONG / LỖI / INTERRUPT, BE PHẢI bắn `chat.delta {turn_id, done:true, full_text=<phần đã stream, có thể rỗng>}`
+ pop seq-counter TRƯỚC/CÙNG `conversation.status:failed`. **Không được** kết lượt fail mà thiếu
`done` → FE đóng bubble streaming KHI nhận done; thiếu done = bubble treo lastSeq lơ lửng tới refetch.
(BE nào emit conversation.status:failed thì emit done trước — 1 điểm bắn, streaming-sse §5.)

**Gap 2 — user thấy LÝ DO lỗi ở đâu (KHÔNG thêm field vào conversation.status — giữ nó chỉ badge, N4):**
- **Lỗi ở SUB** (credit timeout/fail): qua `task.status {task}` với `task.status='failed'` + `task.result.reason`
  (§3 — result.reason giữ chi tiết). FE render reason từ task result (badge task đỏ + tooltip/dòng reason).
- **Lỗi ở MAIN** (lượt main hết trần retry): main ghi 1 message `sender='system'` nội dung lỗi
  (multi-agent §9 — persist DB để user thấy trong LỊCH SỬ chat, F5 không mất) → về FE qua chat.delta
  thường HOẶC message trong full-state refetch. Rồi `conversation.status:failed` (badge).
- `conversation.status.data` = `{status}` THÔI — không mang message/hint. Error 4-field là shape REST/tool (§0), KHÔNG phải SSE payload.

## 5. S1 dùng gì (lát cắt dọc tối thiểu)

FE/BE S1 chỉ cần: auth login · conversations list/create/get · chat POST · SSE (`chat.delta`+`task.created`+`task.status`+`conversation.status`). Card/approval/toolcall = sprint sau (shape đã khai sẵn để FE không phải sửa type khi tới).
