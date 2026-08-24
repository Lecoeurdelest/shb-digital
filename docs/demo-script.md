# DEMO SCRIPT v10 — SYSTEM #132 “Pre-assessment + Middle-office Copilot” (thi Đà Nẵng) — HAI CỬA SỔ + 3 TRỤ (D-73)

> Tài khoản demo (KHÁCH-DN · KHÁCH-CN · ADMIN) đã gửi riêng BTC — repo không chứa credential.

> Kể 5 deliverable đề #132 trong 1 mạch chuyện ~10-13 phút, mở từ **bàn RM/underwriting của
> ngân hàng** theo D-73: hệ chuẩn bị tờ trình sơ thẩm, nguồn và cảnh báo; con người quyết định và
> ký. **Sân khấu = 2 cửa sổ Chrome cạnh nhau: PHẢI = bàn ngân hàng/RM (admin, vai chính) · TRÁI =
> cửa khách (b001, demo/sandbox hỗ trợ).** Cửa khách chứng minh intake, read-scope và vòng đời,
> không phải persona sản phẩm chính. Cả 2 cửa sổ phải VISIBLE (badge poll dừng khi tab ẩn — đừng
> minimize cửa sổ bank).
>
> Setup trước MỖI lần chạy: `cd backend && uv run python -m app.db.reset_demo` (users KHÔNG bị
> wipe — seed_users riêng) + server `uv run uvicorn app.main:app --port 8000` với
> **`DEV_SKIP_AUTH=0`** (BẮT BUỘC — demo persona cần login thật; khác script cũ).
> Standalone không CLI-auth: `SHB_PROVIDER=zai`. Account: **[KHÁCH-DN b001]** (khách DN — Cty TNHH
> Cơ khí Xưởng X, B001) · **[KHÁCH-CN c001]** (khách cá nhân — Nguyễn Văn An, C001) · **[ADMIN]**
> (ngân hàng).

## Mạch chuyện: “RM nhận hồ sơ phức tạp — máy chuẩn bị, người ký”

### CẢNH 1 — Bàn RM lập tờ trình với ĐỘI CHUYÊN GIA (deliverable #1 + #2) — ~3 phút

- Cửa sổ PHẢI: login **[ADMIN]** → Workspace → “+ Ca mới”. Giới thiệu: “Đây là bàn
  RM/underwriting; khách hàng không ngồi điều khiển quyết định tín dụng.”
- Gõ: **“Tôi là RM đang lập tờ trình sơ thẩm hồ sơ doanh nghiệp B001 vay 5 tỷ MỞ RỘNG SẢN
  XUẤT, thế chấp nhà xưởng COL06. Hãy phối hợp kiểm tra sức khoẻ tín dụng, pháp lý tài sản và gói
  vay; nêu nguồn, cảnh báo và đề xuất để tôi rà soát.”**
- CHỈ lobby 3D: các chuyên gia SÁNG ĐÈN — “MAIN tự phân rã và bàn giao việc” (#2). Mở khối
  “Diễn tiến đội” (F1): 🧠 suy nghĩ + 🔧 tool call sống; click một sub để xem brief/trace/kết quả.
- ~60–90s: canvas có card CÓ NGUỒN (DSCR, pháp lý, gói vay) và tờ trình sơ thẩm. Chỉ chip nguồn:
  “máy chuẩn bị và dẫn căn cứ; RM kiểm tra, sửa nếu cần rồi trình ký.”
- Nhịp phụ 20s ở cửa sổ TRÁI: login **[KHÁCH-DN b001]**. Chỉ ra khách không thấy Control Tower,
  không có nút duyệt và chỉ thấy hồ sơ của mình: “cửa này là demo/sandbox chứng minh intake và
  phân tách dữ liệu; persona chính vẫn là bàn RM vừa xem.”
- *Thoát hiểm: MAIN chọn tuần-tự thay song-song → kể “nó đang đi đúng quy trình tín dụng và bàn
  giao thật giữa phòng ban” (D-52); cả hai đường đều chứng minh orchestration.*

### CẢNH 2 — PHANH TẦNG TOOL + BÀN PHÊ DUYỆT 2 CỬA SỔ (deliverable #3) — ~3 phút

> **Cách kể theo D-73:** các nhánh `auto-rule` dưới đây được giữ để chứng minh ma trận thẩm quyền,
> fail-closed và regression của phanh hiện có; chúng không phải lời chào bán máy tự quyết khoản
> vay nhỏ. Pilot đặt ngưỡng `0`: mọi hồ sơ về người, hệ chỉ đưa khuyến nghị có nguồn.

**Chuẩn bị:** cửa sổ PHẢI đã login **[ADMIN]**, để ở Workspace (thấy nút 🗼 Control Tower).
**Nhịp A — khoản nhỏ, ma trận cho tự duyệt (⚠️ v9 sửa theo SEED THẬT + Fix-A cross-owner:
khách CHỈ giải ngân được loan CỦA MÌNH — L006 là của C003, b001 gõ sẽ bị từ chối đúng luật!):**
- TRÁI: login **[KHÁCH-CN c001]** → gõ: **"Giải ngân khoản vay L001 số tiền 340 triệu."** (L001 CỦA
  C001, 340tr < 500tr) → ~15-45s: card **"✅ Tự động duyệt & thực thi"** + biên nhận LUÔN —
  “đây là nhánh tương thích demo của ma trận. NHÌN: phiếu vẫn ghi `decided_by='auto-rule'` +
  lý do — cơ chế kỹ thuật có kiểm soát và audit đủ; cấu hình pilot D-73 sẽ đóng nhánh này về người.”
**Nhịp B — khoản lớn: phiếu BAY sang ngân hàng:**
- TRÁI: login lại **[KHÁCH-DN b001]** → gõ: **"Giải ngân khoản vay L007 số tiền 3 tỷ đồng."** (L007
  CỦA B001, dư nợ 3 tỷ — v9 sửa: script cũ ghi "1 tỷ" lệch seed) → ~5-10s: card
  **"⏳ Đang chờ ngân hàng phê duyệt"** — KHÔNG có nút duyệt phía khách. "Vượt ngưỡng → agent bị
  CHẶN ở tầng tool. Khách không tự duyệt được, dụ agent cũng không mở được — luật nằm ở cái két."
- CHỈ TAY sang cửa sổ PHẢI: **badge đỏ nổi trên nút Control Tower** (poll ≤5s) — "phiếu vừa BAY
  từ cửa khách sang bàn ngân hàng, không ai bấm gì". Mở Tower → "Hàng chờ phê duyệt (1)".
- PHẢI: bấm **✓ Duyệt** (mời giám khảo bấm nếu hợp không khí — "anh/chị đang là giám đốc chi
  nhánh") → queue về 0.
- CHỈ TAY về TRÁI: ~25-30s MAIN tự trả **"✅ Giải ngân thành công, anh..."** + biên nhận —
  "resume tự động, đúng MỘT lần; gọi lại chỉ trả biên nhận cũ."
**Nhịp C — HỒ SƠ XANH: pháp lý 3 TRỤ chấm xanh → agent tự duyệt CẢ KHOẢN TRÊN NGƯỠNG (S7 —
pain người ra đề):**
- TRÁI: login **[KHÁCH-CN c019]** (khách cá nhân lịch sử sạch). Gõ: **"Tôi muốn vay 594 triệu MUA
  NHÀ Ở, vay tín chấp không thế chấp — thẩm định hồ sơ giúp tôi theo quy trình."**
  (⚠️ PHẢI đủ: mục đích MUA NHÀ Ở — `residential_purchase` not_restricted → green; nói
  "mở rộng kinh doanh" là dính `business_expansion` conditional → YELLOW → mất cảnh tự duyệt.
  Rehearsal 18/7 vấp đúng chỗ này. + "tín chấp" để Legal khỏi dừng hỏi loại vay/tài sản.)
- CHỈ khối Diễn tiến: Pháp chế chạy **3 TRỤ THẬT** — 🔧 `legal_check_police` (nhân thân + tiền
  án cổng Bộ Công an) → CIC → `legal_verify_employment` (lương xác minh vs kê khai) →
  `legal_classify_profile` **GHI BIÊN BẢN vào sổ thẩm định** — "server chấm lane, agent không
  được tự phán xanh/đỏ."
- Kết quả: **hồ sơ XANH**. Gõ tiếp: **"Giải ngân khoản vay L108 số tiền 594 triệu."** — *594tr
  VƯỢT ngưỡng 500tr* → nhưng ~15s: **✅ TỰ ĐỘNG DUYỆT** — phiếu `auto-rule`, reason **"Hồ sơ
  XANH — assessment #N"**. → *"Ma trận thẩm quyền 3 tầng: khoản nhỏ tự chạy · khoản vừa CHỈ tự
  chạy khi 3 nguồn chấm XANH — có số biên bản truy được · khoản lớn và hồ sơ chưa xanh (DN 3 tỷ
  vừa nãy) vẫn qua người. Đây là bằng chứng engine tôn trọng ma trận, không phải định vị sản phẩm;
  trong pilot shadow, RM vẫn xem khuyến nghị và ký.”*
- *Tương phản kể miệng: khách C001 tra công an CHƯA CÓ bản ghi → hệ nói "chưa xác minh được",
  KHÔNG đoán sạch/bẩn → bắt buộc người xem. Agent trung thực với dữ liệu thiếu.*

### CẢNH 2B — CỬA KHÁCH DEMO/SANDBOX: khách mới + mail (D-57, cảnh hỗ trợ) — đo thật ~11'
TRỌN vòng (register 2'52 + form 3'54 + thẩm định 4'21) — **DEMO MẶC ĐỊNH: warm-up account +
form trước giờ G, trên sân khấu kể từ bước THẨM ĐỊNH (~4') hoặc chỉ nhịp duyệt→mail (~2')**.
- TRÁI: Đăng xuất → tab **"Đăng ký khách mới"** → tạo account NGAY TRÊN SÂN KHẤU (username tự
  đặt, **email = Gmail demo đang mở trên điện thoại**) → vào thẳng Workspace "Khách hàng".
  "Người ngoài đường tải app là dùng được — không cần là khách có sẵn hồ sơ."
- Gõ: **"Tôi muốn vay 300 triệu mua nhà."** → MAIN KHÔNG hỏi vặt — **card FORM hiện trên
  canvas** (6 trường do server định nghĩa) → điền trực tiếp → Nộp → "✅ Đã nộp" → hệ TỰ tạo hồ
  sơ (mã C9xx) + MAIN tiếp tục thẩm định.
- Thẩm định ra **VÀNG — "chưa xác minh được nhân thân/thu nhập"** (khách mới chưa có bản ghi
  công an/CIC/lương): "hệ TRUNG THỰC với dữ liệu thiếu — không đoán sạch/bẩn, đẩy về con người.
  Đó là cách ngân hàng thật xử khách lạ."
- PHẢI (bank): duyệt phiếu → **📱 GIƠ ĐIỆN THOẠI: mail "BANK Digital" màu cam ting về hộp thư
  khách** (HTML brand: số tiền, ai duyệt, mã biên bản — 2 mail: phê duyệt + giải ngân, đã verify
  Gmail thật 18/7) — "khách không ngồi trong app vẫn biết kết quả." + TRÁI: **chuông 🔔 badge
  nổi** trong app — lưới kép khi mất mạng. (Bell dropdown: verify bằng MẮT lúc rehearsal —
  screenshot tool không chụp được layer này, đã biết.)
- ⚠️ Server chạy tay (không compose): PHẢI export SMTP env từ .env trước khi start — quên là
  mail no-op im lặng. Compose (S10) tự lo qua env_file.

### CẢNH 3 — Control Tower: đài GIÁM SÁT của ngân hàng (deliverable #4) — ~90s (cửa sổ PHẢI)
- "Khách không bao giờ thấy màn này — đây là phía ngân hàng."
- **Nhật ký tool**: filter theo ca vừa chạy — TỪNG tool call input/output theo thời gian,
  append-only — "truy vết 100% hành vi agent, kể cả 2 phiếu vừa nãy (1 auto-rule, 1 admin)."
- **Thống kê**: KPI ngày + trạng thái đội + hồ sơ thẩm định. **Hàng chờ duyệt**: giờ trống — vì vừa xử hết.

### CẢNH 4 — 1 LLM vs CẢ ĐỘI (deliverable #5) — ~90s (PHẢI, tab So sánh)
- Gõ "Khách C001 vay 500 triệu được không?" → Chạy. Trong lúc chờ (~70s): kể kiến trúc
  (1 Postgres, SDK session bền, event-wake, SSE, 2 persona 1 app).
- 2 cột: 1 LLM trần ("không tra được hồ sơ", 0 tool) vs CẢ ĐỘI (DSCR + nguồn, 6 tool).
  "Multi-agent không phải để nhanh hơn — để TIN được."

### CẢNH 5 — Chạy trên BẤT KỲ model nào (bonus) — ~30s (TRÁI)
- "+ Ca mới" → picker cạnh nút gửi: chọn zai/GLM (hoặc wrap/GPT) → 1 câu ngắn → chạy thật.
  "Cùng bộ máy — trí khôn nằm ở tool + kỷ luật hệ thống, không khoá vào 1 nhà model."

## Câu chốt
“Đây là copilot sơ thẩm và vận hành middle office cho hồ sơ phức tạp: đội chuyên gia chuẩn bị tờ
trình, nguồn và cảnh báo; con người ngân hàng giữ quyền quyết định và ký. Năm deliverable đề #132
chạy live; cửa khách chỉ là demo/sandbox của vòng đời end-to-end.”

## Sự cố & thoát hiểm
| Sự cố | Thoát |
|---|---|
| Badge không nổi cửa sổ PHẢI | Cửa sổ bank phải VISIBLE (poll dừng khi tab ẩn). Kéo lên foreground / bấm thẳng vào Tower — queue vẫn đúng |
| Sub chậm >90s | kể kiến trúc; trace F1 cho thấy nó ĐANG làm |
| Model từ chối/lạc đề | ca mới chạy lại (reset_demo đảm bảo lặp được) |
| Main chọn tuần-tự thay song-song (hoặc ngược) | CẢ HAI đều điểm cộng — kể theo đường nó chọn |
| Legal dừng hỏi lại | "Agent không đoán bừa — nó đối chiếu hồ sơ và hỏi. Đây là kiểm soát rủi ro." → trả lời rồi tiếp |
| Lúng túng 2 cửa sổ | FALLBACK: đóng cửa sổ khách, làm hết trên 1 cửa sổ admin (admin thấy mọi ca + duyệt tại card — flow v4 cũ vẫn nguyên) |
| Login lỗi/quên pass | dùng tài khoản demo đã gửi BTC (KHÁCH-DN · KHÁCH-CN · ADMIN) — không đăng trong repo |
| Compare timeout | cột single vẫn hiện — kể "single không đủ" luôn |
| Mất mạng provider | đổi SHB_PROVIDER (claude-cli/zai dự phòng) |
| DB bẩn giữa buổi | reset_demo 1 lệnh (~5s) — users giữ nguyên |

## Timing (C1 cũ/C2 đo rehearsal 18/7 · mở bàn RM D-73 cần đo lại · C3-C5 kế thừa v4) — mục tiêu ≤13ph
C1 cũ **2'10" tham chiếu** · C2 nhịp A **43" đo thật** (model latency — đừng hứa "15 giây", nói
"chưa tới 1 phút") + nhịp B **~3' đo thật** (gồm đổi vai thủ công 1-browser; 2 cửa sổ song
song nhanh hơn) + nhịp C **~5' đo thật** (thẩm định 3 trụ ~3-4' với CÂU ĐÚNG mục-đích-mua-nhà
+ giải ngân xanh 1'15") · C3 ~1.5ph · C4 ~2.5ph · C5 ~1ph. TỔNG đầy đủ ~15' — mặc định demo
CẮT C5 (kể miệng 1 câu) để về ≤13'; bị giục thêm → C1 rút 1 câu, nhịp C kể từ bước giải ngân
(assessment seed sẵn từ vòng warm-up trước giờ G).

## Checklist trước giờ G
- [ ] `reset_demo` sạch · [ ] server :8000 `DEV_SKIP_AUTH=0` + health OK · [ ] .env đủ key
- [ ] login thử b001 + c019 + admin · [ ] 2 cửa sổ xếp cạnh nhau, CẢ HAI visible
- [ ] 1 vòng rehearsal trọn 2-cửa-sổ <13' (đo lại timing sau mở bàn RM theo D-73)
- [ ] browser zoom/máy chiếu OK (floor 1366×768)

> **Luật vận hành (giữ từ v4):** KHÔNG restart server / KHÔNG đụng DB / KHÔNG chạy pytest trên
> DB demo khi đang chạy ca. UI treo >60s không trace mới → F5 (SSE watchdog tự reconnect 25s —
> S6 — nên hiếm cần). Trước giờ-G: 1 vòng cuối LIỀN MẠCH không xen debug.
