# Sprint 23 — End (Segment = config)

**Status (2026-08-24): CLOSED về kỹ thuật.** Config segment tín chấp, operator-start,
reason taxonomy, RFI/exact-case và counter-offer có proof đều vượt hai gate độc lập. Theo
D-80, pilot dữ liệu thật vẫn **NO-GO** cho tới khi bank/legal/data-protection owner ký và
hoàn tất các đánh giá tác động áp dụng.

## Delivered

- Case-intake config v2 bind mỗi source credential vào một `tenant_slug`, giữ parser v1 và
  fallback source-level. Product ngoài `SME_SECURED` chỉ được
  `preassessment_only + shadow`; config/taxonomy không an toàn dừng trước agent boot.
- Ingest segment mới chỉ ghi inbox/case/link/conversation rỗng theo tenant, không wake MAIN,
  message/task/card/approval/tool hay `shadow_reviews`. Operator phải gửi chat chủ động; linked
  context chỉ có sáu field allowlist và không persist thành message.
- Rào trong `_gated_txn` chặn cả `disburse` lẫn `ops_disburse` cho mọi linked conversation
  trước threshold, receipt, verdict và write. Nhánh SME nội bộ không link giữ regression
  tiền/idempotency.
- Reason taxonomy v1 được validate lúc startup và trước khi ghi tờ trình. Memo bắt đúng
  sáu mục; item 5 dùng mã hợp lệ, proof version/checksum do server sở hữu; sai thì zero
  card/SSE. Generic document không bị đổi contract.
- RFI normalize field về allowlist/sentinel, chỉ schedule best-effort sau commit khi changed-set
  hợp lệ; webhook có đúng hai key `{missing_fields, deep_link}`. Exact-case API là
  admin-only/tenant-scoped/404-hide; URL strict được giữ qua login và target ngoài page 50
  được merge/highlight.
- Counter-offer v1 tối đa một offer. Ca C009 `CO-01` có audit thật
  `600m fail → P001 500m eligible → credit reassessment 500m eligible, DSCR 1.371`, hai wiki
  citation active; checker đọc fresh card + `tool_calls`, không tin model memory/markdown.

## Task verdicts

| Task | Kết quả | Bằng chứng chính |
|---|---|---|
| T23-1 | PASS | Config v1/v2/startup/tenant/rollback/idempotency targeted; E2E segment `202` và zero-auto SQL. |
| T23-2 | PASS | Context allowlist/tenant tests; cả hai gated action chặn trước mọi branch; curl/browser operator-start. |
| T23-3 | PASS | Taxonomy + memo write gate; RFI matrix/two-key/no-CIC; exact-case authz và FE exact-fetch/highlight. |
| T23-4 | PASS | Fresh CO-01 tool/card/audit checker; 8 negative checker cases. |
| T23-5 | PASS | Tester-1 gate contract/security/DB độc lập, targeted cuối 118 pass. |
| T23-6 | PASS | Tester-2 E2E/CO-01/full suite; literal curl + Selenium screenshot remediated trước close. |

## Independent evidence and defect history

### Tester-1 — T23-5: PASS sau khi bắt một defect production

Lượt đối kháng đầu là **`1 failed, 4 passed`**. Hai event cùng
`source_version` nhưng raw `missing_fields` khác nhau bị coi là duplicate vì content hash băm
dữ liệu sau normalize. Root sửa identity hash về raw case; normalize chỉ dùng cho
storage/read-model/RFI/context. Rerun cùng regression D-77 đạt **23 passed**; gate targeted cuối
trên freeze đạt **118 passed, 0 failed**. Tester-1 cũng khóa privacy để `cic_consent` và
raw CIC chỉ còn sentinel, không xuất hiện trong webhook.

FE exact-case targeted đạt **13 passed**; Ruff, format và `git diff --check` sạch. Evidence:
`sprints/evidence/s23-tester-1.md`.

### Tester-2 — T23-6: PASS, giữ nguyên caveat/rerun

- Backend freeze: **694 collected = 677 passed + 17 skipped**, 0 fail. Venv test có
  `pyvi==0.1.1`; clean `uv sync --frozen` chưa bảo đảm optional dependency này.
- Frontend default-parallel lượt đầu: **346 passed, 2 failed / 348** do timeout/state timing
  trong `App.test.tsx`, cùng flake đã ghi từ S20. Lượt ký serial: **348/348 passed**.
  Con số chữ ký sprint là **1.025 pass + 17 skip**; không xóa lượt fail ban đầu.
- Ruff/format/typecheck/build/`git diff --check` PASS. Lint exit 0 với sáu Fast Refresh warning
  cũ; build có chunk-size warning không chặn; backend có 156 deprecation warning TestClient.
- E2E ASGI/SQL chứng minh segment zero internal mapping/approval/shadow/disbursement, linked
  context/RFI data-minimized và operator chat là hành động chủ động. CO-01 fresh checker
  PASS với P001 500m, DSCR 1.371 và đúng hai citation.

Báo cáo ban đầu thiếu screenshot literal theo verification T23-6. PM không ký và yêu cầu
remediation. Tester-2 sau đó chạy curl + Selenium trên stack local, chứng minh RFI URL exact
giữ nguyên, target `active + focused`, rồi mở đúng linked conversation có user message và
không có assistant output. PM đã mở kiểm hai ảnh trước khi đóng:

- `sprints/evidence/s23-exact-case-rfi-tester2.png`
- `sprints/evidence/s23-explicit-operator-turn-tester2.png`

Evidence đầy đủ: `sprints/evidence/s23-tester-2.md`.

## PM process cross-review

**Process verdict: PASS.** Plan được rewrite/kickoff trước dispatch tại `825776d`; baseline
fresh S20 `949 + 17 skip` và hai nợ môi trường được ghi từ đầu. T23-5/T23-6 chỉ
phụ thuộc task dev, không phụ thuộc/sign-off lẫn nhau; hai tester dùng DB riêng `:55432` và
`:56432`, cùng review ngược PM. PM chờ cả hai report, review riêng và giữ gate mở cho
tới khi evidence screenshot được bổ sung. Không lặp PM-01/PM-02 của S20.

## Explicit non-claims and remaining debt

- Không có API key/provider credential nên không chạy live model. Không claim memo bốn role,
  DSCR/product hay counter-offer cho case LOS; screenshot operator cố ý không có assistant output.
- `external_party_id` vẫn chỉ là party reference. External→internal identity adapter, full LOS
  four-role và adapter CIC/C06/BHXH non-claim defer S24.
- RFI là best-effort sau commit: transport có thể lặp và crash-window có thể mất chuông;
  sprint không claim exactly-once và không thêm outbox.
- Optional `pyvi` chưa được clean install kéo theo; default-parallel Vitest vẫn có hai
  timing-flake. Serial/focused pass không xóa hai nợ reproducibility này.
- D-80 vẫn là hard gate: sprint kỹ thuật này không phải DPIA/compliance evidence. Pilot dữ
  liệu thật là **NO-GO**.

**Verdict:** T23-1→T23-6 PASS; Tester-1 và Tester-2 PASS độc lập; PM process PASS.
Sprint 23 đóng kỹ thuật với các non-claim/defer trên, không mở pilot dữ liệu thật.
