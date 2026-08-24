# Sprint 20 — End (Máy đo shadow + consent pre-pilot)

**Status (2026-08-24): CLOSED về kỹ thuật, có hai finding quy trình đã sửa trong source-of-truth.**
API/list ca lệch, Tower drill-down và consent foundation vượt gate độc lập. Theo D-80, pilot dùng dữ
liệu thật vẫn **NO-GO**: sprint này không phải DPIA, đánh giá chuyển dữ liệu, ý kiến pháp lý hay
bằng chứng tuân thủ.

## Delivered

- `GET /api/stats/shadow-match/mismatches` là admin-only, tenant lấy từ JWT, chỉ đọc mismatch và
  trả page object/keyset ổn định theo `decided_at, approval_id`; filter thời gian UTC half-open,
  lane, limit và cursor bound với context đều được khóa bằng contract/test.
- Tower có tab “Đối chiếu shadow” chỉ cho admin: KPI tổng/lane/ngày, copy trung lập và bảng ca lệch
  đi qua exact deep-link S19 để highlight đúng phiếu. RM/customer không render và zero-fetch.
- Wording pre-pilot v1 được server snapshot cùng version + SHA-256; ledger `consent_records` có
  constraint, unique proof link và DB trigger chặn UPDATE/DELETE. Migration up/down reversible.
- Form bắt buộc checkbox chưa tick mặc định. Client chỉ gửi `consent_granted:true`; server lấy
  tenant/actor/subject và wording proof từ nguồn sở hữu server. Card, customer, user link và consent
  cùng transaction; lỗi giữa chừng rollback toàn bộ, retry không nhân bản.

## Independent evidence and PM cross-review

### Tester-1 — T20-5: PASS

- Harness đối kháng độc lập: **6/6 pass** cho API/auth/tenant/keyset và consent atomicity,
  checksum/constraints/append-only/static ledger seams.
- DB sạch chạy `upgrade head → downgrade 9f3a2b7c4d10 → upgrade head`; revision cuối
  `d4e8a1b7c203`, table và trigger append-only cùng tồn tại.
- PM chạy lại đúng harness: **6 passed**; đồng thời tự lặp migration hai chiều trên DB tạm và
  drop đúng DB sau khi lấy evidence.
- Evidence: `sprints/evidence/s20-tester-1.md`.

### Tester-2 — T20-6: PASS, có caveat reproducibility

- Gate fresh sau thay đổi: **613 backend passed + 17 skipped**, **336 frontend passed** =
  **949 passed + 17 skipped**, zero failure trong lượt tester ký; Ruff, format, typecheck, build và
  `git diff --check` pass.
- Stack thật/seed xác định có ba comparable: green+approved, red+rejected, green+rejected →
  `matched=2/3`, Tower hiện `66,7%`; click ca lệch mở và highlight đúng approval. Screenshot chứng
  minh dashboard/highlight; exact URL được đối chiếu thêm bằng browser log và integration test vì
  ảnh không chứa thanh địa chỉ.
- Consent live: thiếu consent `400` và zero row; grant `200`, một record v1 có SHA khớp; submit lặp
  `409`, vẫn một record. Forced failure rollback được test riêng.
- Evidence: `sprints/evidence/s20-tester-2.md` và hai ảnh `gate-s20-*-tester2.png`.

PM đối chiếu thêm full backend và nhận **613 pass + 17 skip**. Với frontend, PM tái lập đủ
**336/336** khi chạy một worker và focused `App.test.tsx` **9/9**; default parallel runner có timing
flake lặp lại ở hai test async trong `App.test.tsx` (334/336 ở các lượt PM). Vì tester-2 có lượt
fresh default xanh và serial/focused đều xanh, finding được xếp nợ ổn định test, không phải defect
nghiệp vụ S20; tuy nhiên receipt này không claim PM tự tái lập default parallel zero-fail.

## Process findings and remediation

- **PM-01 — FAIL tại kickoff, remediated in-place:** PM dispatch trước khi chạy fresh baseline.
  Mốc `807 + 17 skip` của S21 chỉ là historical reference; không được đổi nhãn hồi tố. Gate
  `949 + 17 skip` là kết quả sau thay đổi.
- **PM-02 — FAIL source dependency, remediated in-place:** plan ban đầu cho T20-6 phụ thuộc T20-5,
  trái tính độc lập. T20-5/T20-6 thực tế chạy song song theo root và plan đã sửa để cả hai chỉ chờ
  task dev; PM review từng report sau khi cả hai nộp.
- Cả tester-1 và tester-2 đều phát hiện độc lập PM-01/PM-02. PM chấp nhận hai verdict, sửa History
  minh bạch và không biến correction thành claim rằng dispatch ban đầu đúng.

## Quality and remaining debt

- Backend: **613 passed + 17 skipped**; focused S18/S19 **16 passed** theo tester-2.
- Frontend: tester-2 **45 files / 336 passed**; PM serial **45 files / 336 passed**; typecheck/lint/
  build pass theo evidence tester-2.
- Môi trường fresh thiếu optional `pyvi` làm một retrieval test fail trước khi tester cài riêng
  `pyvi==0.1.1` vào test venv. Dependency/conditional skip cần được làm rõ ở sprint sau; không có
  repo change để che nợ này.
- Default parallel Vitest timing flake ở `App.test.tsx` cần harden; serial/focused pass không xóa
  nghĩa vụ xử lý flake.

## D-80 hard gate / explicit non-claims

- Wording/controller/contact, retention/deletion/withdrawal, recipients và cloud/cross-border phải
  được bank legal/data-protection owner phê duyệt.
- DPIA và đánh giá chuyển dữ liệu áp dụng phải hoàn tất trước pilot dữ liệu thật.
- Consent phía LOS/SAHA thuộc trách nhiệm hệ nguồn theo contract; S20 không đổi envelope D-77.
- Vì vậy **TECHNICAL S20: PASS/CLOSED; PILOT REAL-DATA: NO-GO**.

**Verdict:** Tester-1 PASS; Tester-2 PASS với caveat reproducibility được ghi trên; PM process
kickoff FAIL ở PM-01/PM-02 và đã remediated có History. Không kickoff/dispatch Sprint 23 trong lần
đóng này.
