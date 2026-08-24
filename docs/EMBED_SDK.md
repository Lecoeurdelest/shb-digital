# Embed SDK — tích hợp lõi vào SAHA, website, portal RM và LOS

> S21 · D-74. Nguồn contract máy-đọc: [`CONTRACT.md` §9](CONTRACT.md#9-headless-readiness--embed-sdk-boundary-s21--d-74).
> SPA trong `frontend/src/` là **reference host** và Control Tower, không phải dependency của SDK.

## 1. Ba cách dùng, một lõi

| Host | Entry | Dùng khi |
|---|---|---|
| BFF/service hoặc app tự render | `@bank-digital/embed-sdk` | chỉ cần REST + SSE headless, không React/DOM |
| SAHA/portal/LOS viết React | `@bank-digital/embed-sdk/react` | host muốn compose chat/canvas theo design system riêng |
| Trang không dùng React | `@bank-digital/embed-sdk/standalone.js` hoặc IIFE/Web Component | cần thẻ HTML cô lập CSS, cài nhanh |

Package không chứa Control Tower, approval action, mock backend, sidebar toàn hệ, lobby 3D,
Three.js hay dashboard. Phê duyệt vẫn chỉ ở Tower sau auth ngân hàng (D-71).

## 2. Mô hình mạng và auth

### Khuyến nghị: cùng origin qua reverse proxy ngân hàng

```text
SAHA / LOS origin
  ├── tải SDK/widget tĩnh
  └── /api/* ──reverse proxy nội bộ──> FastAPI headless core
```

Host không truyền `apiBaseUrl` (mặc định rỗng), browser gửi httponly cookie tới `/api`. Đây là
đường ít cấu hình nhất, không cần CORS và giữ data trong miền do ngân hàng sở hữu.

### Khác origin: allowlist + Bearer

Backend chỉ mở đúng origin đã khai:

```dotenv
SHB_CORS_ORIGINS=https://saha.bank.example,https://los.bank.example
```

Host cấp token qua callback; callback có thể refresh token và được gọi lại ở từng request:

```ts
import { createBankDigitalClient } from '@bank-digital/embed-sdk'

const client = createBankDigitalClient({
  apiBaseUrl: 'https://agent-api.bank.example',
  getAccessToken: () => bankSso.getAccessToken(),
})
```

Không ghi token vào attribute Web Component, query string, log hoặc localStorage. SDK không lưu
token. Native `EventSource` không được dùng ở đây; fetch-SSE gắn cùng Authorization header với REST.

## 3. Nhận hồ sơ không cần SDK (D-77)

SDK giải quyết **bề mặt làm việc** sau khi đã có một hồ sơ; nó không phải đường đưa hồ sơ vào hệ
thống. LOS/SAHA/CRM không dùng React, Web Component hay chat để tạo hồ sơ. Thay vào đó, BFF/API
Gateway trong DC gọi cổng server-to-server:

```text
LOS / SAHA / CRM
  └── BFF hoặc API Gateway (mTLS/OIDC service identity)
        └── POST /api/integrations/v1/case-events
              └── inbox idempotent + case↔conversation mapping trong core
```

Envelope, receipt, quyền và config source nằm ở [`CONTRACT.md` §11](CONTRACT.md#11-case-intake-và-bàn-làm-việc-sơ-thẩm-d-77).
Transport broker, pull/read-through hay batch legacy về sau cũng gọi cùng ingestion service; không
được ghi trực tiếp `conversations` hoặc suy mapping từ title. `SHB_LOS_CASE_INTAKE_API_KEY` (hoặc
credential tương đương do gateway kiểm) chỉ ở secret manager/env, không bao giờ nằm trong host
JavaScript, SDK hoặc UI.

Đây là đường tích hợp phù hợp khi host **không muốn dùng SDK**: host tự render màn LOS của mình và
chỉ lấy `CaseSummary`/`conversation_id` do core trả. SDK chỉ cần thiết nếu host muốn nhúng copilot
chat/canvas vào đúng case đó.

## 4. Headless client

```ts
// conversationId do CaseEventReceipt/CaseSummary của core cấp; host không tự suy từ title.
const conversationId = caseSummary.conversation_id
if (!conversationId) throw new Error('Hồ sơ chưa được mở phiên xử lý')

const stream = client.openConversationStream(conversationId, {
  onOpen: async () => render(await client.getConversation(conversationId)),
  onEvent: (event) => applyEnvelope(event),
  onStateChange: ({ state, retryInMs }) => showConnectionState(state, retryInMs),
  onError: (error) => reportNonSensitiveError(error),
})

await client.sendMessage(conversationId, 'Chuẩn bị tờ trình sơ thẩm hồ sơ này')

// Khi host đóng tab/đổi hồ sơ:
stream.close()
```

Core giữ mapping có audit giữa application/case của LOS và `conversation.id`. Host chỉ giữ reference
trả về để điều hướng; không tự tạo mapping song song. Mỗi reconnect phải đọc lại full-state; không
xây replay cursor riêng. `render`, `applyEnvelope`, `showConnectionState` và `reportNonSensitiveError`
trong ví dụ là callback của host, không phải export của package. React provider ở §5 đã tự làm bước
full-state/refetch này.

## 5. React: state được inject, UI được compose

```tsx
import {
  BankConversation,
  RmCopilot,
} from '@bank-digital/embed-sdk/react'

// Variant dựng sẵn, gọn cho portal RM.
<RmCopilot
  client={client}
  conversationId={conversation.id}
  heading="Trợ lý sơ thẩm"
/>

// Hoặc host compose đúng design system của mình.
<BankConversation.Provider client={client} conversationId={conversation.id}>
  <BankConversation.Frame variant="rm" styleNonce={window.bankCspNonce}>
    <BankConversation.Status />
    <BankConversation.Messages />
    <MyLosCaseSummary />
    <BankConversation.Cards />
    <BankConversation.Composer />
  </BankConversation.Frame>
</BankConversation.Provider>
```

Các phần UI chỉ đọc interface context `{state, actions, meta}`; provider là nơi duy nhất biết
transport/state implementation. Host có thể lấy `useBankConversation()` để dựng component riêng.

`CustomerAssistant` và `RmCopilot` là hai variant riêng, không phải một component với tổ hợp cờ
`isAdmin/showCanvas/allowApprove`. Cả hai đều không có action phê duyệt.

## 6. Web Component / host không dùng React

Cookie + reverse proxy cùng origin:

```html
<script src="/embed-sdk/dist/bank-digital-widget.iife.js"></script>
<bank-digital-rm-copilot
  conversation-id="018f..."
  heading="Trợ lý sơ thẩm"
  style-nonce="nonce-do-server-render"
></bank-digital-rm-copilot>
```

Đường dẫn artifact phụ thuộc cách host phát hành, không phải Vite tự sinh vào `/assets`:

| Môi trường | Widget | Reference host |
|---|---|---|
| Source repo sau `npm run sdk:build` từ `frontend/` | `frontend/sdk/dist/bank-digital-widget.iife.js` | `frontend/sdk/examples/standalone.html` |
| Vite dev, root `frontend/` | `/sdk/dist/bank-digital-widget.iife.js` | `/sdk/examples/standalone.html` |
| Docker/Nginx của repo | `/embed-sdk/dist/bank-digital-widget.iife.js` | `/embed-sdk/examples/standalone.html` |

Package consumer có thể side-effect import `@bank-digital/embed-sdk/standalone.js`, hoặc copy file
`dist/bank-digital-widget.iife.js` sang static path có version của kênh ngân hàng. Phải chạy
`npm run sdk:build` trước khi mở reference host qua Vite dev.

Tích hợp có Bearer dùng mount API thay vì attribute:

```ts
import { mountRmCopilot } from '@bank-digital/embed-sdk/element'

const mounted = mountRmCopilot(document.querySelector('#copilot')!, {
  client,
  conversationId: conversation.id,
  heading: 'Trợ lý sơ thẩm',
  styleNonce: window.bankCspNonce,
})

router.onLeave(() => mounted.unmount())
```

Widget dùng Shadow DOM. Theme qua CSS custom properties trên element/target, không yêu cầu copy
CSS của reference SPA. Host có CSP `style-src` theo nonce truyền `styleNonce` như trên (hoặc
attribute `style-nonce` cho declarative element):

```css
bank-digital-rm-copilot {
  --bank-digital-accent: #d97757;
  --bank-digital-surface: #ffffff;
  --bank-digital-text: #1a1917;
  --bank-digital-font: Inter, system-ui, sans-serif;
}
```

Declarative element chỉ phát custom event `bank-digital:event` nội bộ element với
`detail: {type}`. Host cần full SSE envelope dùng mount API và truyền `onEvent` tường minh; SDK
không broadcast card/CIC payload ra document.

## 7. Checklist tích hợp ngân hàng

- `/api/health` dùng cho liveness; `/api/ready` phải `200` trước khi nhận traffic.
- Đặt `SHB_RUNTIME_MODE=bank_dc`, không dùng compose/profile demo, khi yêu cầu data-residency.
- Reverse proxy phải tắt buffering cho `/api/conversations/*/sse` và giữ timeout dài.
- Auth/ownership vẫn do backend cưỡng chế; không tin `conversationId` do DOM cung cấp.
- Không đưa approval action vào SDK/BFF; deep-link về Control Tower.
- Không lưu access token; không gửi telemetry/credit data tới vendor frontend.
- Bật source intake bằng config GitOps/maker-checker; default `enabled:false`, rollout `off → shadow`
  trước khi chọn product/branch. Không có form hot-edit config trong Control Tower.
- Dedupe source event bằng `Idempotency-Key`, lấy `conversation_id` từ receipt/read-model, không từ
  title/chat/DOM. `shadow` không được gọi tool giải ngân hoặc tạo approval.
- Khi gắn core banking thật, adapter phải nhận idempotency key và core phải replay cùng receipt;
  adapter seed hiện tại không phải bằng chứng tích hợp core live.
- Từ `frontend/`, chạy `npm run sdk:build`, `npm run sdk:test`, `npm run sdk:smoke`; smoke cài và
  thực thi tarball đóng gói thật.

## 8. Ranh giới đã chứng minh và chưa được phép tuyên bố

| Nội dung | Trạng thái |
|---|---|
| Runtime MAIN/SUB, gate Postgres atomic, REST/SSE, role MCP in-process | Có code + test trong repo |
| SDK headless/React/Web Component | Package S21; build/test/smoke là gate phát hành |
| Case intake server-to-server | P0: inbox/link idempotent + case read-model; source default tắt, không tự quyết/giải ngân |
| CORS khác origin | Chỉ khi allowlist tường minh; mặc định đóng |
| Data không rời DC | Chỉ khi profile `bank_dc` readiness pass **và** network egress policy của ngân hàng pass |
| CIC/core thật | Chưa có endpoint/credential; hiện là tool contract + adapter seed |
| Exactly-once qua core HTTP ngoài DB | Chưa được chứng minh tới khi core hỗ trợ idempotency-key/receipt replay + crash-window test |
| Audit tool-call 100% / WORM | Chưa; trace thường hiện best-effort, approval/receipt có ledger transaction riêng |

Không dùng screenshot reference UI hoặc mock data làm bằng chứng cho bất kỳ dòng integration/runtime
nào ở bảng này.
