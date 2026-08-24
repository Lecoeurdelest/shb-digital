# Sprint 23 — Plan (DRAFT — chưa kickoff, không dispatch)

<!-- LUẬT SỐNG CÒN: Plan là source of truth duy nhất; kickoff EDIT IN-PLACE rồi APPEND section
     Kickoff ở cuối. Task-id: T23-<n>. Namespace S22 đã được dùng bởi evidence UX reframe nên gói
     segment đổi thành S23. D-81/D-82 bên dưới mới là ĐỀ XUẤT; chỉ thành decision sống khi kickoff
     S23 ratify và cập nhật DECISIONS.md. -->

**Objective:** Mở segment tín chấp bằng config trên cổng case-intake D-77, nhưng giữ fail-closed:
event shadow chỉ tạo inbox/case/link/phiên rỗng để middle-office tiếp nhận, không tự chạy MAIN,
không tạo approval và không đi vào `shadow_reviews`. Song song, chuẩn hóa reason-code/RFI/
counter-offer cho luồng sơ thẩm có kiểm soát; không mở auto-approve cho segment mới.

**Theme:** SEGMENT = CONFIG — nhận segment mới mà không giả vờ đã có approval workflow.

**Baseline test count:** tối thiểu mốc đóng `end_sprint_20.md`; phải điền số thật tại kickoff S23.

**Ranh không được nhập nhằng:**

- `case-intake auto_start: shadow` (D-77) = durable intake/read-model, **zero orchestration và zero
  approval** tại thời điểm ingest.
- `shadow_reviews` S18 = so sánh counterfactual của một approval đã được người quyết. Không có
  approval thì không có sample, và S23 không được tạo approval giả chỉ để dashboard S20 tăng số.
- Reason-code/counter-offer được gate trên memo/bench có kiểm soát; không được dùng số dashboard
  S20 làm bằng chứng segment mới.
- `external_party_id` D-77 hiện chỉ là `party_reference`, không phải `customers.id`/internal owner.
  Không được giả mapping bằng cách cho hai chuỗi trùng nhau. S23 có thể tạo memo nêu thiếu mapping/
  dữ liệu; full tool-backed 4-role và counter-offer trên chính case LOS phải chờ adapter identity
  được contract hóa ở gói S24. `CO-01` S23 chạy riêng trên internal owner đã map.

## Tasks (6, làm theo dependency)

### T23-1 — Case-intake config v2 + guard fail-closed

- **Assignee:** `dev-be` (BA-S23 review schema/compatibility trước code).
- **Mô tả:** Contract-first schema config v2 cho `backend/app/case_intake/config.py` và
  `configs/case-intake.yaml`: `allowed_products` thêm `UNSECURED_CONSUMER` và
  `UNSECURED_PUBLIC`; `product_profiles` override theo product, thiếu key fallback tuyệt đối về
  `workflow_profile` v1. Guard ở code: mọi product ngoài `SME_SECURED` chỉ được resolve thành
  `preassessment_only` + `auto_start: shadow`; config yêu cầu profile/mode khác thì raise
  `CaseIntakeConfigError` không chứa secret. Giữ parser v1 backward-compatible. Validate config
  trong `app.main` lifespan trước cleanup/agent boot để “invalid config = service không boot” là
  sự thật, thay vì chỉ 503 ở request đầu. Đề xuất ratify D-81 tại kickoff.
- **Dependency:** none.
- **Verification:** Unit test YAML v1 hiện hành parse y nguyên; YAML v2 fallback/override đúng;
  product mới được accept và product ngoài allowlist trả 4-field. Lifespan với config unsafe raises
  trước `cleanup_orphans/main_session.boot`; error không lộ env/credential. Intake event product mới
  atomically tạo inbox + external case link + tối đa một conversation, nhưng SQL/assert chứng minh
  zero messages/tasks/cards/approvals/shadow_reviews/tool call và zero wake MAIN.

### T23-2 — Ranh operator-start cho conversation preassessment-only

- **Assignee:** `dev-be`.
- **Mô tả:** Chốt contract/runbook cho việc cán bộ mở conversation đã link và **chủ động** gửi
  user message qua đường chat hiện hữu; ingest không gửi message hộ. MAIN system context ở lượt đó
  đọc server-side từ `external_case_links` theo `conversation_id` + tenant, chỉ inject
  `{source_system, external_case_id, product_code, loan_amount_vnd, missing_field_codes,
  data_as_of}`; không copy raw inbox và không coi `external_party_id` là internal owner. Quan trọng
  hơn, guard ngay choke-point `gated()` chặn `disburse|ops_disburse` cho mọi conversation link từ
  intake `preassessment_only`, trước verdict/approval INSERT, dù prompt/model yêu cầu; trả envelope
  4-field `preassessment_only` có action kế. Không đổi behavior conversation SME/internal không link.
- **Dependency:** T23-1.
- **Verification:** Event ingest một mình sau thời gian chờ vẫn zero task/message/card/approval.
  Sau admin gửi explicit start, context tenant A không đọc được từ tenant B; prompt context không có
  field ngoài allowlist và external party không bị dùng làm owner. Gọi trực tiếp cả `disburse` lẫn
  `ops_disburse` từ linked conversation bị chặn trước verdict, approval insert và loan/application
  mutation; cùng call trên fixture SME/internal hiện hữu giữ regression.
  Restart/retry không tự start và không tạo conversation thứ hai.

### T23-3 — Reason-code taxonomy + RFI tối thiểu dữ liệu

- **Assignee:** `dev-be` + `dev-fe` (`dev-be` taxonomy/RFI transport, `dev-fe` exact-case deep-link).
- **Mô tả:** Contract-first `configs/reason-codes.yaml` versioned với nhóm `HS_THIEU_*`, `CIC_*`,
  `THU_NHAP_*`, `PHAP_LY_*`, `TSDB_*`; mỗi code có id/nhóm/mô tả và checksum. Tờ trình sáu mục chỉ
  chọn code tồn tại, ghi `reason_codes[]` + taxonomy version/hash trong mục 5; không đổi card type.
  Checker máy-đọc là release gate, không tuyên bố prompt tự nó là phanh.

  Với RFI, contract bổ sung allowlist `missing_fields` dạng code (unknown không được forward),
  admin exact-case resource/deep-link, và payload webhook riêng chỉ gồm event kind, danh sách code
  field và internal deep-link; cấm amount, tên khách, external party id, CIC value, document content.
  Notification chỉ phát **sau commit** khi receipt mới có status `accepted`; duplicate/stale/đủ hồ
  sơ không phát. Retry cùng event không tạo notification ứng dụng lần hai. Việc mở rộng D-71 phải
  được ratify thành decision riêng tại kickoff; trước đó task không được dispatch.
- **Dependency:** T23-1.
- **Verification:** Taxonomy loader reject duplicate/unknown group/malformed version; checker đọc
  `cards.data` và fail mọi code ngoài taxonomy. Webhook mock ca missing nhận đúng allowlist codes +
  link, assert absence amount/name/CIC/content; unknown field bị reject hoặc omit fail-closed theo
  contract; case đủ/duplicate/stale → 0 request. Anonymous/RM/customer exact-case → 401/403 và zero
  fetch; admin tenant khác không thấy. Row/link mở đúng case, không suy case từ conversation title.
  Regression `test_notify_channels.py` và contract D-71 approval doorbell giữ nguyên payload cũ.

### T23-4 — Counter-offer có tính lại và citation

- **Assignee:** `dev-be` (prompt/skill + bench; không sửa vỏ/card/FE).
- **Mô tả:** Đề xuất phương án thay thế chỉ khi retrieval products tìm được gói phù hợp và tool
  nghiệp vụ chứng minh lại: `product_suggest` chọn candidate, `credit_assess` chạy với số tiền/
  điều kiện candidate, wiki products cung cấp điều khoản/lãi suất. Mỗi item có source cho cả kết
  quả tool và wiki; model không tự sinh sản phẩm, số tiền hay lãi suất. Memo vẫn sáu mục, phương án
  thay thế là subsection có điều kiện. Đề xuất D-82 tại kickoff: taxonomy chỉ-được-chọn và
  counter-offer chỉ từ tool + nguồn có citation.
- **Dependency:** T23-3 (memo shape/taxonomy chốt).
- **Verification:** Bench `CO-01` deterministic: ca không đạt gói lớn, `product_suggest` có candidate,
  `credit_assess` chạy lại với candidate và memo có counter-offer; mỗi item có đủ tool source + wiki
  source và reason code hợp lệ. Negative fixture thiếu một trong hai tool result hoặc citation →
  checker fail/không sinh counter-offer. `XD-01` vẫn đúng sáu mục/sources; ca một-role dùng fixture
  deterministic, không dùng live CR-01 làm negative gate.

### T23-5 — Gate contract/safety độc lập

- **Assignee:** `tester-1`.
- **Mô tả:** Kiểm config v1/v2/startup fail, tenant/idempotency, zero-auto invariant và tool-layer
  preassessment-only; kiểm RFI minimization/dedup/exact-case authz. Review ngược plan PM để bảo đảm
  không task nào dùng approval-shadow làm proxy cho intake-shadow.
- **Dependency:** T23-1, T23-2, T23-3.
- **Verification:** Evidence độc lập cho invalid config không boot; product mới ingest `202` nhưng
  zero task/card/approval/shadow row; direct gated call không tạo side effect; webhook đúng allowlist
  một lần sau commit; tenant B zero visibility. Ghi rõ mọi divergence và không ký PASS khi thấy
  sample S20 tăng từ intake-only event.

### T23-6 — Gate memo/bench + full regression độc lập

- **Assignee:** `tester-2`.
- **Mô tả:** Chạy vòng có kiểm soát sau operator-start: product mới giữ preassessment-only, nhận
  linked context/RFI và memo reason-coded trung thực (có thể kết luận thiếu internal-party mapping),
  rồi kết thúc ở output/handover. Counter-offer chạy **riêng** bằng `CO-01` trên
  `internal_operations` owner đã map; không claim đó là case LOS mới. Không decide approval, không
  ghi `shadow_reviews`, không gọi disburse cho segment mới. Regression
  `SME_SECURED`, S18 ledger/S20 dashboard và D-77 intake idempotency nguyên vẹn. PM review evidence
  của cả hai tester; hai tester review source-of-truth/kickoff trước ký cuối.
- **Dependency:** T23-1, T23-2, T23-3, T23-4, T23-5.
- **Verification:** Log/SQL/screenshot linked-context memo + exact-case/RFI; mọi reason code hợp lệ.
  `CO-01` riêng có `product_suggest + credit_assess + wiki citation`; SQL segment mới có zero
  approval/shadow/disbursement và không có fake external→internal owner mapping. Full suite
  `>= end_sprint_20`, 0 fail; ruff/format/FE test/tsc và
  `git diff --check` sạch.

---

## History — rewrite 2026-08-24 (>30% drift)

Draft ban đầu mang số S22 và gate `case-intake shadow → 4 role → approval decision →
shadow_reviews → dashboard S20`. Repo audit chứng minh chuỗi đó trái D-77: intake shadow hiện chỉ
tạo mapping/conversation, không chạy MAIN, tạo approval hay tool call; ledger S18 cũng không có
product code để chứng minh segment. Namespace `sprints/evidence/s22-ux-reframe/` đã tồn tại. Vì vậy
plan được đổi thành S23 và rewrite: tách hai nghĩa shadow, thêm explicit operator-start + tool-layer
profile guard, contract hóa RFI/exact-case, và loại dashboard S20 khỏi gate segment.

## Kickoff — {{YYYY-MM-DD}}

**Drift since plan:** {{phải chạy lại repo/suite và ratify hoặc bỏ D-81/D-82 + decision RFI; không
được dùng nội dung History thay cho audit kickoff mới.}}

**Plan revisions:** {{...}}

**Final task list (chốt dispatch):**

- {{CHƯA DISPATCH — chỉ điền sau kickoff S23.}}
