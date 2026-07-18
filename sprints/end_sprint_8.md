# Sprint 8 — End

**Theme (D-56, user chốt 18/7 — làm TRƯỚC S7):** 2 persona — app = CỬA KHÁCH HÀNG (khách tự
chat, agent tự duyệt khoản nhỏ theo ma trận), khoản lớn bắn về NGÂN HÀNG duyệt. Đảo D-54.
**Commit:** 82883bb (kickoff) · 06585e4 (T8-1 BE) · 09c55c7 (T8-2 FE) · ac966b4 (T8-3 script v6)
· f4c1da9 (D-57 S9 draft) · đóng = commit chứa file này

## Kết quả từng task

### T8-1 — done (authz/scoping D-56 + MAIN identity inject, 06585e4)
- **Bằng chứng:** decide/audit → require_admin (khách 403 4-field) · scoping `can_access_conv`
  trên conversations/SSE/interrupt (ca người khác → 404-hide, không lộ tồn tại) · admin list
  TẤT CẢ ca · users.owner_id + seed c001→C001, b001→B001 · /api/me {username, role, owner_id}
  (+/api/auth/me backward) · MAIN inject block "KHÁCH HÀNG HIỆN TẠI" theo CREATOR ca (xưng
  anh/chị, khoanh về khách, không tra người khác; bank/ca cũ → không block; lỗi DB → best-effort).
- **Chuẩn PROD trong task:** main_session 627→412 LOC — tách main_skill/main_prompts/audit_emit
  (move-only), test import về canonical home.
- **Tester verdict:** matrix 7/7 + invert 2 test D-54→D-56 (tester tự sửa test mình — author≠checker).

### T8-2 — done (FE view theo role + badge phiếu-bay, 09c55c7)
- **Bằng chứng:** ApprovalPanel canDecide (khách pending → "⏳ Đang chờ ngân hàng phê duyệt",
  DOM 0 button — tester zoom + query xác nhận) · Tower gate isAdmin · useApprovalBadge poll 5s
  (dừng tab ẩn, 403 tắt im lặng, không SSE global — không thêm primitive SPEC §2) · client.me()
  fallback server-cũ. FE tự-verify Chrome live: c001 ẩn hết, admin badge 21 phiếu thật.

### T8-3 — done (script demo v6 hai-cửa-sổ, ac966b4)
- Sân khấu 2 cửa sổ (khách trái b001 / bank phải admin), cảnh 2 phiếu-bay, DEV_SKIP_AUTH=0,
  fallback 1-cửa-sổ admin = flow v4 nguyên vẹn. MAIN tone khách = inject (T8-1), không cần sửa skill.
- **Rehearsal (gate — DELTA, architect chốt):** C1+C2 chạy TRỌN, PASS (tester 18/7): câu C1
  không-khai-mã → MAIN tự map B001 qua inject, KHÔNG hỏi lại, fan-out song song 3 sub, Legal
  không dừng, 0 chuỗi nội bộ lộ — **2'10"**. C2A auto-rule **43"** (mốc script đổi ~45s — model
  latency, không phải logic; decided_by/reason DB đúng). C2B trọn vòng phiếu-bay→duyệt→receipt
  **~3'** (gồm đổi vai thủ công 1-browser). C3/C4/C5 KHÔNG chạy lại — zero delta so v4
  (Tower/compare/picker không bị S8 đụng; evidence S4/S5 rehearsal + T8-4 + smoke e2e).
  Vòng trọn 2-cửa-sổ bằng tay = checklist trước giờ G (người chạy).

### T8-4 — done (tester e2e 2-phía)
- **Bằng chứng:** khách disburse 1 tỷ → card chờ (0 button) → admin badge/queue (1) → duyệt UI
  thật → queue về 0 → DB pending→approved→used+receipt, loan disbursed → khách login lại nhận
  "✅ Giải ngân thành công, anh..." · decide từ session c001 → 403 4-field · ca người khác →
  404 · fan-out khách: MAIN xưng "anh" 3 lượt, tự khoanh C001, KHÔNG lộ
  tool_call/dispatch/sub-agent/orch (get_page_text toàn trang). Cookie-isolation chứng minh
  qua 2 HTTP session độc lập (real-time 0→1 data-layer).

## 3 Quality Gates
- [x] **Gate 1 — API**: /api/me mới + đảo authz decide/audit (403/404 đúng 4-field, envelope
  giữ) · integration mới (persona_d56 11 + e2e_tester) · test cũ pass (241) · không primitive
  ngoài SPEC (badge = polling, không SSE global/WebSocket) · status code đúng (403 forbidden
  vs 404 hide phân biệt chủ đích).
- [x] **Gate 2 — Function**: unit mới (can_access_conv, inject, badge hook, canDecide) · edge
  (owner thiếu → fallback, /api/me server cũ → null, 403 poll-stop, tab ẩn, DEV_SKIP_AUTH
  regression) · fail-open/closed rõ (inject best-effort fail-open ""; authz fail-closed) ·
  ruff check + format sạch + tsc sạch · không test tự-xác-nhận (tester verify độc lập, invert
  test của chính nó) · FE Chrome self-verify · LOC ≤400 sau tách (412 trong biên mềm ±10%,
  3 module mới ≤107).
- [x] **Gate 3 — Sprint**: số liệu tự chạy lại độc lập: **241 BE + 90 FE = 331 ≥ baseline 302**
  · architect đọc trọn (4 nhánh diff BE + 3 module tách + hook/panel FE) · tester 100% +
  browser + rehearsal v6 · phát hiện ngoài-scope ghi (dưới) · commit format · invariant SPEC
  §15 giữ (phanh/audit nguyên — chỉ đổi AI duyệt) · UNVERIFIABLE → sổ ngoại lệ (dưới),
  architect duyệt.

## Test counts
Baseline 302 (224 BE + 78 FE) → **331** (241 BE + 90 FE), re-run độc lập trước commit đóng.
Live: tester e2e 2-phía + FE Chrome + rehearsal v6 delta C1 2'10" / C2A 43" / C2B ~3'.

## Sổ ngoại lệ (§6b)
- **"2 cửa sổ Chrome CÙNG LÚC thấy nhau đổi real-time" không browser-verify được** — Chrome MCP
  1 browser instance, share cookie jar theo domain (tester thực nghiệm: tab 2 tự lộ session tab
  1). Hành vi 2-phía độc lập ĐÃ chứng minh đầy đủ tầng thay thế: HTTP 2-session độc lập
  (cookie-tách + real-time 0→1) + browser tuần tự đổi vai (UI từng phía). — lý do chấp nhận:
  giới hạn CÔNG CỤ verify, không phải sản phẩm; demo thật = 2 cửa sổ người mở, người verify ở
  rehearsal tay trước giờ G. — 18/7 — architect duyệt — xét lại: khi có Chrome profile/browser
  thứ 2 kết nối được.

## Nợ/kỹ thuật ghi nhận
- Deviation chấp nhận: `_customer_prompt_block` query per-turn (dispatch dặn cache) — demo-grade
  OK, cache-ở-create nếu thấy chậm.
- Ca tạo thời DEV_SKIP_AUTH=1 thuộc account 'admin' — login khách không thấy (đúng thiết kế,
  ghi để khỏi báo nhầm bug; user đã hỏi 1 lần — trả lời: reset_demo wipe + scoping đúng).
- RM (role 'user') không duyệt được (require_admin) — persona RM là legacy, demo không dùng.

## Findings ngoài scope (S7/S9)
- **S7 nối ngay:** LAB legal port (T7-1 dispatch sẵn trong mailbox backend) — classify lane =
  ma trận thẩm quyền nâng cao, hợp D-56 hơn nữa.
- Tool-level scoping chặt (khách A hỏi hồ sơ khách B qua chat — skill dặn, tool chưa cưỡng chế)
  — known-limitation, cân sau demo.
- Agent-bền D-50 (sau demo) · settled-helper chung · confirm 2-process lần restart kế (S6 waiver).

## Bài học sprint
- **Đảo hướng lớn ≠ đập engine**: soát seam trước khi hoảng — user_id/require_admin/isAdmin có
  sẵn từ S1/S4 khiến "pivot persona" chỉ là 1 sprint mỏng. Spot-check seam TRƯỚC khi ước effort.
- **Giới hạn công cụ verify phải khai tường minh + bù bằng tầng thay thế** (HTTP-isolation thay
  2-browser) — không hạ chuẩn lặng lẽ, không overclaim badge "real-time" khi chỉ chứng minh
  được data-layer.
