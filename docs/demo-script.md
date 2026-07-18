# DEMO SCRIPT v6 — SYSTEM #132 "Chi nhánh ngân hàng số" (thi Đà Nẵng) — HAI CỬA SỔ (D-56)

> Kể 5 deliverable đề #132 trong 1 mạch chuyện ~10-13 phút, THEO HƯỚNG D-56: app là CỬA KHÁCH
> HÀNG — khách tự chat với đội chuyên gia số, khoản nhỏ agent TỰ DUYỆT theo ma trận, khoản lớn
> bắn về NGÂN HÀNG duyệt. **Sân khấu = 2 cửa sổ Chrome cạnh nhau: TRÁI = khách (b001) ·
> PHẢI = ngân hàng (admin).** Cả 2 cửa sổ phải VISIBLE (badge poll dừng khi tab ẩn — đừng
> minimize cửa sổ bank).
>
> Setup trước MỖI lần chạy: `cd backend && uv run python -m app.db.reset_demo` (users KHÔNG bị
> wipe — seed_users riêng) + server `uv run uvicorn app.main:app --port 8000` với
> **`DEV_SKIP_AUTH=0`** (BẮT BUỘC — demo persona cần login thật; khác script cũ).
> Standalone không CLI-auth: `SHB_PROVIDER=zai`. Account: **b001/b001** (khách DN — Cty TNHH
> Cơ khí Xưởng X, B001) · **c001/c001** (khách cá nhân — Nguyễn Văn An, C001) · **admin/admin**
> (ngân hàng).

## Mạch chuyện: "Doanh nghiệp tự đến chi nhánh số — vay, được thẩm định, giải ngân"

### CẢNH 1 — Khách tự chat với ĐỘI CHUYÊN GIA (deliverable #1 + #2) — ~3 phút
- Cửa sổ TRÁI: login **b001/b001** → "b001 · Khách hàng". CHỈ RA: khách KHÔNG thấy Control
  Tower, không thấy nút duyệt — "đây là cửa khách, như app ngân hàng thật".
- ⚠️ Hệ TỰ BIẾT khách là ai (MAIN inject B001) — khách không cần khai mã. NHƯNG vẫn nêu
  MỤC ĐÍCH + TÀI SẢN (luật Pháp chế #3/#6 — thiếu là nó dừng hỏi, đúng nghề nhưng tốn nhịp).
- Gõ: **"Công ty tôi muốn vay 5 tỷ MỞ RỘNG SẢN XUẤT, thế chấp nhà xưởng (COL06) — khảo sát
  nhanh giúp tôi: sức khoẻ tín dụng, pháp lý hồ sơ thế chấp, gói vay phù hợp. Chưa phải hồ sơ
  chính thức."** ("khảo sát... chưa chính thức" = tín hiệu FAN-OUT.)
- CHỈ constellation: Main giữa, đường nối CHẢY XANH tới các sub SONG SONG — "điều phối viên tự
  phân rã việc" (#2). MAIN xưng "anh/chị" với khách — chỉ cho giám khảo thấy nó ĐANG nói
  chuyện với khách hàng, không phải nhân viên.
- Mở khối "Diễn tiến đội" (F1): 🧠 suy nghĩ + 🔧 tool call sống. Click 1 sub → SubAgentView.
- ~60-90s: canvas đầy card CÓ NGUỒN (DSCR, pháp lý, gói vay) — chip nguồn: "mọi con số truy
  được về tool".
- *Thoát hiểm: Main chọn tuần-tự thay song-song → kể luôn "nó đang đi đúng quy trình tín dụng
  — bàn giao thật giữa phòng ban" (D-52) — cả hai đường đều điểm cộng.*

### CẢNH 2 — PHANH PHÂN TẦNG 2 CỬA SỔ: khoản nhỏ TỰ DUYỆT, khoản lớn BAY về ngân hàng (deliverable #3 — CẢNH ĂN TIỀN) — ~3 phút
**Chuẩn bị:** cửa sổ PHẢI đã login **admin/admin**, để ở Workspace (thấy nút 🗼 Control Tower).
**Nhịp A — khoản nhỏ, ma trận cho tự duyệt:**
- TRÁI gõ: **"Giải ngân khoản vay L006 số tiền 300 triệu."** → ~15s: card **"✅ Tự động duyệt &
  thực thi"** + biên nhận LUÔN — "dưới ngưỡng 500 triệu, ma trận thẩm quyền cho agent tự duyệt.
  Nhưng NHÌN: phiếu vẫn ghi `decided_by='auto-rule'` + lý do — tự động CÓ KIỂM SOÁT, audit đủ."
**Nhịp B — khoản lớn: phiếu BAY sang ngân hàng:**
- TRÁI gõ: **"Giải ngân khoản vay L007 số tiền 1 tỷ đồng."** → ~5-10s: card
  **"⏳ Đang chờ ngân hàng phê duyệt"** — KHÔNG có nút duyệt phía khách. "Vượt ngưỡng → agent bị
  CHẶN ở tầng tool. Khách không tự duyệt được, dụ agent cũng không mở được — luật nằm ở cái két."
- CHỈ TAY sang cửa sổ PHẢI: **badge đỏ nổi trên nút Control Tower** (poll ≤5s) — "phiếu vừa BAY
  từ cửa khách sang bàn ngân hàng, không ai bấm gì". Mở Tower → "Hàng chờ phê duyệt (1)".
- PHẢI: bấm **✓ Duyệt** (mời giám khảo bấm nếu hợp không khí — "anh/chị đang là giám đốc chi
  nhánh") → queue về 0.
- CHỈ TAY về TRÁI: ~25-30s MAIN tự trả **"✅ Giải ngân thành công, anh..."** + biên nhận —
  "resume tự động, đúng MỘT lần; gọi lại chỉ trả biên nhận cũ." → *"Đây là pain nghiệp vụ thật:
  không chặn hết (chậm), không thả hết (rủi ro) — ma trận phân tầng nằm ở TẦNG TOOL, audit 100%."*

### CẢNH 3 — Control Tower: đài GIÁM SÁT của ngân hàng (deliverable #4) — ~90s (cửa sổ PHẢI)
- "Khách không bao giờ thấy màn này — đây là phía ngân hàng."
- **Nhật ký tool**: filter theo ca vừa chạy — TỪNG tool call input/output theo thời gian,
  append-only — "truy vết 100% hành vi agent, kể cả 2 phiếu vừa nãy (1 auto-rule, 1 admin)."
- **Thống kê**: trạng thái đội + cost meter per-ca. **Hàng chờ duyệt**: giờ trống — vì vừa xử hết.

### CẢNH 4 — 1 LLM vs CẢ ĐỘI (deliverable #5) — ~90s (PHẢI, tab So sánh)
- Gõ "Khách C001 vay 500 triệu được không?" → Chạy. Trong lúc chờ (~70s): kể kiến trúc
  (1 Postgres, SDK session bền, event-wake, SSE, 2 persona 1 app).
- 2 cột: 1 LLM trần ("không tra được hồ sơ", 0 tool) vs CẢ ĐỘI (DSCR + nguồn, 6 tool).
  "Multi-agent không phải để nhanh hơn — để TIN được."

### CẢNH 5 — Chạy trên BẤT KỲ model nào (bonus) — ~30s (TRÁI)
- "+ Ca mới" → picker cạnh nút gửi: chọn zai/GLM (hoặc wrap/GPT) → 1 câu ngắn → chạy thật.
  "Cùng bộ máy — trí khôn nằm ở tool + kỷ luật hệ thống, không khoá vào 1 nhà model."

## Câu chốt
"Khách tự đến chi nhánh số, đội chuyên gia AI phục vụ, khoản nhỏ tự quyết theo ma trận có audit,
khoản lớn con người ngân hàng giữ chìa — 5 deliverable chạy live, không video."

## Sự cố & thoát hiểm
| Sự cố | Thoát |
|---|---|
| Badge không nổi cửa sổ PHẢI | Cửa sổ bank phải VISIBLE (poll dừng khi tab ẩn). Kéo lên foreground / bấm thẳng vào Tower — queue vẫn đúng |
| Sub chậm >90s | kể kiến trúc; trace F1 cho thấy nó ĐANG làm |
| Model từ chối/lạc đề | ca mới chạy lại (reset_demo đảm bảo lặp được) |
| Main chọn tuần-tự thay song-song (hoặc ngược) | CẢ HAI đều điểm cộng — kể theo đường nó chọn |
| Legal dừng hỏi lại | "Agent không đoán bừa — nó đối chiếu hồ sơ và hỏi. Đây là kiểm soát rủi ro." → trả lời rồi tiếp |
| Lúng túng 2 cửa sổ | FALLBACK: đóng cửa sổ khách, làm hết trên 1 cửa sổ admin (admin thấy mọi ca + duyệt tại card — flow v4 cũ vẫn nguyên) |
| Login lỗi/quên pass | password = username (b001/b001, admin/admin) |
| Compare timeout | cột single vẫn hiện — kể "single không đủ" luôn |
| Mất mạng provider | đổi SHB_PROVIDER (claude-cli/zai dự phòng) |
| DB bẩn giữa buổi | reset_demo 1 lệnh (~5s) — users giữ nguyên |

## Timing (C1/C2 đo THẬT rehearsal 18/7 · C3-C5 kế thừa v4) — mục tiêu ≤13ph
C1 **2'10" đo thật** · C2 nhịp A **43" đo thật** (model latency — đừng hứa "15 giây" trên sân
khấu, nói "chưa tới 1 phút") + nhịp B **~3' đo thật** (gồm đổi vai thủ công 1-browser; 2 cửa sổ
song song thật sẽ nhanh hơn) · C3 ~1.5ph · C4 ~2.5ph · C5 ~1ph (+ đệm). Bị giục → cắt C5,
C1 rút còn 1 câu + kể miệng.

## Checklist trước giờ G
- [ ] `reset_demo` sạch · [ ] server :8000 `DEV_SKIP_AUTH=0` + health OK · [ ] .env đủ key
- [ ] login thử cả b001 + admin · [ ] 2 cửa sổ xếp cạnh nhau, CẢ HAI visible
- [ ] 1 vòng rehearsal trọn 2-cửa-sổ <13' (đo lại timing v6 — chưa đo THẬT sau D-56)
- [ ] browser zoom/máy chiếu OK (floor 1366×768)

> **Luật vận hành (giữ từ v4):** KHÔNG restart server / KHÔNG đụng DB / KHÔNG chạy pytest trên
> DB demo khi đang chạy ca. UI treo >60s không trace mới → F5 (SSE watchdog tự reconnect 25s —
> S6 — nên hiếm cần). Trước giờ-G: 1 vòng cuối LIỀN MẠCH không xen debug.
