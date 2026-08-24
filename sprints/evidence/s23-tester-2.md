# Sprint 23 — evidence Tester-2

**Ngày:** 2026-08-24
**Phạm vi:** T23-6 operator/E2E, exact-case/RFI, CO-01, full regression và kiểm tra ngược PM.
**Snapshot ký:** base commit `825776d`, worktree S23 được root freeze trước full suite cuối.
**DB độc lập:** PostgreSQL 15 `shb_test` tại `127.0.0.1:56432`; không dùng DB Tester-1 `:55432`.

## Kết luận

- **Implementation: PASS.** Final gate đạt **677 BE + 348 FE = 1.025 pass, 17 skip, 0 fail**,
  cao hơn baseline S20 `949 pass + 17 skip`. Segment intake giữ zero-auto/zero fake mapping; RFI và
  linked context tối thiểu dữ liệu; exact-case tenant-scoped; tool guard chặn đường tiền.
- **CO-01: PASS trên tool/DB thật.** Fresh internal conversation C009 có đúng chuỗi audit
  `600m fail -> 500m/P001 eligible -> same-amount credit reassessment eligible`, hai wiki citation
  active và checker đọc card + `tool_calls` đạt.
- **PM/source-of-truth: PASS.** Plan tách đúng hai nghĩa shadow, defer external identity sang S24,
  cho hai tester chạy độc lập và giữ nguyên caveat môi trường/rerun.
- **Live model: không chạy; browser local: PASS.** Không có `ANTHROPIC_API_KEY`, `ZAI_API_KEY`
  hoặc `OPENAI_API_KEY`; Tester-2 không dùng model để tạo bằng chứng giả. Operator boundary ban đầu
  được kiểm qua API/SQL thật với room runner no-op; CO-01 dùng trực tiếp deterministic tool
  functions. Remediation sau sign-off đã khởi động API/FE local và chụp exact-case cùng explicit
  operator turn bằng Selenium/Chrome, hoàn toàn không gọi provider.

## Audit ngược PM

Nguồn đọc: `sprints/plan_sprint_23.md`, D-81/D-82/D-83, `docs/CONTRACT.md` §11/§13,
`sprints/CURRENT.md` và `sprints/ROADMAP.md`.

| Invariant | Đánh giá | Bằng chứng |
|---|---|---|
| Một source of truth, kickoff không stale | PASS | Plan được rewrite/append kickoff 2026-08-24 trước dispatch; namespace đổi S22 -> S23 vì S22 đã có evidence UX. |
| Hai nghĩa shadow tách biệt | PASS | Objective/ranh/T23-1/2/5/6 đều khóa intake-shadow = durable empty link; không approval, không `shadow_reviews`, không dùng dashboard S20 làm proxy. |
| Không giả external identity | PASS | `external_party_id` chỉ là party reference; mapping/full LOS four-role defer S24; CO-01 ghi rõ là owner nội bộ C009. |
| Rào tiền ở tool | PASS | T23-2 yêu cầu chặn cả `disburse|ops_disburse` trước threshold/receipt/verdict/write; prompt không được coi là phanh. |
| RFI/counter-offer có proof máy kiểm | PASS | D-83 khóa changed-set/post-commit/two-key/no-CIC; D-82 khóa taxonomy write-time và candidate + same-amount reassessment + active wiki proof. |
| Hai tester độc lập | PASS | T23-5 và T23-6 cùng phụ thuộc dev tasks, không phụ thuộc/sign-off lẫn nhau; PM phải review riêng cả hai. |
| Baseline/caveat trung thực | PASS | Plan giữ `949 + 17 skip`, nợ optional `pyvi` và timing-flake Vitest; cấm dùng rerun để xóa lượt fail. |

**PM verdict: PASS.** Không phát hiện lỗi quy trình tương tự PM-01/PM-02 của S20.

## E2E segment độc lập — API + SQL trên DB 56432

Kịch bản cuối sau full suite dùng case `233cbe3a-f906-4655-aae1-b642af03ad75`, conversation
`0117a0d1-6235-4cb7-ae32-59047c93039e`:

1. POST CaseEventV1 `UNSECURED_CONSUMER`, cố tình truyền query tenant khác, raw external id chứa
   delimiter, `external_party_id=C009`, assignee/document secret và missing fields gồm
   `identity_document`, `cic_consent`, raw CIC note.
2. API trả `202 accepted`; config credential vẫn bind tenant mặc định. SQL ngay sau ingest:

   ```text
   internal_application_id = NULL
   party_reference = C009
   missing_fields = [additional_information, identity_document]
   messages/tasks/cards/tool_calls/approvals/shadow_reviews = 0/0/0/0/0/0
   ```

3. `GET /api/cases/<id>` với admin cùng tenant trả `200` đúng case. Explicit admin chat qua endpoint
   hiện hữu trả `202` và gọi room runner đúng một lần. Sau hành động này SQL chỉ có **một user
   message**; task/card/tool/approval/shadow vẫn bằng 0.
4. Linked prompt JSON có đúng sáu key:

   ```json
   {
     "data_as_of": "2026-08-24T10:00:00+00:00",
     "external_case_id_or_case_id": "233cbe3a-f906-4655-aae1-b642af03ad75",
     "loan_amount_vnd": 600000000,
     "missing_field_codes": ["additional_information", "identity_document"],
     "product_code": "UNSECURED_CONSUMER",
     "source_system": "los"
   }
   ```

   Không có raw external id/delimiter, `C009`, assignee, document ref, `cic_consent` hay raw CIC.
5. Direct `ops_disburse(APP01, 600m)` trên linked conversation trả
   `code=preassessment_only`; tổng `disbursements` trước/sau giữ **2 -> 2**.
6. Generic RFI body có đúng hai key và không chứa chuỗi `cic`:

   ```json
   {
     "missing_fields": ["additional_information", "identity_document"],
     "deep_link": "https://bank.example/?tab=cases&case=233cbe3a-f906-4655-aae1-b642af03ad75"
   }
   ```

Đây là ASGI HTTP + SQL thật, chỉ thay room runner bằng no-op để không gọi provider ngoài. Vì không
có model output, gate không claim DSCR/product/counter-offer hay memo bốn-role cho case LOS.

## CO-01 — fresh deterministic tool/card/audit proof

Fresh internal conversation: `ff59aed3-85a9-421c-8c27-8d2329eb6cff`; SQL xác nhận
`external_case_links=0`, nên đây **không** phải case LOS.

Chuỗi tool thật đã chạy và persist vào `tool_calls` trước card:

```text
credit_assess(C009, 600000000, consumer) -> ineligible, DSCR 1.179
product_suggest(C009, 600000000, consumer) -> eligibleOptions=[]
product_suggest(C009, 500000000, consumer) -> P001 active/eligible
credit_assess(C009, 500000000, consumer) -> eligible, DSCR 1.371
wiki_lookup(goi-tieu-dung-chuan) -> active
wiki_lookup(qd-2026-laisuat) -> active
```

Tester cố tình bơm `reason_taxonomy.version=999/checksum=forged`; write-time validator overwrite
thành server proof:

```text
version=1
checksum=sha256:cb6e400e1fe69eb7bd551c73ec6b3000c5d377d7a026ea11d1c178605fe13c41
```

Lệnh machine checker đọc fresh card + audit DB:

```bash
cd backend
DATABASE_URL=postgresql://shb:***@localhost:56432/shb_test \
  .venv/bin/python ../bench/check_counter_offer.py \
  --conv-id ff59aed3-85a9-421c-8c27-8d2329eb6cff
```

Kết quả: `ok=true`, `product_id=P001`, `proposed_amount_vnd=500000000`, `loan_type=consumer`, đúng
hai wiki citation và một counter-offer. Mọi numeric term map về eligible option của
`product_suggest`.

Negative checker:

```bash
DATABASE_URL=postgresql://shb:***@localhost:56432/shb_test \
TEST_DATABASE_URL=postgresql://shb:***@localhost:56432/shb_test \
  .venv/bin/pytest -q tests/test_counter_offer_checker_t234.py
```

Kết quả **8 passed**: thiếu candidate, thiếu reassessment, sai amount, reassessment ineligible,
thiếu citation, sửa numeric term hoặc claim offer không có structured object đều làm checker FAIL.

## Focused gates

```bash
TEST_DATABASE_URL=postgresql://shb:***@localhost:56432/shb_test \
  .venv/bin/pytest -q \
  tests/test_case_intake_config_s23.py \
  tests/test_case_intake_runtime_s23.py \
  tests/test_linked_context_gated_s23.py \
  tests/test_reason_taxonomy_t233.py \
  tests/test_credit_memo_write_gate_t233.py \
  tests/test_counter_offer_checker_t234.py \
  tests/test_credit_memo_prompt_t183.py tests/test_prompt_catalog.py
```

Kết quả đầu: **64 passed**. Sau hai hardening do Tester-1/root bắt trong lúc gate, Tester-2 rerun
trên patch mới:

- raw equal-version/content-hash + D-77/tool/counter-offer: **41 passed**;
- RFI/CIC privacy + linked/tool/D-71: **32 passed**.

Focused FE:

```bash
npm run test -- --run \
  src/App.caseDeepLink.test.tsx \
  src/components/stats/CaseWorkbench.test.tsx \
  src/api/client.cases.test.ts
```

Kết quả: **3 files / 15 tests passed** — exact fetch/merge/highlight ngoài page 50, URL giữ qua
login, malformed URL zero-fetch, non-admin zero Tower/list/exact fetch và API client đúng path.

## Full regression và quality gate

Backend venv có `pyvi==0.1.1`. Đây vẫn là optional prerequisite được cài riêng vào test venv;
clean `uv sync --frozen` chưa đảm bảo kéo nó, đúng caveat kế thừa S20.

```bash
cd backend
TEST_DATABASE_URL=postgresql://shb:***@localhost:56432/shb_test .venv/bin/pytest
```

Final frozen snapshot: **694 collected; 677 passed, 17 skipped, 0 failed in 78.23s**. Có 156
Starlette/TestClient deprecation warnings, không có test failure. Hai lượt full trước đó cũng xanh
nhưng không dùng làm chữ ký vì root đã harden equal-version rồi RFI/CIC giữa các lượt; Tester-2
giữ log và chạy lại full sau khi root xác nhận freeze.

Frontend default-parallel, đúng yêu cầu phải giữ evidence flake:

```bash
npm run test
```

Lượt đầu: **46 files; 346 passed, 2 failed / 348**. Hai lỗi đều ở `src/App.test.tsx`: một timeout
5 giây và một assertion trạng thái chưa kịp hoàn tất — cùng timing-flake PM đã ghi từ S20.

Lượt ký serial:

```bash
npm run test -- --maxWorkers=1
```

Kết quả: **46 files / 348 tests passed, 0 failed in 52.24s**.

Các gate còn lại:

| Lệnh | Kết quả |
|---|---|
| `.venv/bin/ruff check .` | PASS — `All checks passed!` |
| `.venv/bin/ruff format --check .` | PASS — `187 files already formatted` |
| `git diff --check` | PASS |
| `npm run typecheck` | PASS, gồm SDK typecheck |
| `npm run build` | PASS reference + SDK ESM/CJS/standalone; warning chunk >500 KB không chặn |
| `npm run lint` | exit 0; 6 warning Fast Refresh có sẵn ở `controlTowerAudit.tsx`, 0 error |

Tổng chữ ký: **677 BE + 348 FE = 1.025 pass + 17 skip**, tăng 76 test pass so baseline
`949 + 17 skip`.

## Static boundary và giới hạn

- Không có start endpoint mới; intake service không import/call MAIN/orchestrator.
- Không có migration/table/outbox/notification ledger mới trong S23; không có write
  `shadow_reviews` từ intake.
- Không có đường gán `external_party_id`/`party_reference` sang `internal_application_id`.
- Generic exact-case/card regressions, approval doorbell D-71, S18 shadow ledger, S19 deep-link và
  S20 consent/dashboard đều nằm trong full suite xanh.
- Chưa có external identity adapter/full LOS four-role; đây là defer có chủ đích S24, không phải
  claim đã hoàn thiện pilot dữ liệu thật.

## Sign-off Tester-2

- **T23-6 / implementation:** PASS trên frozen snapshot.
- **PM/source-of-truth:** PASS.
- **Live provider:** NOT RUN, có caveat rõ; không làm giả output.
- **Local browser screenshot:** PASS sau remediation, xem phụ lục dưới.
- **Pilot dữ liệu thật:** vẫn NO-GO theo D-80 cho tới bank/legal/data-protection sign-off và các
  đánh giá tác động áp dụng.

## Phụ lục remediation — literal curl + browser local

Sau yêu cầu cross-review của PM, Tester-2 khởi động đúng stack local, không sửa production/test:

```bash
cd backend
DATABASE_URL=postgresql://shb:***@localhost:56432/shb_test \
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

cd frontend
VITE_USE_MOCK_API=false npm run dev -- --host 127.0.0.1 --port 5173
```

Literal curl bằng cookie admin thật:

```text
GET /api/cases/233cbe3a-f906-4655-aae1-b642af03ad75 -> 200
GET /?tab=cases&case=233cbe3a-f906-4655-aae1-b642af03ad75 -> 200
```

Resource exact trả đúng `source_system=los`, `case_status=missing_information`,
`missing_fields=[additional_information, identity_document]` và conversation
`0117a0d1-6235-4cb7-ae32-59047c93039e`.

Selenium `4.47.0` + Google Chrome `150.0.7871.128` đăng nhập qua UI thật tại chính RFI URL. Máy
kiểm quan sát:

```text
URL=http://127.0.0.1:5173/?tab=cases&case=233cbe3a-f906-4655-aae1-b642af03ad75
ACTIVE_TAB=Cơ sở sơ thẩm
ROW_CLASS=casewb__row casewb__row--active casewb__row--focused
```

Ảnh cho thấy target ngoài danh sách mặc định được exact-fetch, chọn và viền highlight; detail nói
`Thiếu thông tin`, `Mã hồ sơ nội bộ: Chưa liên kết`, next action bổ sung thông tin và có nút
`Mở phiên xử lý`:

- [Exact-case RFI target được highlight](s23-exact-case-rfi-tester2.png)

Từ chính detail đó, browser bấm `Mở phiên xử lý`; Workspace tải đúng title
`Phiên xử lý sơ thẩm` và user message đã ghi bởi explicit operator, không có assistant/model output:

```text
Bắt đầu rà soát; thiếu mapping thì chỉ yêu cầu bổ sung.
```

- [Explicit operator turn trong linked conversation](s23-explicit-operator-turn-tester2.png)

Hai PNG được Selenium ghi trực tiếp, lần lượt `168333` và `54403` byte; Tester-2 đã mở lại cả hai
để kiểm tra nội dung/viewport. Phụ lục này đóng deviation screenshot mà không thay đổi caveat
provider và không biến case LOS thành counter-offer/DSCR claim.
