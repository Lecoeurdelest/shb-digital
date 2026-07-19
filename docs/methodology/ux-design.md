# AI-Native UX & Tư duy thiết kế

> BANK Digital — Digital Expert Guild · đề #132 · VAIC 2026.
> Khuôn mỗi mục: *định kiến → cơ chế thật → lựa chọn → trade-off khai thật.* Mọi claim dẫn tên
> component/file cụ thể — UX không phải mô tả suông, phải chỉ được vào code. FE ~3.100 LOC
> component (`frontend/src/components/`), tài liệu này là LẬP LUẬN đằng sau chúng.

## §0. Nguyên tắc gốc — TRUST là tính năng số 1

**Định kiến:** UX cho app AI = một ô chat + một cái spinner. Model thông minh thì giao diện chỉ
cần "chỗ gõ, chỗ đọc".

**Cơ chế thật:** người dùng KHÔNG tin thứ họ không nhìn thấy đang làm việc. Với ngân hàng, mỗi
con số dẫn tới một quyết định tiền thật — "AI bảo thế" không đủ; phải thấy *ai* tính, *bằng*
gì, và *ai* được phép bấm nút cuối. Spinner giấu quá trình → khách hồi hộp, cán bộ không dám
ký. Vậy nhiệm vụ số 1 của UX ở đây không phải đẹp, mà là **làm quá trình ra quyết định NHÌN
THẤY ĐƯỢC** — biến hộp đen thành hộp kính.

Bốn thứ phải hiển thị để tin: **ai đang làm** (§1) · **dựa vào nguồn nào** (§2) · **cái gì đang
bị chặn chờ người** (§3) · **ai có quyền quyết** (§4).

## §1. Nhìn-thấy-đội-làm-việc — thay spinner bằng sân khấu thật

**Vấn đề:** "đội 5 agent đang xử lý" mà chỉ hiện xoay vòng = vô hình, không tin được.

**Lựa chọn:** một chi nhánh ngân hàng 3D (`Lobby3D.tsx`, three.js) — 5 quầy: Main ở giữa phục
vụ khách, 4 chuyên gia hai bên (Tín dụng, Pháp chế, Sản phẩm, Vận hành). Agent `run` → icon
nhấp nháy trên đầu + beam giao việc sáng từ Main tới quầy đó (`applyState`, `beams`). Trạng thái
này KHÔNG phải trang trí — nó map thẳng từ task thật: `Canvas.tsx` `agentStatus()` đọc
`OrchTask.status` (`running`/`done`/`failed`) → màu quầy. Click một nhân vật → mở `SubAgentView`
đúng task của phòng ban đó.

Song song, dòng suy nghĩ + tool-call chảy realtime qua SSE (`useConversationSSE.ts`: event
`thinking` + `toolcall` → `TraceBlock`) thay cho spinner câm. Khách thấy "Tín dụng đang gọi
`calc_dscr`" — chờ CÓ NỘI DUNG, không phải chờ mù. Cùng scene được tái dùng làm hero Landing
(`landing/Landing.tsx`) — trang bán hàng chính là sản phẩm thật, không phải ảnh dựng.

## §2. Card-có-nguồn — thay wall-of-text bằng bằng chứng bấm được

**Vấn đề:** LLM trả một đoạn văn dài. Ngân hàng không ký trên đoạn văn — cần con số + nguồn +
đạt/không đạt.

**Lựa chọn:** đội trình kết quả bằng CARD có cấu trúc, không bằng markdown thô. `CardRenderer.tsx`
switch theo `card.type` → 7 loại (metric, checklist, options, timeline, case_file, document,
approval, form). Bảng chỉ số (`MetricBody`) có cột **Ngưỡng** riêng, badge **✓ Đạt / ✗ Không
đạt**, và cột **Nguồn** = `CitationChip` — mỗi con số đính chip tên tool đã tính ra nó
(`calc_dscr`, `check_cic`…). Bấm chip → banner nguồn (`Canvas.tsx` `onCite`). "Mọi con số có
nguồn" là nguyên tắc demo, cưỡng chế bằng UI: số không có `source` thì không có chip, người xem
thấy ngay chỗ nào là suy luận, chỗ nào là dữ liệu.

## §3. Phanh HIỂN THỊ cho khách — chờ có lý do dễ chấp nhận hơn chờ vô cớ

**Vấn đề:** hành động nhạy cảm (giải ngân) phải chờ người duyệt. Cách dễ là giấu — khách chỉ
thấy "đang xử lý". Nhưng chờ mù sinh nghi ngờ.

**Lựa chọn:** phanh được HIỂN THỊ CÔNG KHAI cho khách. `ApprovalPanel.tsx`: khi phiếu `pending`
và `canDecide=false` (khách), render đúng dòng **"⏳ Đang chờ ngân hàng phê duyệt"** — không có
nút, không giả vờ đang chạy. Khách biết chính xác *đang chờ cái gì* và *ai sẽ quyết*. Chờ có lý
do dễ chịu hơn chờ vô cớ. Phiếu quyết xong KHÔNG xoá card (bằng chứng §6) — chuyển badge sang
✓ ĐÃ DUYỆT / ✗ TỪ CHỐI kèm người quyết + lý do (`decidedText`), để lại vết trên màn hình.

## §4. Hai persona, một app — quyền ở JWT role, không ở UI ẩn/hiện

**Vấn đề:** khách và cán bộ ngân hàng cần hai trải nghiệm khác hẳn. Cám dỗ: một UI, ẩn/hiện nút
theo vai — nhưng "ẩn nút" không phải bảo mật.

**Lựa chọn:** hai cửa rõ ràng. **Cửa khách** (`Workspace.tsx`) chỉ thấy ca của mình
(`listConversations` scope theo cookie), có chuông thông báo, không có quyền quyết phiếu. **Bàn
ngân hàng** (`ControlTower.tsx`, admin) có 6 tab: Tổng quan · Hàng chờ duyệt · Hồ sơ + lý do AI
· Nhật ký tool · Trạng thái đội · So sánh 1-vs-đội. Quyền quyết đến từ `user.role==='admin'`
truyền xuống làm `canDecide` (`Workspace.tsx` → `Canvas` → `ApprovalPanel`) — và backend cũng
403 nếu khách cố gọi `decide`. UI phản ánh quyền, KHÔNG *là* quyền: nút ẩn chỉ là lịch sự, hàng
rào thật ở role JWT + tầng tool.

## §5. Form intake NGAY trong hội thoại — không nhảy sang trang khác

**Vấn đề:** khách mới cần nộp hồ sơ. Bắt rời hội thoại sang một form riêng = gãy mạch, mất ngữ
cảnh ca.

**Lựa chọn:** form là một loại CARD (`FormCard.tsx`, type `form`) hiện ngay trên canvas cạnh
cuộc trò chuyện. Fields do SERVER định nghĩa (`card.data.fields`), FE render đúng theo — không
hardcode, thêm trường = sửa server. Validate required client-side để báo sớm (server vẫn validate
lại), nộp xong → `status='submitted'` → card tự chuyển read-only "✅ Đã nộp". Giá trị đang gõ được
nâng lên `Workspace` theo `card.id` (`formDrafts`) để sống qua đổi tab canvas — gõ dở không mất.

## §6. Approval bắt LÝ DO khi từ chối — friction đặt đúng chỗ

**Vấn đề:** duyệt và từ chối không đối xứng. Từ chối mà không nói lý do = khách hụt hẫng, không
biết sửa gì.

**Lựa chọn:** **Duyệt = 1 click** (không thêm ma sát cho đường thuận). **Từ chối = 2 bước bắt
buộc lý do**: `ControlTower.tsx` `ApprovalQueue` — bấm "✗ Từ chối" mở ô textarea, nút xác nhận
`disabled` tới khi có lý do (`!rejectReason.trim()`); `ApprovalPanel.tsx` cũng chặn tương tự. Lý
do đi thẳng tới khách ("khách sẽ nhận được"). Friction cố ý đặt vào đúng hành động cần cân nhắc,
không rải đều.

## §7. Những chi tiết nhỏ mà cộng lại thành "đáng tin"

- **Theme sáng/tối** (`useTheme.ts` + `ThemeToggle`): mặc định LIGHT tường minh, set trước
  first-paint qua inline script (chống FOUC — nháy trắng khi load). Có mặt ở cả 3 màn.
- **Render defensive** (`CardRenderer` default branch, `cardUtil`): type card lạ → render THÔ,
  KHÔNG crash cả canvas. Field thiếu → bỏ qua; `timeline` đọc shape tự do rất khoan dung. Vỏ FE
  không bao giờ vỡ vì một card méo — trust nghĩa là không bao giờ hiện màn trắng.
- **Trạng thái error/loading tường minh**: mọi lỗi API hiện banner người-đọc-được
  (`Workspace` `handleError`, 401 → về login); ca `failed` hiện lý do thật từ `task.result.reason`
  ngay dưới badge phòng ban, không nuốt lỗi.
- **Render-on-demand 3D** (`Lobby3D`): scene TĨNH, chỉ vẽ lại khi trạng thái đổi; blink loop chỉ
  chạy khi có agent `run`. Không đốt GPU/pin khi đội đứng yên. Guard WebGL vắng (jsdom/máy yếu) →
  div rỗng, không nổ.
- **Chuông thông báo qua portal** (`NotificationBell`): dropdown render ra `document.body`
  position:fixed để thoát `overflow:hidden` của header (cần cho máy chiếu 1366) — sửa lỗi khách
  bấm chuông không thấy gì. Chi tiết vô hình khi đúng, chí mạng khi sai.
- **Ngôn ngữ người-thường**: bỏ jargon dev khỏi màn cán bộ ("per-turn/SDK/D-48" → "ước tính theo
  từng lượt trao đổi" — `ControlTower` `AgentStatus`); nhãn tiếng Anh trong card dịch ở tầng hiển
  thị (`METRIC_LABEL_MAP`).

## §8. Trade-off khai thật (không giấu)

- **Responsive còn mỏng — desktop-first CÓ CHỦ ĐÍCH.** Chỉ 8 file CSS có `@media`; layout tối ưu
  cho màn cán bộ/máy chiếu demo, chưa gọt kỹ mobile. Đúng scope: sản phẩm là bàn làm việc ngân
  hàng, không phải app điện thoại — nhưng đây là NỢ đã biết, không phải "đã xong".
- **Chưa có `prefers-reduced-motion`.** 3D nhấp nháy + beam + marquee Landing chạy bất kể cài đặt
  giảm-chuyển-động của hệ điều hành (`grep prefers-reduced-motion` = 0). Cần thêm cho a11y —
  chưa làm.
- **Theme KHÔNG theo `prefers-color-scheme`.** Cố định default light (`useTheme.ts`) theo quyết
  định người chốt; máy đặt dark-mode vẫn mở ra light. Chủ ý, nhưng là một lựa chọn đánh đổi
  (đồng nhất demo > tôn trọng cài đặt OS).
- **Citation chip chưa nối trace ĐẦY ĐỦ.** Bấm chip hiện banner tên tool (`Canvas` `onCite`);
  trace tool-call đầy đủ ở `TraceBlock`/`SubAgentView`/tab Nhật ký, nhưng đường từ *chip → đúng
  dòng trace đó* còn là banner tạm ("trace tool-call đầy đủ ở Sprint 4"), chưa deep-link.
- **FE mặc định MOCK để dev/test.** `USE_MOCK_API = VITE_USE_MOCK_API !== 'false'` — chạy chay là
  mock, có badge "● MOCK API" trên header (`Workspace`) để không ai nhầm dữ liệu thật. Prod phải
  ép `VITE_USE_MOCK_API=false`; badge chính là cái phanh chống-nhầm đó.
