# Sprint 23 — evidence Tester-1

**Ngày:** 2026-08-24
**Phạm vi:** T23-5 contract/security/DB adversarial gate + kiểm tra ngược PM.
**Nguyên tắc:** DB riêng `shb_test` tại `127.0.0.1:55432`; không dùng test dev làm bằng chứng duy
nhất; không sửa production; không chạy full suite vì T23-6/Tester-2 sở hữu.

## Kết luận

**PASS sau một defect production được bắt và sửa.** Lượt độc lập đầu phát hiện equal
`source_version` với raw source content khác nhau bị coi là duplicate vì `content_hash` băm
`missing_fields` sau normalize. Điều này trái CONTRACT §11d. Root sửa identity hash về raw case;
normalize chỉ còn ở storage/read-model/RFI/context. Tester-1 rerun test bắt lỗi cùng regression
idempotency/versioning: PASS.

Freeze cuối còn gồm hardening privacy do root audit: bỏ `cic_consent` khỏi allowlist vì §11f cấm
mọi tên/giá trị CIC trong chuông. Tester-1 thêm test riêng chứng minh cả `cic_consent` lẫn raw
`CIC score 700` chỉ còn sentinel và serialized webhook không chứa chuỗi `cic`.

## Audit ngược PM / source-of-truth

Source plan đọc tại `sprints/plan_sprint_23.md` (kickoff commit `825776d`):

| Invariant PM phải khóa | Bằng chứng trong plan | Verdict |
|---|---|---|
| Intake-shadow khác approval-counterfactual shadow | Objective, “Ranh không được nhập nhằng”, T23-1/2/5/6 đều nói zero approval, zero `shadow_reviews`; gate không dùng dashboard S20 làm proxy | PASS |
| External party không phải internal owner | Ranh scope defer mapping S24; T23-2 context cấm party; T23-6 không claim LOS four-role/counter-offer | PASS |
| Rào tiền ở tool, không chỉ prompt | T23-2 chốt cả `disburse` và `ops_disburse`, trước threshold/receipt/verdict/write | PASS |
| RFI tối thiểu dữ liệu, sau commit, không exactly-once giả | T23-3/D-83 khóa changed-set, exact two-key, crash-window/retry caveat, không outbox/table mới | PASS |
| Hai tester độc lập | T23-5 và T23-6 chỉ phụ thuộc dev tasks, không phụ thuộc/sign-off lẫn nhau; PM review riêng sau cả hai | PASS |
| Baseline và caveat trung thực | Fresh S20 `949 pass + 17 skip`; plan giữ cả caveat `pyvi` và Vitest timing-flake, cấm xóa lượt fail | PASS |

**PM review: PASS.** Không có stale dispatch, không serial hóa Tester-1→Tester-2, không nhập nhằng
hai nghĩa shadow và không tạo sample S20 giả. Phép đọc heading CONTRACT bằng `rg` xác nhận chỉ một
§13; tín hiệu duplicate ban đầu là artefact do hai khoảng `sed` chồng dòng và đã được retract ngay,
không ghi thành defect.

## Lượt đối kháng độc lập bắt defect

Tester-1 thêm `backend/tests/test_s23_tester1_adversarial.py`. Lượt đầu:

```bash
cd backend
TEST_DATABASE_URL=postgresql://shb:shb@localhost:55432/shb_test \
  uv run pytest -q tests/test_s23_tester1_adversarial.py
```

Kết quả thật: **`1 failed, 4 passed`**. Ca fail gửi hai event khác `event_id`, cùng case và
`source_version=7`, nhưng raw `missing_fields` lần lượt là `raw-secret-a`/`raw-secret-b`. Server
không raise; contract yêu cầu `409 source_version_conflict`. Nguyên nhân: `content_hash` dùng
normalized sentinel `additional_information` cho cả hai.

Sau fix production, lệnh rerun độc lập cùng hai regression D-77:

```bash
TEST_DATABASE_URL=postgresql://shb:shb@localhost:55432/shb_test \
  uv run pytest -q \
  tests/test_s23_tester1_adversarial.py \
  tests/test_case_intake.py \
  tests/test_case_intake_runtime_s23.py
```

Kết quả: **`23 passed, 0 failed, 1 warning in 3.95s`**. Warning duy nhất là deprecation
Starlette TestClient/httpx.

Test độc lập còn chứng minh:

- source đang disabled vẫn không che được fallback non-SME `auto_start: off`; startup fail-closed;
- case config hỏng dừng sau runtime-security, trước taxonomy/registry/cleanup/boot;
- proof taxonomy do model bơm bị server overwrite; reason code lạ trả đúng 4 field và zero DB/SSE;
- role `user|customer` cùng tenant vẫn không được start linked conversation `user_id=NULL`: `404`,
  zero message và zero wake; chỉ admin có đường operator-start.

Focused privacy rerun sau patch CIC:

```bash
TEST_DATABASE_URL=postgresql://shb:shb@localhost:55432/shb_test \
  uv run pytest -q \
  tests/test_s23_tester1_adversarial.py tests/test_case_intake_runtime_s23.py \
  -k 'rfi or equal_source_version'
```

Kết quả: **`5 passed, 7 deselected, 0 failed`**.

## Gate targeted hợp nhất

```bash
TEST_DATABASE_URL=postgresql://shb:shb@localhost:55432/shb_test \
  uv run pytest -q \
  tests/test_s23_tester1_adversarial.py \
  tests/test_case_intake.py \
  tests/test_case_intake_config_s23.py \
  tests/test_case_intake_runtime_s23.py \
  tests/test_linked_context_gated_s23.py \
  tests/test_reason_taxonomy_t233.py \
  tests/test_credit_memo_write_gate_t233.py \
  tests/test_credit_memo_prompt_t183.py \
  tests/test_notify_channels.py \
  tests/test_gated.py \
  tests/test_gate_s3_gated_disburse_tester.py \
  tests/test_ops_disburse_gated_t123b.py \
  tests/test_shadow_reviews.py
```

Kết quả cuối trên HEAD freeze: **`118 passed, 0 failed, 5 warnings in 5.56s`**.

| Gate | Evidence quan sát được | Verdict |
|---|---|---|
| Config v1/v2 + startup | v1 defaults giữ; v2 fallback/override; unsafe non-SME kể cả disabled fail; config/taxonomy hỏng chặn trước cleanup/boot; runtime config hỏng trả 503 4-field | PASS |
| Tenant + rollback + idempotency | credential/config slug quyết tenant bất kể query bơm tenant; inbox/link/conversation cùng tenant; unknown tenant/forced DB/mid-TX failure zero partial; retry không nhân conversation; equal-version raw khác trả 409 sau fix | PASS |
| Zero-auto | Product mới `202` chỉ inbox/link/tối đa một empty conversation; SQL zero message/task/card/approval/`shadow_reviews`/tool; wake spy zero | PASS |
| Linked context | JOIN tenant-consistent; JSON đúng sáu allowlisted key; malicious delimiter/external id, party, assignee, document và raw missing không lọt; tenant khác nhận empty block | PASS |
| Tool guard | Cả hai gated action, threshold `0`/cao/default và pending/approved/used đều trả `preassessment_only` trước threshold/receipt/verdict/inner; zero mutation/SSE/receipt replay; non-linked money regressions xanh | PASS |
| Memo write-time | Exact six section/order, source, reason taxonomy; mã thiếu/lạ/trùng/sai order fail 4-field `invalid_credit_memo`, zero card/SSE; proof server-owned; generic document không đổi | PASS |
| RFI | Matrix first/changed/same/duplicate/stale/equal/cancel/complete đúng count; unknown/CIC chỉ sentinel; schedule observer thấy inbox/link đã commit; rollback zero schedule; webhook body đúng hai key và serialized body không có `cic` | PASS |
| Exact case authz | anonymous 401, user/customer 403, tenant B/not-found/malformed 404-hide; success admin cùng tenant trả resource `CaseSummary` trần | PASS |
| Regression S18/S19/D-71 | `test_shadow_reviews.py`, approval doorbell payload/retry và gated money suites đều xanh | PASS |

Targeted FE exact-case bổ sung:

```bash
cd frontend
npm run test -- --run \
  src/App.caseDeepLink.test.tsx \
  src/components/stats/CaseWorkbench.test.tsx
```

Kết quả: **`2 files / 13 tests passed`**. Bao phủ admin exact-fetch/merge/highlight ngoài page 50,
URL giữ qua login, malformed URL zero-fetch, RM/customer zero Tower/list/exact fetch và exact 404
không xóa list độc lập.

## Static / quality gate

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/ruff format --check .
cd ..
git diff --check
```

Kết quả: **ruff PASS; 187 files formatted; `git diff --check` PASS**.

Static checks bổ sung:

- không có route `POST|PUT|PATCH ... start`; operator dùng chat hiện hữu;
- S23 không thêm migration/table, không thêm write `outbox_events`/notification và không thêm
  `INSERT INTO shadow_reviews`; insert ledger duy nhất vẫn ở `orch/store_shadow.py` đường decide;
- `case_intake/service.py` không import orchestrator/wake/MAIN;
- không có fixture/sample dashboard S20 được ghi từ đường intake;
- cleanup test SQL: `external_case_links` và `integration_inbox` prefix `LOS-T1-%` đều `0`.

## Handoff

T23-5 **PASS** tại snapshot sau content-hash fix. Tester-2 vẫn phải ký T23-6/full suite độc lập;
PM chỉ đóng sprint sau khi review riêng evidence của cả hai tester.
