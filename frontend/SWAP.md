# SWAP mock → backend thật (khi T1-3 xong)

> FE build S1 chạy trên MOCK API (in-memory, đúng shape `docs/CONTRACT.md` D-30). Khi backend
> T1-3 ship chat API + SSE thật, làm theo checklist này để ráp. Mục tiêu: **swap không đau** —
> UI/hook/types KHÔNG đổi, chỉ đổi 1 cờ env + verify contract khớp.

## 0. Điều kiện đủ để bắt đầu swap
Backend T1-3 đã cung cấp (bám CONTRACT.md §1/§2/§4):
- `GET /api/conversations` → `Conversation[]` (200)
- `POST /api/conversations` `{title}` → `Conversation` (201)
- `GET /api/conversations/{id}` → `ConversationFullState` (200 / 404)
- `POST /api/conversations/{id}/chat` `{content}` → **202** (ack, main stream qua SSE)
- `GET /api/conversations/{id}/sse` → text/event-stream, envelope 1 shape, `chat.delta` có **seq per-turn**
- (auth) `POST /api/auth/login` → `{token, user}` + JWT qua **cookie** (S1 có thể bypass)

## ✅ ĐÃ RÁP THẬT (2026-07-18) — auth seam đóng
Ráp mock→thật xong. Auth seam (architect cảnh báo) ĐÃ LỘ + ĐÓNG:
- **Finding**: routes `Depends(require_user)` → không cookie = 401 (confirmed bằng curl: no-cookie→401,
  with-cookie→200/201/202). FE T1-4 "bypass auth" → flip mock=false hit 401 như dự đoán.
- **Fix**: thêm LOGIN flow FE — `src/components/Login.tsx` (form user/pass) + `App.tsx` = auth gate
  (chưa login→Login, login→Workspace) + `Workspace.tsx` (tách từ App, nhận user + onAuthExpired 401→logout).
  `client.ts login()` POST /api/auth/login → server set cookie httponly `shb_token` → mọi call sau +
  EventSource `withCredentials` authenticated. `mock.login()` = accept mọi cred (mock không auth).
- **Verified API thật**: login (user/user) → Workspace → ca "Probe ca DSCR" full-state render **DSCR=3.709
  THẬT** + nguồn credit_assess + badge credit done (Chrome). SSE live: chat POST 202 → chat.delta seq
  per-turn + task.created credit + conversation.status, shape khớp CONTRACT (curl verify).
- **Deviation S1**: F5 reload mất user-state (cookie httponly FE không đọc được) → về Login. Chấp nhận
  S1; mở rộng = gọi /me lúc mount nếu backend thêm endpoint.

## 1. Bật API thật (1 dòng)
```bash
# frontend/.env  (hoặc export trước npm run dev)
VITE_USE_MOCK_API=false
```
- Cờ đọc ở `src/api/index.ts`: `USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API !== 'false'`.
  Mặc định (không set) = **mock BẬT**. Chỉ `=false` mới sang thật.
- Badge "● MOCK API" trên topbar (App.tsx) TỰ TẮT khi cờ false → dấu hiệu mắt-thường đã swap.
- Vite proxy `/api` → `http://localhost:8000` (vite.config.ts). Backend cổng khác → set
  `VITE_API_PROXY_TARGET=http://host:port`.

## 2. Điểm ráp — CHỈ 2 chỗ chạm backend, verify từng cái
`src/api/index.ts` → `realApi` gọi:
| Hàm | File | Endpoint | Verify |
|---|---|---|---|
| listConversations | client.ts | GET /api/conversations | trả mảng `Conversation` trần (không `{data}`) |
| createConversation | client.ts | POST /api/conversations | 201 + body `Conversation` |
| getConversation | client.ts | GET /api/conversations/{id} | full state {conversation, messages, tasks} |
| sendChat | client.ts | POST /api/conversations/{id}/chat | **202** (client `request` chấp nhận 2xx; body {} OK) |
| openEventSource | index.ts `browserEventSource` | GET /api/conversations/{id}/sse | wrap DOM EventSource → {data} |

- `client.ts request()` đã set `credentials:'include'` (cookie-JWT). Error = 4-field
  `{code,message,hint,retryable}` → bắt qua `ApiRequestError.body`.
- `browserEventSource` (index.ts): DOM `EventSource` → `MinimalEventSource`; chỉ chuyển `.data`
  (chuỗi JSON) + tín hiệu open/error. Hook `useConversationSSE` ăn y hệt mock.

## 3. Verify SSE thật (điểm dễ vỡ nhất — xem bài học `.claude/agent-memory/frontend/sse-seq-contract.md`)
1. **seq per-turn**: mở DevTools Network → SSE stream → xem frame `data:`. `chat.delta` PHẢI có
   `seq` tăng dần trong 1 turn (1,2,3…). Nếu `seq:null` → hook DROP hết → **answer biến mất
   im lặng** (không console error). Đây là gap #1 đã báo architect.
2. **done.full_text**: chunk cuối lượt có `{done:true, full_text:<toàn văn>}` → hook thay text
   ghép bằng full_text (van tự lành). Thiếu → bubble streaming treo.
3. **Header SSE** (backend, streaming-sse §4): `X-Accel-Buffering:no` + `Cache-Control:no-cache`
   + heartbeat 15s. Thiếu X-Accel sau nginx = SSE chết im. FE không sửa được — báo backend nếu SSE im.
4. **task.created/status + conversation.status**: bắn nguyên row, seq=null (không qua seq-gate) →
   badge + status cập nhật. Upsert theo id.
5. **Reconnect**: tắt mạng giữa lượt → mở lại → hook onopen refetch full state → text đúng nguyên
   văn (KHÔNG replay-cursor). Test: DevTools offline→online.

## 4. Verify end-to-end (Chrome — Gate 2)
Lặp lại gate T1-4 trên API THẬT:
- Tạo ca → gõ "Khách C001 xin vay 5 tỷ — DSCR?" → stream chữ Main + DSCR có nguồn + badge credit "✓ xong".
- Console sạch (0 error/warn). Multi-turn upsert theo id.
- `npm run test` vẫn xanh (test chạy trên mock — độc lập, không cần backend).

## 5. Nếu contract lệch
CONTRACT.md là 1 nguồn sự thật (D-30). Backend trả shape khác CONTRACT → **KHÔNG tự vá FE**;
báo architect patch CONTRACT.md TRƯỚC, cả 2 phía sửa theo. Grep điểm đổi: `src/types.ts`
(shape) · `src/api/client.ts` (endpoint/status) · `src/hooks/useConversationSSE.ts` (SSE parse).

## Nhánh FAILED — đã chốt (CONTRACT §4b) + mock đã harden theo
- **Gap 1 (a)**: MỌI kết lượt main bắn `chat.delta {done:true, full_text}` (kể cả lỗi) → FE đóng
  bubble không treo. Verify SSE thật: lượt fail PHẢI có done. Nếu backend fail mà thiếu done →
  bubble streaming treo → báo backend.
- **Gap 2**: lỗi SUB → `task.status {task}` status='failed' + `task.result.reason` (FE render dòng
  reason đỏ dưới bảng task). Lỗi MAIN → message `sender='system'` (meta.error) persist DB, FE
  lấy qua **full-state refetch khi conversation.status→failed** (App tự refetch). conversation.status
  data = {status} thôi.
- Test trigger mock (chỉ mock, backend thật lỗi thật): câu chứa "credit fail"/"timeout" → SUB fail;
  "lỗi main"/"quá tải"/"hết trần" → MAIN fail. Verify swap thật: các nhánh này backend tạo bằng
  lỗi thật (sub timeout, main hết retry), KHÔNG cần từ khoá.
