# Sprint 9 — DRAFT: Khách mới + vòng đời hồ sơ (D-57, sau S7)

> Người chốt 18/7 (input mentor): quy trình vay nhiều giai đoạn — khách MỚI đăng ký chưa có
> thông tin → form intake; duyệt xong user vắng app → mail thật + bell. App password Gmail:
> NGƯỜI gửi sau — code phải chạy sạch khi env thiếu (mail no-op + log, bell vẫn sống).

## Task dự kiến

### T9-1 — Backend: signup + form intake + tạo hồ sơ (gating)
- `POST /api/auth/register` (username/password/email) → role=customer, owner_id=NULL.
- Card type `form` + tool `present_form` (MAIN/sub gọi khi thiếu info — pattern present-tool N5
  sẵn): fields[] định nghĩa server-side (họ tên, CMND, thu nhập, mục đích, tài sản, kỳ hạn).
- `POST /api/conversations/{id}/form-submit` (hoặc submit thành message cấu trúc — chốt kickoff):
  tạo/UPDATE bản ghi `customers` mới + link `users.owner_id` + đánh thức MAIN (đường
  handle_room_event sẵn — KHÔNG cơ chế mới).
- Khách mới → 3 trụ honest-null → lane yellow (S7 đã port — không việc gì thêm, chỉ verify).

### T9-2 — Backend: mail + bell API (song song T9-1 sau contract)
- `notify_email(to, subject, body)`: smtplib SMTP_SSL smtp.gmail.com:465, env `SMTP_USER` /
  `SMTP_APP_PASSWORD` / `NOTIFY_FROM_NAME` (.env.example cập nhật, gitignored). Env thiếu →
  log + skip (no-op sạch). Gửi async best-effort SAU approval.decided + receipt — lỗi mail
  KHÔNG chết resume (§12 best-effort như audit).
- users.email (migration) — register thu email; seed b001/c001 email demo.
- `GET /api/notifications` (khách): sự kiện duyệt/giải ngân của CA MÌNH (đọc từ approvals/cards
  — không bảng mới nếu query đủ; chốt kickoff).

### T9-3 — Frontend: Register form + FormCard + bell khách
- Màn đăng ký (từ Login). FormCard render fields + submit. Bell header khách (poll
  /api/notifications — pattern useApprovalBadge, dừng tab ẩn) + dropdown danh sách.

### T9-4 — Script v7 + tester e2e vòng đời
- Cảnh mới: khách MỚI đăng ký trên máy chiếu → form → thẩm định yellow "chưa xác minh" → bank
  duyệt → MAIL về điện thoại thật trên sân khấu + bell trong app. Thoát hiểm: mất mạng → chỉ bell.
- Tester: e2e register→form→hồ sơ mới→yellow→duyệt→bell (mail assert log-level khi chưa có
  creds; live-mail test khi người gửi app password).

## Gate S9 (dự kiến)
E2e khách mới trọn vòng đời + mail thật gửi nhận (khi có creds; chưa có → waiver §6b tạm) +
bell sống + suite ≥ baseline S8. Không chết resume khi mail fail (kill-switch test).
