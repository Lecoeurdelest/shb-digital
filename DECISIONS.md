# DECISIONS — sổ ngoài-dự-tính (mới nhất trên cùng)

> ① VƯỢT-SPEC: tình huống spec không lường. ② TỰ-QUYẾT: phương án agent chốt khi vắng người.
> Format: `quyết gì — vì sao — cách đổi`. NGƯỜI đọc lại async + override (human-wins).
> Entry đã tiêu hóa vào kit thì xoá — sổ chỉ giữ quyết định CÒN SỐNG (lịch sử đầy đủ: git log).

## ① VƯỢT-SPEC

- (trống)

## ② TỰ-QUYẾT

- **D-16 · SDK auth = dùng auth máy (claude-cli subscription), KHÔNG env/key trong build**
  (người chốt 18/7) — port pattern `Providers` từ `battle/core/runtime/providers.py`:
  `providers.yaml` giữ 1 provider `claude-cli` (`kind: subscription`, `default: true`) →
  `resolve_env` trả env RỖNG → SDK dùng auth Claude CLI bundle của máy, không cần
  `.env`/API key. Model routing: **main=sonnet · sub=haiku**. Slot `wrap`/`zai` (base-url +
  key) COMMENT sẵn trong yaml — chỉ mở khi build PROD. — Đổi: người nói cắm provider thật.
- **D-17 · `customers` = tool CHUNG của role Credit, KHÔNG phải chuyên gia thứ 5**
  (người chốt 18/7) — 4 chuyên gia = 4 PHÒNG BAN (Credit/Legal/Products/Operations).
  "Khách hàng" là ĐỐI TƯỢNG trong câu hỏi RM (DN X vay 5 tỷ), không phải actor gọi vào hệ.
  LAB `customers.py` (`cust_search`/`cust_get`) → nhét vào toolpack `credit` (tra khách là
  input thẩm định — SKILL credit ghi rõ). — Đổi: người tách customers thành role riêng.
- **D-18 · Products + Operations = STUB cùng contract; VỎ chủ động không để LAB block**
  (người chốt 18/7) — role LAB đang build bên `../shb-digital-experts/` → mount stub trả
  data giả đúng shape, swap function thật khi LAB giao (§7: thả file + dán SCHEMAS + xoá
  stub, `mount_role` không đổi). Cùng cơ chế thì chỉ đổi biến/tên — bản chất nhiệm vụ giữ
  nguyên. **`disburse` (tool gated) build SẴN wrapper gated THẬT của VỎ** (phanh là của vỏ
  §4.4, không của LAB) để B4 chạy end-to-end; swap function khi Ops về. — Đổi: LAB giao bản thật.
- **D-19 · Người duyệt phanh = QUẢN LÝ (account admin), màn Control Tower** (người chốt 18/7)
  — nghiệp vụ thật: RM (user) xin giải ngân → phanh chặn → QUẢN LÝ duyệt (đúng đời thật quản
  lý duyệt cho nhân viên). 2 account seed đúng đề: `user`=RM · `admin`=quản lý·compliance.
  "Control Tower" = MÀN CỦA QUẢN LÝ, không phải actor kỹ thuật thứ ba. — Đổi: người đổi mô hình duyệt.
- **D-20 · Chat-với-sub = CỬA SỔ GIÁM SÁT, không phải kênh giao việc song song** (người chốt
  18/7) — UI: user CHỦ YẾU chat với Main; click 1 sub (panel phải: lobby 3D + chip phòng ban) →
  khung giữa chuyển sang view sub đó (trace sống + nhắn riêng + ⏹ dừng). Nhắn riêng cho sub
  KHÔNG phá luật "sub không nói với user": sub chỉ ghi nhận, kết quả VẪN về Main rồi Main trả
  user (§3). Mock `App.jsx` đã encode (`focus: planner|role`). — Đổi: người mở kênh sub trực tiếp.

- **D-08 · Nguồn tài sản LAB (reuse-copy READ-ONLY)** — copy từ repo anh em
  `../shb-digital-experts/missions/shb-132/`: `tools/functions/*.py` (credit, customers, legal)
  · cụm SCHEMAS trong `tools/server.py` · `skills/<role>/SKILL.md` · `seed/shb-132.db`. Không
  sửa gì bên nguồn. Nguồn VẮNG → hỏi người cấp, **cấm tự chế** (nhất là seed DB). — Đổi: người
  chỉ nguồn khác. *(Roster mount THẬT/stub đã chốt cứng ở D-17+D-18 — không còn "quyết lúc kickoff".)*
- **D-12 · Git: repo PUBLIC `tinhnguyen0110/shb-digital` (lệnh người 18/7)** — đã push init
  lên `https://github.com/tinhnguyen0110/shb-digital` (public). Branch: `master`. **`.mcp.json`
  GITIGNORED** (chứa key Cairn `ck_...` — không lên remote; `git add -A` từng suýt lọt, đã
  `git rm --cached`). Architect commit theo task + push nền như CLAUDE.md §6. — Đổi: người đổi
  visibility / xoay key Cairn.
- **D-13 · Design/mock = THAM KHẢO, không phải nguồn scope (người chốt 17/7)** — có thể thiếu
  hoặc thừa; scope build = TÍNH NĂNG trong SPEC. Đã mã hoá vào CLAUDE.md §1 + frontend.md +
  tester.md. — Đổi: người tuyên bố lại "mock là baseline cứng".
- **D-15 · Alert/notification ngoài (Discord/email) KHÔNG vào scope chính (người chốt 18/7)**
  — demo: toast in-app + badge + approval queue đủ; webhook Discord = TUỲ CHỌN nhét A6 nếu
  kịp (~30'), không phải sprint riêng. — Đổi: người kéo vào scope khi chốt backlog.
- **D-14 · Design bundle đã nhận (17/7), nằm tại `design/`** — export Claude Design: tokens
  ĐẦY ĐỦ (`design/workspace/shared.jsx` — object `T`: bộ màu run/pass/fail/warn/main + font),
  Workspace React mock + lobby 3D + seed snapshot, `design/Digital Expert Guild.dc.html`
  (Login + Tower + Approval). FE port tokens từ `T` → `frontend/src/tokens.css` ở dispatch
  đầu. Blocker B2 đóng. — Đổi: người cấp bản design mới đè vào `design/`.
