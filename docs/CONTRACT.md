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
- **REST dùng HTTP status** cho phân loại (200/201/202/400/401/403/404/409/429); body lỗi mới là 4-field.
- **id**: mọi id do BE sinh (uuid string). FE cầm id để tham chiếu; model KHÔNG bao giờ thấy id (SPEC §15).
- Timestamp: ISO-8601 UTC string.
- Mọi resource vận hành gắn tenant (conversation, approval, audit, assessment, stats/cost và case
  link) chỉ được đọc/ghi trong tenant từ phiên đăng nhập; ID tenant khác trả bề mặt 404-hide hoặc
  danh sách rỗng, không có query/body override.

---

## 1. Auth (SPEC §11 · D-19)

Role: `customer` (khách hàng) · `user` (RM/cán bộ ngân hàng) · `admin` (quản lý/compliance). JWT.

| Method | Path | Body | Trả (success) |
|---|---|---|---|
| POST | `/api/auth/login` | `{username, password}` | `{token, user: {username, role, tenant_id}}` — role ∈ `customer`\|`user`\|`admin` |
| GET | `/api/me` | — | `{username, role, owner_id, tenant_id, user:{username, role, tenant_id}}`; `owner_id: string|null` |

- JWT qua **cookie** (`withCredentials`) — vì `EventSource` không set custom header (streaming-sse.md §4).
  `/api/me` là boot-check canonical; `/api/auth/me` chỉ giữ backward compatibility cùng payload.
- `tenant_id` do server lấy từ account và đóng vào JWT; client không được gửi/chọn tenant trên API
  nghiệp vụ. Token cũ thiếu claim được server resolve lại từ `users`, không mặc định sang tenant khác.
- 401 khi sai credential / thiếu token → body 4-field `{code:"unauthorized", ...}`.

## 2. Conversations + Chat (SPEC §11)

| Method | Path | Body | Trả (success) | Status |
|---|---|---|---|---|
| GET | `/api/conversations` | — | `Conversation[]` | 200 |
| POST | `/api/conversations` | `{title, group_id?}` | `Conversation` | 201 |
| GET | `/api/conversations/{id}` | — | `ConversationFullState` | 200 (404 nếu không có) |
| POST | `/api/conversations/{id}/chat` | `{content}` | `{}` hoặc `{queued: bool}` | **202** (ack — main stream qua SSE, KHÔNG chờ) |
| GET | `/api/conversations/{id}/sse` | — | text/event-stream (§4) | 200 |

Main đang bận → tin user XẾP HÀNG (multi-agent §2), vẫn trả 202. FE hiện "đang xử lý" từ `conversation.status`.

Mọi list/get/create/patch/delete/chat/SSE/interrupt được scope theo tenant trong JWT trước ownership
scope hiện hữu. `admin` thấy mọi phiên **trong tenant của mình**, không thấy tenant khác. ID tenant
không nhận từ body/query để tránh confused-deputy.

### 2b. Conversation groups

Group chỉ là thư mục tổ chức các phiên xử lý, không phải `case`, `application`, team hay kênh chat
chung. Một conversation thuộc tối đa một group; `group_id=null` nghĩa là “Chưa phân nhóm”.

| Method | Path | Body | Trả (success) | Status |
|---|---|---|---|---|
| GET | `/api/conversation-groups` | — | `ConversationGroup[]` | 200 |
| POST | `/api/conversation-groups` | `{name}` | `ConversationGroup` | 201 |
| PATCH | `/api/conversation-groups/{id}` | `{name}` | `ConversationGroup` | 200 |
| DELETE | `/api/conversation-groups/{id}` | — | `{deleted:true,id}` | 200 |

- Group luôn thuộc tenant từ JWT và có `created_by`; trùng `name` không phân biệt hoa/thường trong
  workspace của cùng người tạo → 409. Non-admin chỉ list/sửa group của mình; admin có thể đọc toàn
  tenant để giám sát nhưng group khác tenant luôn bị 404-hide.
- Xóa group chỉ đưa conversation về `group_id=null`, không xóa conversation hoặc audit.
- `PATCH /api/conversations/{id}` nhận thêm `group_id?: string|null`; group khác tenant/không tồn tại
  đều trả 404 `group_not_found` để không lộ topology tenant.

## 3. Shape (types) — khớp `frontend/src/types.ts`

```ts
type ConversationStatus = 'running' | 'waiting_approval' | 'done' | 'failed' | 'idle';
interface Conversation { id; user_id?; tenant_id: string; group_id: string|null; title; status: ConversationStatus; sdk_session_id?: string|null; created_at; }

interface ConversationGroup { id: string; name: string; created_by: string; created_at: string; updated_at: string; }

type MessageSender = 'user' | 'assistant' | 'system';
interface Message { id; conv_id; ts; sender: MessageSender; content; meta?: object|null; }

type TaskStatus = 'queued' | 'running' | 'done' | 'failed';  // + 'timeout' map về failed ở render
interface OrchTask { id; conv_id; role: string; title; status: TaskStatus;
                     input?; result?: object|null; queued_at?; started_at?; ended_at?; cost?; }

interface Card { id: string; conv_id: string; task_id: string|null; type: string; ts: string; title?: string; items?: object[]; sources?: string[]; }  // S2: card canvas — id VỎ-inject; nội dung (title/items/sources) agent bơm
interface ConversationFullState { conversation: Conversation; messages: Message[]; tasks: OrchTask[]; cards: Card[]; }  // S2: +cards (canvas reload)

interface ApiError { code: string; message: string; hint: string; retryable: boolean; }  // CHỈ error
```

- `OrchTask.role` = string tự do (role động SPEC §3) — FE KHÔNG hardcode enum cứng. S1 chỉ thấy `credit`.
- `outcome` của sub (done/failed/timeout) map vào `tasks.status`: timeout → `failed` (render), result.reason giữ chi tiết.
- **`conv_id` = string** (D-31/D-76): định danh xuyên tầng (registry/cwd/SSE), API không đổi.
  DB dual-write thêm `conversation_id uuid FK` cho row có conversation cha; text legacy vẫn được giữ
  trong cửa sổ migration. FE tiếp tục dùng string — không lộ cột FK nội bộ.

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
| ✓(S2) `card` | `{card}` — full row cards (id VỎ-inject, task_id, type, title, items, sources...) | canvas render; FE upsert theo id, replace theo (task_id,type) giữ ts mới nhất |
| ✓(S3) `approval.pending`/`approval.decided` | `{phieu}` | phanh — badge chờ duyệt, resume |
| ✓(S4) `toolcall` | `{id, task_id, tool, summary, cost}` | trace timeline (T4-1); `id`=tool_calls.id → FE upsert dedup (reload GET /api/audit + live SSE cùng id); `cost`=null hiện tại (SDK per-turn, không per-tool) |
| ✓(S4) `thinking` | `{task_id, text}` | trace: suy nghĩ model (ThinkingBlock) — LIVE-ONLY, KHÔNG persist DB (T4-2 F1); `task_id`=sub role · `null`=main; `text`=block.thinking (FE line-clamp nếu dài) |

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

## 6. Approval resource + deep-link (S19 · D-71)

### 6a. REST — lấy đúng một phiếu

`GET /api/approvals/{id}` chỉ dành cho `admin`; success `200` trả **resource trần** sau đây,
không bọc `{data}`. Endpoint tìm được cả bốn trạng thái, không chỉ hàng chờ:

```ts
type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'used' | 'exec_failed';
interface Approval {
  id: string;
  conv_id: string;
  task_id: string | null;
  action: string;
  payload: Record<string, unknown>;
  payload_hash: string;
  status: ApprovalStatus;
  decided_by: string | null;
  decided_at: string | null;
  reason: string | null;
  used_at: string | null;
  receipt: Record<string, unknown> | null;
  exec_attempts: number;
  display: {
    customer_name: string | null;
    owner_id: string | null;
    loan_id: string | null;
    amount_vnd: number | null;
    lane: string | null;
  };
}
```

Không có phiếu (kể cả `id` sai format) → `404` với đúng envelope 4-field:

```json
{"code":"not_found","message":"Không có phiếu '<id>'.","hint":"Kiểm lại id hoặc liên kết.","retryable":false}
```

Thiếu phiên → `401`; role `customer`/`user` → `403`. Hai lỗi authz cũng dùng envelope §0 và
không được phân biệt “phiếu có thật” với “phiếu không tồn tại”. `GET /api/approvals?status=pending`
vẫn là API danh sách hàng chờ riêng, không thay thế endpoint theo `id` này.

### 6b. URL vào đúng phiếu

URL công khai giữa các bề mặt là `/?tab=approvals&approval=<id>`:

- `admin` đã đăng nhập: mở Control Tower → tab approvals, gọi đúng một lần endpoint §6a rồi
  focus/highlight phiếu; phiếu đã `approved`/`rejected`/`used` vẫn mở và hiện trạng thái cuối.
- Chưa đăng nhập: giữ **nguyên pathname + query string** qua login handoff; login thành công với
  role `admin` thì tiếp tục đúng deep-link, không rơi về URL mặc định.
- `customer` và `user` không-admin: **không gọi bất kỳ approval API nào** (zero fetch), không mount
  Tower/phiếu, không hiện thông báo suy ra phiếu có hay không. Nếu tự gọi API trực tiếp thì luôn
  nhận `403` chung như trên.

Chat ngoài ngân hàng chỉ mang link này như “chuông cửa”. Không có endpoint hoặc nút approve/reject
từ Lark/Teams/webhook; quyết định chỉ diễn ra trong Control Tower sau auth ngân hàng.

## 7. Shadow-review ledger + match-rate API (S18)

### 7c. Cấu hình agent (admin)

`GET /api/admin/agent-config` chỉ dành cho `admin`. Success trả resource trần gồm `environment`,
`providers` (public view, không key/URL secret) và danh sách prompt. Mỗi prompt có `key`, `scope`,
`description`, `variables`, `active` (`version`, `content`, `activated_by`, `activated_at`). Đây là
cấu hình hành vi agent; không chứa approval policy, tool whitelist hay credential provider.

`POST /api/admin/agent-config/prompts/{key}` chỉ dành cho `admin`, body:

```json
{"content":"...", "activate":true}
```

`content` dài 1–30000 ký tự. Server tạo version immutable (hoặc tái dùng bản có checksum trùng) và,
nếu `activate=true`, atomically đổi binding cho `SHB_PROMPT_ENV` hiện hành. Success trả snapshot cấu
hình đã làm mới. Mọi lần tạo/kích hoạt được ghi append-only trong audit config; response/error không
bao giờ trả DSN, API key hay nội dung provider secret. Provider topology/default chỉ đổi qua
GitOps/env và restart đã kiểm soát.

### 7a. Snapshot và tính `match`

Khi tạo phiếu `pending`, BE chụp lane/assessment và khuyến nghị phản-thực vào các cột nội bộ của
phiếu (không trộn vào `payload`/`payload_hash`). Khi người duyệt chuyển phiếu
`pending → approved|rejected`, BE dùng đúng snapshot đó để ghi một row append-only
`shadow_reviews` **trong cùng transaction** với approval decision. `UNIQUE(approval_id)` bảo đảm
double-click/race không tạo hai mẫu; nếu ghi ledger lỗi thì decision cũng rollback. Assessment hoặc
config đổi sau lúc tạo phiếu không được viết lại lịch sử, gồm:

```ts
interface ShadowReview {
  approval_id: string;
  conv_id: string;
  system_lane: 'green' | 'yellow' | 'red' | null;
  system_recommendation: 'auto-eligible' | 'human-review' | 'reject-recommended';
  human_decision: 'approved' | 'rejected';
  human_reason: string | null;
  decided_at: string;                 // ISO-8601 UTC
  match: boolean | null;
}
```

`system_recommendation` là khuyến nghị phản-thực (counterfactual) của ma trận thẩm quyền tại thời
điểm **tạo phiếu**, trước override ép đi người của shadow-mode: lane `red` →
`reject-recommended`; nếu ma trận không có override sẽ tự động → `auto-eligible`; mọi trường hợp
còn lại (kể cả action không có đường auto) → `human-review`. Cụ thể, khi threshold cấu hình
`<=0`, route thật luôn qua người nhưng snapshot phản-thực dùng ngưỡng danh nghĩa tương thích
`500_000_000`; threshold dương cấu hình được dùng nguyên giá trị cho cả route và snapshot. Quy tắc
so sánh cố định:

- `auto-eligible`: comparable; `match=true` khi người duyệt `approved`, ngược lại `false`.
- `reject-recommended`: comparable; `match=true` khi người duyệt `rejected`, ngược lại `false`.
- `human-review`: trung tính; `match=null`, không ép diễn giải đồng thuận/bất đồng.

### 7b. `GET /api/stats/shadow-match`

Endpoint chỉ dành cho `admin`, không nhận query param. Success `200` trả object trần đúng shape:

```json
{
  "total": 3,
  "comparable": 2,
  "matched": 1,
  "rate": 0.5,
  "by_lane": [
    {"lane":"green","total":1,"comparable":1,"matched":0,"rate":0.0},
    {"lane":"yellow","total":1,"comparable":0,"matched":0,"rate":0.0},
    {"lane":"red","total":1,"comparable":1,"matched":1,"rate":1.0}
  ],
  "by_day": [
    {"date":"2026-08-24","total":3,"comparable":2,"matched":1,"rate":0.5}
  ]
}
```

- `total` đếm mọi snapshot; `comparable` chỉ đếm `match IS NOT NULL`; `matched` chỉ đếm
  `match=true`; `rate = matched / comparable`. Khi `comparable=0`, `rate` bắt buộc là `0.0`
  (không `null`, `NaN` hay chia 0).
- Mỗi bucket dùng cùng mẫu số comparable. `by_lane` có một row cho mỗi lane quan sát được
  (`green`, `yellow`, `red`, hoặc `null` nếu không có assessment), theo thứ tự đó; lane không có mẫu
  thì không sinh row. `by_day` group theo ngày UTC `YYYY-MM-DD`, tăng dần; ngày trống không sinh row.
- Ledger rỗng trả chính xác
  `{"total":0,"comparable":0,"matched":0,"rate":0.0,"by_lane":[],"by_day":[]}`.

### 7d. `GET /api/stats/shadow-match/mismatches` (S20 · D-79)

Endpoint chỉ dành cho `admin`, tenant luôn lấy từ JWT/account và không nhận `tenant_id` từ query
hoặc body. Success `200` là page object trần:

```ts
interface ShadowMismatch {
  approval_id: string;
  conv_id: string;
  system_lane: 'green' | 'yellow' | 'red' | null;
  system_recommendation: 'auto-eligible' | 'human-review' | 'reject-recommended';
  human_decision: 'approved' | 'rejected';
  human_reason: string | null;
  decided_at: string; // ISO-8601 UTC
}
interface ShadowMismatchPage {
  items: ShadowMismatch[];
  next_cursor: string | null;
}
```

Query contract:

- `from` và `to` là ISO-8601 có timezone; server chuẩn hóa UTC. `from` inclusive, `to` exclusive;
  nếu cả hai có mặt thì bắt buộc `from < to`.
- `lane` nếu có chỉ nhận `green|yellow|red`. `limit` mặc định `50`, nhỏ nhất `1`, lớn nhất `200`.
- Chỉ row `match=false`, sort ổn định `decided_at DESC, approval_id DESC`. Phân trang dùng keyset,
  không dùng offset; trang cuối và trang rỗng trả `next_cursor:null`.
- `cursor` là chuỗi opaque có integrity check, bind với tenant cùng canonical filter
  `from/to/lane`; reuse ở tenant khác hoặc đổi bất kỳ filter nào trả `400 invalid_cursor`, không
  được biến thành danh sách của context mới.
- Timestamp/lane/limit/cursor sai hoặc `from >= to` trả `400` error 4-field §0. Thiếu phiên `401`,
  role `customer|user` trả `403`. Tenant khác không bao giờ thấy row.

Endpoint này chỉ đọc ledger. Write seam duy nhất của `shadow_reviews` vẫn là
`store_shadow.insert_review()` trong transaction `approvals.decide`; không có API update/delete.

## 8. Outbound webhook doorbell (S19 · D-71)

Config: `SHB_NOTIFY_WEBHOOK_URL` rỗng/thiếu = tắt; `SHB_NOTIFY_CHANNEL=lark|generic`
(thiếu = `generic`, giá trị khác = log warning rồi tắt);
`SHB_NOTIFY_INCLUDE_AMOUNT=0|1`, mặc định `0`. Adapter chỉ phát hai thời điểm: phiếu `pending` và
sau decision `approved|rejected`; cả hai đều **sau DB commit + SSE nội bộ**. Đây là best-effort
post-commit: không đổi HTTP response/main flow; không outbox, không queue bền, không replay và
không approve-from-chat.

### 8a. Generic JSON — whitelist chính xác

```json
{
  "action": "disburse",
  "conv_id": "12345678",
  "status": "pending",
  "deep_link": "https://bank.example/?tab=approvals&approval=018f..."
}
```

Chỉ bốn key trên được phép. Khi và chỉ khi `SHB_NOTIFY_INCLUDE_AMOUNT=1`, thêm
`"amount": 500000000` (integer VND). `conv_id` là đúng 8 ký tự đầu; `status` chỉ là
`pending|approved|rejected`. Không copy/merge `payload`, `display`, `receipt` hoặc approval row vào
body.

### 8b. Lark interactive card — whitelist chính xác

```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": {"tag": "plain_text", "content": "BANK Digital · Approval doorbell"}
    },
    "elements": [
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**disburse** · ca `12345678` · pending"
        }
      },
      {
        "tag": "action",
        "actions": [
          {
            "tag": "button",
            "text": {"tag": "plain_text", "content": "Open Control Tower"},
            "type": "primary",
            "url": "https://bank.example/?tab=approvals&approval=018f..."
          }
        ]
      }
    ]
  }
}
```

Nội dung động chỉ lấy từ whitelist generic: `action`, `conv_id` 8 ký tự, `status`, `deep_link`.
Khi include-amount bật, nối đúng ` · 500000000 VND` vào cuối chuỗi `content`; không thêm field/card
element khác. Tuyệt đối không gửi tên khách, owner/loan/application id, hồ sơ, CIC, tài liệu, lý do,
người duyệt hay biên nhận ra webhook.

### 8c. Transport + lỗi

- `POST application/json`; mỗi request có timeout `5s`. Timeout/network error, HTTP `429` hoặc
  `5xx` được thử tối đa **3 attempts tổng**: ngay lập tức, sau `1s`, rồi sau thêm `3s`; sau đó log
  warning và drop. HTTP `4xx` khác không retry.
- Retry có thể tạo notification trùng; webhook chỉ là chuông cửa và deep-link luôn đọc trạng thái
  chuẩn từ bank DC. Không thêm outbox/event-store chỉ để chống trùng.
- Log không chứa full webhook URL/token, headers, request/response body hay field nghiệp vụ. Chỉ log
  channel, status sự kiện, `conv_id` 8 ký tự, attempt, HTTP status hoặc exception class.

## 9. Headless readiness + Embed SDK boundary (S21 · D-74)

Phần này **không đổi** shape conversation/card/SSE ở §2–§4. Nó khóa cách một kênh ngân hàng
(SAHA, website, portal RM hoặc LOS) dùng lõi mà không kéo SPA/Control Tower vào bundle của host.

### 9a. Readiness của lõi

`GET /api/health` vẫn là liveness rẻ `{ok:true}`. Nó chỉ chứng minh process đang trả HTTP, không
được dùng để tuyên bố DB/provider/MCP đã sẵn sàng.

`GET /api/ready` là readiness không cần auth. Success `200` trả resource trần, không lộ URL,
credential, model hay schema nội bộ:

```ts
interface ReadyResponse {
  ready: true;
  profile: 'demo' | 'bank_dc';
  checks: {
    database: true;
    migrations: true;
    provider: true;
    mcp_mounts: true;
  };
}
```

Mỗi lần gọi phải kiểm trực tiếp: kết nối + `SELECT 1` Postgres; revision Alembic hiện tại bằng mọi
head trong repo; provider hiệu lực resolve được; mọi `roles/<role>` mount thành MCP và tool list
không rỗng. Bất kỳ check nào fail → `503` với đúng error 4-field §0, `code="not_ready"`; chi tiết
kỹ thuật chỉ vào server log, không nằm trong response.

### 9b. Public API của package nhúng

Package: `@bank-digital/embed-sdk`. Entry `.` là headless và **không import React, ReactDOM, CSS,
Three.js, Recharts, mock API hay SPA**. Public contract tối thiểu:

```ts
interface BankDigitalClientOptions {
  apiBaseUrl?: string;                  // mặc định '' → /api cùng origin
  credentials?: RequestCredentials;    // mặc định 'include'
  fetch?: typeof globalThis.fetch;      // inject cho host/test
  getAccessToken?: () => string | null | Promise<string | null>;
  headers?: Record<string, string> | (() => Record<string, string> | Promise<Record<string, string>>);
}

interface BankDigitalClient {
  me(): Promise<{username: string; role: 'customer'|'user'|'admin'; owner_id: string|null}>;
  listConversations(): Promise<Conversation[]>;
  createConversation(input: {title: string; provider?: string; model?: string}): Promise<Conversation>;
  getConversation(id: string): Promise<ConversationFullState>;
  sendMessage(id: string, content: string): Promise<{queued: boolean}>;
  openConversationStream(id: string, handlers: StreamHandlers): ConversationStream;
}

declare function createBankDigitalClient(options?: BankDigitalClientOptions): BankDigitalClient;
```

Mọi REST request lấy token **tại thời điểm request** rồi gắn `Authorization: Bearer …`; SDK không
lưu token, không đưa token vào URL/DOM/log/localStorage. Error non-2xx được ném dưới dạng
`BankDigitalApiError(status, body)` với `body` là error 4-field hoặc `null` nếu upstream trả sai.
SDK không export `decideApproval`, `listApprovals` hay một action phê duyệt tương đương.

`openConversationStream` dùng `fetch()` đọc `text/event-stream`, do đó cùng auth adapter với REST
và dùng được Bearer. Parser chỉ nhận data-frame §4, bỏ comment frame, hỗ trợ chunk cắt giữa UTF-8/
dòng/frame, bỏ frame JSON lỗi mà không crash. Reconnect exponential tối đa 30 giây; heartbeat im
quá 25 giây thì abort + reconnect. Sau mỗi connect/reconnect, React provider refetch full-state;
không gửi `Last-Event-ID`, không replay cursor và DB tiếp tục là nguồn sự thật.

### 9c. React và Web Component

Entry `./react` export provider có context đúng ba phần `{state, actions, meta}` và compound
components để host tự compose. Hai variant dựng sẵn là tên tường minh:

- `CustomerAssistant`: chat; không hiện/khởi tạo hành động phê duyệt.
- `RmCopilot`: chat + canvas card; không chứa sidebar toàn hệ, lobby 3D, dashboard hay Tower.

Entry `./element` export `mountCustomerAssistant` và `mountRmCopilot`, trả handle có `unmount()`.
Standalone bundle tự đăng ký `<bank-digital-customer-assistant>` và
`<bank-digital-rm-copilot>` trong Shadow DOM để CSS host không rò vào widget và ngược lại. Custom
element chỉ nhận `api-base-url`/`conversation-id`/`heading` và optional `style-nonce`; tích hợp
Bearer phải dùng mount API với callback token, không bao giờ nhét token vào attribute. React variant
và mount API cũng nhận `styleNonce` để host có CSP nghiêm cấp nonce cho stylesheet Shadow DOM.

### 9d. Origin, CORS và biên dữ liệu

Đường khuyến nghị trong bank DC: host reverse-proxy `/api` về FastAPI, SDK dùng `apiBaseUrl:''` +
httponly cookie. Direct cross-origin mặc định bị chặn. Chỉ khi vận hành đặt
`SHB_CORS_ORIGINS=https://saha.bank,https://los.bank` thì backend mới trả CORS cho **đúng** origin
allowlist; wildcard `*`, origin có path/query/userinfo và scheme ngoài `http|https` là cấu hình lỗi.
Cross-origin nên dùng Bearer do BFF/SSO ngân hàng cấp vì auth cookie hiện `SameSite=Lax`.

SDK chạy bên trong kênh ngân hàng, nhận cùng resource đã được `require_user` + ownership scope ở
server. Nó không gửi telemetry ra ngoài, không gọi Lark/Teams và không tự copy CIC/hồ sơ sang một
dịch vụ thứ ba. `bank_dc` là profile fail-fast riêng; profile `demo`/compose hiện hữu không phải
bằng chứng data-residency.

## 10. Presentation boundary của Workspace (D-75)

D-75 **không đổi API, SSE, DB hoặc package SDK** trong §1–§9. SPA reference chỉ đổi cách trình bày
cho `customer`/`user` và mặt public:

- `Conversation` được gọi là **Phiên xử lý**. Không được gọi là “hồ sơ”, “case” hay “application”
  vì hiện chưa có quan hệ application↔conversation hoặc read-model tương ứng.
- Reference Workspace tạo phiên với `{title}` và để server chọn provider/model mặc định. Optional
  `provider`/`model` trong contract vẫn giữ cho runtime, adapter kỹ thuật và tương thích consumer;
  bề mặt RM/khách/public không gọi `/api/models`, không picker/switch theo lượt.
- `task`, `card`, nguồn, trạng thái, lỗi và form intake vẫn render theo quyền. Workspace/Embed SDK
  chỉ render **trạng thái** approval ở chế độ đọc; hành động Duyệt/Từ chối chỉ thuộc Control Tower có
  auth + audit theo D-71/D-74, không có đường quyết định từ Workspace hay kênh nhúng.
  `toolcall`/`thinking`, token/cost/model và raw task input/output vẫn được backend ghi hoặc stream
  theo contract, nhưng reference Workspace không fetch/hydrate hay render chúng cho RM/khách.
- Sản phẩm công việc là tab mặc định; tiến độ xử lý là tab phụ. Composer chỉ là cửa gửi yêu cầu
  nghiệp vụ, không phải nơi cấu hình runtime.

`CaseSummary`/`CaseDetail`, work queue theo application, thiếu chứng từ và application↔conversation
relation được định nghĩa tại §11; không suy case từ title hoặc `conv_id`.

## 11. Case intake và bàn làm việc sơ thẩm (D-77)

Phần này bổ sung lớp **Case/Application Workspace** mà §10 đã để mở. Nó không đổi shape của
conversation, card, SSE, approval hoặc Embed SDK ở §1–§10.

`conversation` vẫn là phiên xử lý; `case` là hồ sơ nghiệp vụ có identity riêng. Một case chỉ được
tạo/cập nhật qua nguồn nghiệp vụ đã tin cậy hoặc read-model nội bộ, tuyệt đối không suy từ title,
chat, `conv_id`, webhook D-71 hay thao tác gõ tay ở Control Tower. SDK là tùy chọn để nhúng UI làm
việc vào LOS/SAHA; nó **không** là đường intake.

### 11a. Transport và cấu hình nguồn

P0 mở một cổng REST server-to-server để LOS, SAHA hoặc BFF ngân hàng gọi qua API Gateway:

```http
POST /api/integrations/v1/case-events
Authorization: Bearer <service-credential>
Idempotency-Key: <source event_id>
Content-Type: application/json
```

Broker consumer, pull/read-through adapter và batch loader (legacy/backfill) là transport P1/P2;
khi có, chúng phải gọi cùng service `ingest_case_event`, không tự ghi case hoặc conversation. Kênh
Lark/Teams/webhook §8 chỉ là chuông cửa outbound và không bao giờ là transport intake.

Mỗi source nằm trong `configs/case-intake.yaml`, commit **không chứa secret**. Schema v2 bind
credential của một source vào đúng một tenant và cho phép override profile theo product:

```yaml
version: 2
sources:
  los:
    tenant_slug: bank-digital-default
    enabled: false
    modes: [api]
    accepted_schema_versions: [1]
    allowed_event_types: [case.snapshot_upserted, case.preassessment_requested, case.cancelled]
    workflow_profile: preassessment_only
    auto_start: shadow
    allowed_products: [SME_SECURED, UNSECURED_CONSUMER, UNSECURED_PUBLIC]
    product_profiles:
      UNSECURED_CONSUMER: {workflow_profile: preassessment_only, auto_start: shadow}
      UNSECURED_PUBLIC: {workflow_profile: preassessment_only, auto_start: shadow}
    max_payload_bytes: 262144
    api_key_env: SHB_LOS_CASE_INTAKE_API_KEY
```

V1 vẫn được parse nguyên hành vi: server gán `tenant_slug=bank-digital-default` và
`product_profiles={}`. Với v2, `tenant_slug` và `product_profiles` bắt buộc; slug khớp
`^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$`. Mỗi profile product có **đúng** hai khóa
`{workflow_profile, auto_start}`; product không có override fallback tuyệt đối về hai field cấp
source. Product config chỉ thuộc allowlist `SME_SECURED | UNSECURED_CONSUMER | UNSECURED_PUBLIC`.
Mọi product ngoài `SME_SECURED` phải resolve thành đúng `preassessment_only + shadow`; cấu hình
khác bị từ chối lúc load, không được dùng YAML để mở auto.

Loader cấu trúc chạy khi startup ngay sau runtime-security và trước registry reset, orphan cleanup
hay boot agent. Loader không hỏi DB lúc startup. Mỗi request đã khớp service credential mới resolve
`tenant_slug` sang `tenants.id` **bên trong transaction ingest**; slug không tồn tại hoặc DB lỗi trả
`503 case_intake_not_ready` và không có partial write. Tenant không nhận từ body/query/header tùy ý.
Mọi lookup/lock/write inbox, link và conversation dùng tenant đã resolve; conversation mới ghi
`tenant_id` tường minh. Một alias source cho nhiều tenant và đổi unique key DB được defer.

`enabled:false` là default an toàn. `api_key_env` chỉ là connector demo/test sau API Gateway;
giá trị thật nằm trong env/secret manager, không vào YAML, response hay log. Trong `bank_dc`,
gateway phải xác thực service identity bằng mTLS/OIDC client credential, kiểm scope `case:ingest`
và buộc source claim khớp payload trước khi request tới app. Không dùng JWT cookie của người dùng
làm service trust.

Config production đi qua PR/maker-checker, schema validation và artifact checksum; P0 không có màn
chỉnh hot config. Rollout chỉ theo `off → shadow → selected → on`; P0 triển khai `off` và `shadow`
thôi. `shadow` được phép tạo mapping/phiên làm việc nhưng không được gọi tool giải ngân, tạo approval
hay coi kết quả là quyết định tín dụng.

### 11b. Event envelope v1

`Idempotency-Key` bắt buộc bằng `event_id`. `source_version` là số nguyên tăng đơn điệu trên từng
`(source_system, external_case_id)`; adapter của nguồn phải chuyển version riêng của nó về số này.
V1 chỉ nhận allowlist field dưới đây. `document_refs` là mã tham chiếu, không chứa file hay nội dung
chứng từ.

```ts
interface CaseEventV1 {
  schema_version: 1;
  event_id: string;
  event_type: 'case.snapshot_upserted' | 'case.preassessment_requested' | 'case.cancelled';
  source_system: string;
  source_version: number;
  occurred_at: string; // ISO-8601 UTC
  case: {
    external_case_id: string;
    external_party_id?: string;
    assigned_rm_subject?: string; // IdP subject, không phải username/email
    product_code: string;
    loan_amount_vnd: number;
    document_refs?: string[];
    missing_fields?: string[];
  };
}
```

`case.snapshot_upserted` chỉ refresh snapshot; `case.preassessment_requested` đưa case vào trạng
thái sẵn sàng sơ thẩm và, ở source `shadow`, tạo/lấy lại **một** phiên xử lý được link rõ ràng;
`case.cancelled` dừng case chưa được bàn giao nhưng không xóa inbox/audit. P0 chưa chạy MAIN tự động
và không gửi dữ liệu ra ngoài; cán bộ mở đúng case/phiên để bắt đầu quy trình có kiểm soát.

`missing_fields` được server chuẩn hóa thành sorted unique code. Allowlist v1 là
`identity_document`, `internal_identity_mapping`, `income_proof`, `employment_proof`,
`residence_proof`, `tax_return`, `financial_statements`, `financial_statements_2025`,
`collateral_document`, `collateral_valuation`, `legal_document`. Mã liên quan CIC và một hay nhiều giá
trị ngoài allowlist chỉ còn đúng sentinel `additional_information`; raw value không được đưa vào
linked context, read-model hoặc webhook.

Success là resource trần `202`:

```ts
interface CaseEventReceipt {
  id: string;                         // case link id
  event_id: string;
  status: 'accepted' | 'duplicate' | 'stale_ignored';
  source_system: string;
  external_case_id: string;
  source_version: number;
  case_status: CaseStatus;
  conversation_id: string | null;
}
```

### 11c. Case read-model của Control Tower

`GET /api/cases?status=&source=&limit=` dành cho `admin`/middle-office trong Control Tower; P0 chưa
mở trực tiếp cho customer hoặc RM. RM làm việc trong LOS/portal đã được ngân hàng cấp quyền; khi có
IdP mapping thật, endpoint sẽ scope theo assignee thay vì trust `assigned_rm_subject` từ payload.

`GET /api/cases/{id}` cũng chỉ dành cho `admin`, trong đó `id` là UUID nội bộ của
`external_case_links`, và trả một resource `CaseSummary` trần cùng shape bên dưới. Không thấy hoặc
khác tenant đều trả `404 not_found` để hide existence; anonymous trả `401`, role khác trả `403`.
Endpoint exact-case không nhận tenant/source từ query và không dùng identity legacy
`internal_operations:<id>`.

Khi lọc `source`, `internal_operations` là nguồn read-only hợp lệ. Source không có trong config trả
`404 source_not_configured`; source đã cấu hình nhưng đang tắt trả `403 source_disabled`. Hai lỗi chỉ
được kiểm tra **sau** `admin` auth, để không lộ topology tích hợp cho người chưa đăng nhập. Mảng
success rỗng chỉ có nghĩa read-model chưa có case phù hợp; UI không được suy diễn rằng hệ thống nguồn
đã phản hồi, đã bật hoặc đã gửi dữ liệu.

Success trả mảng resource trần, mới nhất trước:

```ts
type CaseStatus =
  | 'received'
  | 'missing_information'
  | 'ready_for_preassessment'
  | 'preassessment_in_progress'
  | 'needs_specialist'
  | 'ready_for_handover'
  | 'cancelled';

interface CaseSummary {
  id: string;
  source_system: string;
  external_case_id: string;
  internal_application_id: string | null;
  party_reference: string | null;      // reference nghiệp vụ, không PII raw
  product_code: string | null;
  loan_amount_vnd: number | null;
  case_status: CaseStatus;
  next_action: string;
  document_count: number;
  missing_fields: string[];
  source_version: number | null;
  data_as_of: string | null;
  synced_at: string;
  conversation_id: string | null;
  assessment: {
    lane: 'green' | 'yellow' | 'red' | null;
    created_at: string | null;
  };
}
```

Danh sách có thể đọc các `applications` demo nội bộ hiện có dưới source `internal_operations` để
demo không rỗng, nhưng chúng là read-only và không được coi là một LOS connector. Case từ event và
application demo được merge bằng identity rõ ràng, không bằng display name/title.

Màn “Cơ sở sơ thẩm” phải render first viewport: mã hồ sơ nguồn, trạng thái bằng text (không chỉ
màu), sản phẩm/số tiền, dữ liệu cập nhật lúc nào, blocker/thiếu gì và **một next action**. Chi tiết
có thể hiển thị basis/criteria đã có, nhưng kết quả `green/yellow/red` là cơ sở sơ bộ, không phải
quyết định cuối hay adverse action.

Khi `conversation_id` khác `null`, Tower có thể có nút **“Mở phiên xử lý”** để điều hướng admin đã
được xác thực tới đúng phiên link sẵn. Nút này không gửi chat, không tạo phiên mới, không đánh thức
MAIN và không tạo approval/disbursement. Khi `conversation_id` là `null`, UI chỉ trình bày next
action; không được dựng nút “tạo/chạy hồ sơ” thay thế.

### 11d. Atomicity, idempotency và lỗi

Trong một transaction, ingestion phải ghi inbox append-only, tạo/cập nhật `external_case_links` và
tạo/lookup conversation (nếu event/profile cho phép). Hai identity độc lập:

- inbox `UNIQUE(source_system, event_id)` để retry không tạo event/case/phiên đôi;
- case link `UNIQUE(source_system, external_case_id)` để version mới cập nhật đúng một case.

Hai unique key vật lý vẫn global trong S23 vì một source config chỉ thuộc một tenant; dù vậy mọi SQL
runtime phải kèm `tenant_id`, advisory-lock phải bind tenant, và link/conversation phải khớp tenant.

Cùng event id + cùng payload hash trả receipt cũ với `status:'duplicate'`; cùng event id + hash khác
trả `409 idempotency_conflict`. Version nhỏ hơn version đã nhận trả `202 stale_ignored`; version bằng
nhau nhưng content khác trả `409 source_version_conflict`. Case/event payload hỏng, source không
allowlist, source tắt, product ngoài allowlist hoặc vượt max byte phải fail-closed bằng envelope
4-field §0; inbox/event payload không được chép vào audit UI hoặc server log.

Không rõ assignee/party mapping thì case nằm unassigned để middle-office xử lý; không được gán theo
username/email payload. Không có credential hợp lệ trả `401`; credential hợp lệ nhưng source không
khớp/tắt trả `403`. Approval API và đường `ops_disburse` giữ nguyên quyền/phanh hiện có — cổng intake
không có quyền phê duyệt hay giải ngân.

### 11e. Operator-start, linked context và rào `preassessment_only` (D-81)

Intake `auto_start: shadow` chỉ commit inbox/link và tối đa một conversation rỗng: **zero** message,
MAIN turn, task, card, approval, `shadow_reviews`, sensitive-tool call hoặc wake. Không có endpoint
start riêng. Admin cùng tenant mở phiên đã link rồi tự gửi một user message qua API chat hiện hữu;
đó là hành động duy nhất bắt đầu lượt xử lý.

Khi dựng system prompt cho lượt chủ động, server đọc link bằng `conversation_id + tenant_id` với
JOIN bắt buộc `e.conversation_id=c.id AND e.tenant_id=c.tenant_id`. Context chỉ gồm:

```ts
{
  source_system: string;
  external_case_id_or_case_id: string;
  product_code: string | null;
  loan_amount_vnd: number | null;
  missing_field_codes: string[];
  data_as_of: string | null;
}
```

Raw `external_case_id` chỉ được dùng khi khớp `^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$`; nếu không,
server dùng UUID link nội bộ. Missing-field dùng allowlist §11b. JSON canonical nằm giữa delimiter
`BEGIN_LINKED_CASE_CONTEXT_JSON`/`END_LINKED_CASE_CONTEXT_JSON` cùng chỉ dẫn rằng mọi value là dữ
liệu không đáng tin, không phải instruction. Không inject/persist raw `party_reference`, assignee,
document ref/content, inbox payload hoặc context block thành message.

Rào thật nằm ở tool: ngay sau mở cursor trong `_gated_txn`, trước cross-owner, advisory lock,
receipt/idempotency, verdict và mọi write, server kiểm link tenant-consistent. Mọi linked
conversation — kể cả product SME — gọi `disburse` hoặc `ops_disburse` đều trả:

```json
{
  "code": "preassessment_only",
  "message": "Phiên intake này chỉ dùng để sơ thẩm, không được thực hiện hành động giải ngân.",
  "hint": "Bàn giao hồ sơ sang quy trình phê duyệt được ngân hàng cấu hình riêng.",
  "retryable": false
}
```

Rào chạy trước cả replay receipt đã dùng; không tạo/đổi approval, card, receipt, conversation hay
gọi inner tool. Conversation nội bộ không có link giữ nguyên đường tiền/idempotency hiện hành.

### 11f. RFI changed-set và exact deep-link (D-83)

Dưới case lock, ingestion so sorted unique normalized `missing_fields` mới với set đã lưu. Chỉ
receipt `accepted`, event không phải cancel, set mới nonempty và khác set trước mới trả một
`rfi_candidate` nội bộ. Duplicate, stale, equal-version, set không đổi, complete và cancel không có
candidate. Candidate không nằm trong receipt public và chỉ được API schedule sau khi transaction
đã commit; rollback không schedule.

RFI v1 dùng generic webhook best-effort và body có **đúng hai key**:

```json
{
  "missing_fields": ["identity_document"],
  "deep_link": "https://app.example/?tab=cases&case=1ac7e141-1780-4e09-9cef-b165cb7a0c8b"
}
```

URL luôn ở root và query đúng `tab=cases&case=<external_case_links.id>`. Body không có event kind,
amount, tên, external id/party, CIC, document ref/content hay inbox payload. Mỗi changed set chỉ
schedule một lần ở app; retry transport có thể tạo bản tin trùng và crash-window sau commit có thể
làm mất chuông. S23 không thêm outbox, notification table hay claim exactly-once.

## 12. Consent pre-pilot tại cửa form khách (S20 · D-80)

Đây là proof kỹ thuật versioned, **không phải DPIA, đánh giá chuyển dữ liệu hay bằng chứng tuân thủ
đầy đủ**. Wording canonical nằm ở `configs/consent/pre-pilot.vi.md`; server parse metadata và tính
SHA-256 trên đúng bytes UTF-8 của phần `content_markdown` được snapshot vào card. Đổi một byte nội
dung phải bump version qua PR/maker-checker và tạo checksum mới; row cũ không bị viết lại.

`present_form` tiếp tục không nhận argument từ model và snapshot vào `card.data`:

```ts
interface ConsentSnapshot {
  required: true;
  purpose: 'pre_pilot_shadow_preassessment';
  wording_version: 'v1';
  wording_checksum: string; // lowercase SHA-256, 64 hex
  content_markdown: string;
}
// Card form hiện hữu được bổ sung: { ..., consent: ConsentSnapshot }
```

Client phải render nguyên snapshot, checkbox riêng mặc định `false`, và chỉ được gửi trạng thái
đồng ý. Request form mới:

```ts
interface FormSubmitBody {
  card_id: string;
  values: Record<string, unknown>;
  consent_granted: true;
}
```

Body không có field version/checksum/tenant/subject/actor. Extra field bị schema từ chối. Server lấy
tenant, actor và `subject_ref` từ claims; metadata proof chỉ lấy từ card server-owned rồi đối chiếu
lại wording canonical. Thiếu/`false` trả `400 consent_required`; snapshot malformed hoặc không khớp
canonical trả `400 consent_wording_invalid`; card form legacy không có snapshot trả
`409 consent_wording_unavailable`. Mọi error dùng đúng envelope 4-field §0 và không tạo partial row.
Endpoint form-submit chỉ dành cho role `customer`: thiếu phiên trả `401`; `user`/`admin` trả `403`
trước khi đọc hoặc ghi form. `subject_ref` và `actor` đều là nguyên văn claim `sub` phía server.

Khi hợp lệ, một transaction duy nhất thực hiện card `pending→submitted`, tạo `customers`, link
`users.owner_id` và append đúng một `consent_records` với:

```ts
{
  tenant_id: '<JWT tenant>',
  subject_type: 'user',
  subject_ref: '<JWT sub>',
  purpose: 'pre_pilot_shadow_preassessment',
  wording_version: 'v1',
  wording_checksum: '<snapshot SHA-256>',
  granted: true,
  recorded_at: '<server UTC>',
  granted_at: '<server UTC>',
  actor: '<JWT sub>',
  source: 'customer_form',
  source_ref: '<card_id>'
}
```

`consent_records` là append-only ở cả app và DB: direct `UPDATE`/`DELETE` bị trigger từ chối;
unique `(tenant_id, source, source_ref, purpose)` chặn double-submit. `source_ref` là proof link
dạng text, không FK cascade về card. Wake MAIN chỉ chạy sau commit. V1 chỉ ghi grant; rút lại sau
này phải là event row mới, không update row lịch sử.

Consent LOS/SAHA thuộc trách nhiệm hệ nguồn; event envelope §11b không đổi và không chứng minh nguồn
đã thu consent. Trước pilot dữ liệu thật bắt buộc có bank data-protection/legal owner ký wording,
xác nhận controller/contact, purpose, data/source/recipient, retention+xóa, withdrawal và cloud/
chuyển dữ liệu; đồng thời hoàn tất DPIA cùng đánh giá chuyển dữ liệu áp dụng. Cho tới đó kết luận là
**PILOT NO-GO**.

## 13. Taxonomy, tờ trình và liên kết đúng hồ sơ (S23 · D-82/D-83)

### 13a. Reason-code taxonomy và write-time gate

Artifact canonical `configs/reason-codes.yaml` có đúng root `{version, codes}`. V1 dùng
`version: 1`; mỗi phần tử `codes` có đúng `{id, group, description}`. `group` chỉ thuộc
`HS_THIEU | CIC | THU_NHAP | PHAP_LY | TSDB`; `id` là uppercase snake-case, bắt đầu bằng đúng
`<group>_`, duy nhất toàn file. Mã `HS_THIEU_DINH_DANH_NOI_BO` là bắt buộc.

Loader fail-closed nếu root/entry thừa hoặc thiếu field, version/group/id sai, description rỗng,
id trùng hay thiếu mã bắt buộc. Sau khi parse, server sort codes theo `id`, serialize canonical JSON
UTF-8 bằng sorted keys và separator compact, rồi công bố checksum `sha256:<64 lowercase hex>`.
Khoảng trắng/comment/thứ tự YAML không làm đổi checksum. Taxonomy phải load thành công ở startup
sau runtime-security nhưng trước cleanup/boot, đồng thời được render vào prompt MAIN ở runtime.

`present(type='document', title='Pre-assessment credit memo')` có write-time gate trước DB/SSE. `items` phải
có đúng sáu mục theo đúng thứ tự canonical ở `backend/prompts/main/credit_memo.json`; mỗi mục có
`section`, `content`, `source` là string khác rỗng. Riêng mục 5 có thêm `reason_codes`: mảng
nonempty các id duy nhất, tất cả thuộc taxonomy đang chạy. Client/model không sở hữu proof:
server luôn overwrite/inject vào mục 5:

```ts
reason_taxonomy: {
  version: 1;
  checksum: `sha256:${string}`;
}
```

Vi phạm trả tool result lỗi 4-field `invalid_credit_memo`, `retryable:true`; không ghi card và
không phát SSE. Gate không áp dụng cho document có title khác hoặc card type khác.

### 13b. Counter-offer v1 trong mục khuyến nghị

Mục 5 được có tối đa một `counter_offer` object (không dùng array), song song với `content` để
người đọc hiểu được. Shape v1:

```ts
interface CounterOfferV1 {
  product_id: string;
  product_name: string;
  proposed_amount_vnd: number;
  loan_type: string;
  rationale: string;
  terms: Array<{
    field: 'rate_annual' | 'term_max_months' | 'amount_min_vnd' | 'amount_max_vnd' | 'fee_pct';
    value: number;
    source: 'product_suggest';
  }>;
  proof: {
    product_tool: 'product_suggest';
    reassessment_tool: 'credit_assess';
    wiki_citations: string[];
  };
}
```

Offer chỉ hợp lệ khi audit của chính conversation có `product_suggest` tại đúng
`proposed_amount_vnd`/`loan_type` trả product đó trong `eligibleOptions`, và `credit_assess` chạy
lại cùng owner/amount/type trả `verdict:'eligible'`. `wiki_citations` phải gồm tài liệu product
đang `status: active` cho mô tả và tài liệu quyết định đang active cho hiệu lực. Mọi numeric term
phải map đúng field của eligible option từ `product_suggest`; wiki không phải nguồn số. Thiếu một
trong ba proof thì không được sinh offer; checker đọc fresh card cùng `tool_calls` theo conversation,
không chấm response markdown.

### 13c. Exact-case API và URL

`GET /api/cases/{id}` nhận UUID và chỉ dành cho admin. Success trả resource `CaseSummary` trần như
§11c. Không có phiên trả `401`; RM/customer trả `403`; id không tồn tại hoặc thuộc tenant khác đều
trả `404` để không lộ sự tồn tại.

Public URL duy nhất để mở đúng hồ sơ là `/?tab=cases&case=<uuid>`. Parser chỉ nhận pathname `/`,
không hash, đúng hai key `tab` và `case`, mỗi key xuất hiện đúng một lần, `tab=cases` và case UUID
hợp lệ; param thừa/lặp/malformed là URL thường và không exact-fetch. URL hợp lệ được giữ nguyên qua
login. Sau khi xác thực, chỉ admin mount Tower ở tab `assessments`, gọi exact endpoint rồi merge
theo `CaseSummary.id`, chọn và highlight row kể cả target không nằm trong list 50 ban đầu. Lỗi exact
không phá danh sách tải độc lập. RM/customer không mount Tower và không gọi list/exact-case API.
Deep-link approval `/?tab=approvals&approval=<uuid>` giữ nguyên.
