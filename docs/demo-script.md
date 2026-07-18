# DEMO SCRIPT — SYSTEM #132 "Chi nhánh ngân hàng số" (thi Đà Nẵng)

> Kể 5 deliverable đề #132 trong 1 mạch chuyện ~8-10 phút. Timing đo THẬT trên :8000
> (18/7). Trước MỖI lần chạy: `cd backend && uv run python -m app.db.reset_demo` (DB sạch,
> 18 loans active) + server sống `DEV_SKIP_AUTH=1 uv run uvicorn app.main:app --port 8000`
> (KHÔNG --reload). Standalone không CLI-auth: thêm `SHB_PROVIDER=zai` (.env có key).

## Mạch chuyện: "Hồ sơ vay 5 tỷ của DN Gỗ Việt Phát — từ câu hỏi tới giải ngân"

### CẢNH 1 — Đội chuyên gia + luồng nghiệp vụ (deliverable #1 + #2) — ~2 phút
- Mở app → vào thẳng Workspace admin (skip-auth). GIỚI THIỆU 3 panel: sidebar ca | chat | canvas.
**Nhịp A — câu hỏi nhanh: đội fan-out SONG SONG:**
- Gõ: **"Khách hàng B001 (DN Gỗ Việt Phát) muốn vay 5 tỷ — kiểm tra tín dụng, pháp lý và gợi ý gói vay, đánh giá tổng thể."**
- CHỈ **constellation "Đội làm việc"**: Main giữa, đường nối CHẢY XANH tới từng sub đang chạy
  SONG SONG — "điều phối viên tự phân rã việc, không ai lập trình luồng cứng" (planner→executor, #2).
**Nhịp B (kể miệng hoặc demo nếu dư giờ) — hồ sơ VAY chính quy: TUẦN TỰ có BÀN GIAO (D-52):**
- "Với quy trình thẩm định chính quy, điều phối viên đi ĐÚNG nghiệp vụ: Tín dụng TRƯỚC → kết quả
  (DSCR, CIC, nợ) BÀN GIAO vào brief Pháp lý — pháp lý không kiểm mù → Vận hành tổng hợp cuối.
  Cùng bộ máy, luồng theo đúng quy trình tín dụng ngân hàng." (Demo: "xin vay 500tr thẩm định
  hồ sơ" → thấy credit chạy 1 mình → legal sau với ngữ cảnh.)
- **Khối "Diễn tiến đội"** (F1): mở ra — thấy 🧠 suy nghĩ thật + 🔧 từng tool call sống.
- Click 1 sub (Tín dụng) → **SubAgentView**: nhiệm vụ + tool đã gọi + kết quả. (Nút Huỷ: nói
  "có thể huỷ từng chuyên gia không đụng người khác" — KHÔNG bấm trong demo.)
- ~60-90s: main tổng hợp — canvas đầy card CÓ NGUỒN (DSCR từ credit_assess, pháp lý 4 card,
  gói vay). CHỈ chip nguồn trên card: "mọi con số đều truy được tool nào sinh ra".

### CẢNH 2 — PHANH PHÂN TẦNG: hồ sơ nhỏ tự chạy, vay lớn cần chìa giám đốc (deliverable #3) — ~90s
**Nhịp A — hồ sơ nhỏ (dưới ngưỡng 500tr) tự duyệt theo rule:**
- Gõ: **"Giải ngân khoản vay L006 số tiền 300 triệu."** → ~15s: card **"✅ Tự động duyệt & thực
  thi"** + biên nhận hiện LUÔN — "hồ sơ nhỏ, rule cho phép: agent tự duyệt — nhưng NHÌN audit:
  phiếu vẫn ghi decided_by='auto-rule' + lý do. Phanh không biến mất, chỉ tự động CÓ KIỂM SOÁT."
**Nhịp B — vay lớn: két khoá chờ người (tương phản):**
- Gõ: **"Giải ngân khoản vay L007 số tiền 1 tỷ đồng."** (trên ngưỡng)
- ~5-10s: card **"🔒 Duyệt: disburse"** — "vượt ngưỡng → agent BỊ CHẶN ở tầng tool. Luật nằm ở
  cái két, không ở lời dặn — có dụ nó cũng không mở được." CHỈ: loans vẫn `active`.
- Bấm **✓ Duyệt** → ~25-30s: resume → **"Biên nhận giải ngân"**. "Đúng MỘT lần — gọi lại chỉ trả
  biên nhận cũ." → *"Đây chính là pain nghiệp vụ: không chặn hết (chậm), không thả hết (rủi ro) —
  luật phân tầng nằm ở tầng tool, audit 100%."*

### CẢNH 3 — Control Tower (deliverable #4) — ~60s
- Bấm **🗼 Control Tower**: hàng chờ duyệt (demo duyệt-tại-chỗ nếu còn phiếu) · **Nhật ký tool**
  (audit append-only — filter theo ca vừa chạy, thấy từng input/output) · trạng thái đội + cost.
- "Mọi hành động của mọi agent đều ghi sổ bất biến — giám sát và truy vết 100%."

### CẢNH 4 — 1 LLM vs CẢ ĐỘI (deliverable #5) — ~90s (chạy chờ ~70s)
- Tab **So sánh 1 vs đội** → gõ "Khách C001 vay 500 triệu được không?" → Chạy.
- Trong lúc chờ: kể kiến trúc (1 Postgres, SDK session bền, event-wake, SSE).
- Kết quả 2 cột: **1 LLM trần** ("không tra được hồ sơ" — 13s, 0 tool) vs **CẢ ĐỘI** (DSCR 1.501
  + nguồn, 6 tool, 2 card). "Đây là lý do multi-agent: không phải nhanh hơn — mà TIN được."

### CẢNH 5 — Chạy trên BẤT KỲ model nào (bonus) — ~30s
- "+ Ca mới" → picker cạnh nút gửi: chọn **zai/GLM** (hoặc wrap/GPT) → gõ 1 câu ngắn → chạy thật.
- "Cùng bộ máy — Claude, GLM, GPT đều cắm được. Trí khôn nằm ở tool + kỷ luật hệ thống, không
  khoá vào 1 nhà model." (Đội đủ multi-agent: dùng zai. GPT: cửa chính.)

## Câu chốt
"5 deliverable: đội song song · planner tự phân rã · hành động thật CÓ PHANH · đài giám sát
truy vết 100% · và bằng chứng đo được vì sao multi-agent thắng. Toàn bộ chạy live — không video."

## Sự cố & thoát hiểm
| Sự cố | Thoát |
|---|---|
| Sub chậm >90s | kể kiến trúc tiếp; trace F1 cho thấy nó ĐANG làm (không chết) |
| Model từ chối/lạc đề | ca mới chạy lại (seed-reset đảm bảo lặp được) |
| Compare timeout | cột single vẫn hiện — kể điểm "single không đủ" luôn |
| Mất mạng provider ngoài | claude-cli/zai dự phòng; đổi SHB_PROVIDER |
| DB bẩn giữa buổi | reset_demo 1 lệnh (~5s) |

## Checklist trước giờ G
- [ ] `reset_demo` chạy sạch · [ ] server :8000 sống + health OK · [ ] .env đủ key (zai/wrap)
- [ ] 1 vòng rehearsal trọn <12 phút · [ ] browser zoom/màn hình chiếu OK · [ ] tab Tower + Workspace sẵn
