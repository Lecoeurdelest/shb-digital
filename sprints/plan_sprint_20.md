# Sprint 20 — Plan

<!-- LUẬT SỐNG CÒN (đọc trước khi sửa file):
     Plan này là 1 SOURCE OF TRUTH duy nhất cho sprint. Kickoff KHÔNG viết file mới —
     architect EDIT IN-PLACE file này (drift <10% = note inline; 10–30% = edit + History appendix;
     >30% = rewrite), rồi APPEND section `## Kickoff — YYYY-MM-DD` ở CUỐI. Never dispatch từ
     plan stale. Task = spec: mỗi task phải có verification MÁY-KIỂM-ĐƯỢC. Task-id: T20-<n>. -->

**Objective:** Trả đúng hai món đang chờ trong `sprints/CURRENT.md`: biến sổ shadow S18 thành
màn hình pilot có số tổng, breakdown và drill-down ca lệch; đồng thời đặt móng consent có phiên
bản, bằng chứng nội dung và ghi nhận atomic tại cửa form khách. Đây là móng pre-pilot theo D-80,
**không phải DPIA, ý kiến pháp lý hay bằng chứng tuân thủ đầy đủ**.

**Theme:** MÁY ĐO — nhìn thấy độ khớp, ghi được sự đồng ý.

**Historical test reference (không phải fresh kickoff baseline):** `807 pass + 17 skip`
(`531 BE pass + 17 skip`, `276 FE pass`) theo `end_sprint_21.md`. **Fresh kickoff baseline: NOT
RUN** — PM-01 là sai lệch quy trình và không được dựng lại hồi tố. Gate sau thay đổi được tester-2
chạy fresh là `613 BE pass + 17 skip` và `336 FE pass` = **949 pass + 17 skip**; đây là acceptance
gate sau triển khai, không phải baseline trước dispatch.

## Tasks (6, làm theo dependency)

### T20-1 — Contract + API danh sách ca lệch

- **Assignee:** `dev-be` (BA-S20 review contract trước code).
- **Mô tả:** Sửa `docs/CONTRACT.md` **trước**, rồi mở rộng `backend/app/api/stats.py` và
  `backend/app/orch/store_shadow.py` với admin-only, tenant-scoped
  `GET /api/stats/shadow-match/mismatches`. Endpoint chỉ đọc `shadow_reviews` có `match=false` và
  trả page object trần `{items, next_cursor}`; mỗi item gồm đúng `{approval_id, conv_id,
  system_lane, system_recommendation, human_decision, human_reason, decided_at}`. Query được khóa:
  `from` inclusive, `to` exclusive (ISO-8601 có timezone, chuẩn hóa UTC), `lane=green|yellow|red`,
  `limit` mặc định 50/tối đa 200 và `cursor` opaque; sort/keyset ổn định
  `decided_at DESC, approval_id DESC`. Cursor phải bound với tenant + bộ lọc `from/to/lane`, không
  dùng offset và không cho đổi filter giữa hai page; trang cuối trả `next_cursor:null`. Khoảng sai
  (`from >= to`), timestamp/lane/limit/cursor sai trả `400` envelope 4-field. Tenant chỉ lấy từ JWT
  theo D-79, không nhận từ query/body.
  `by_day` đã tồn tại trong endpoint tổng S18 nên không sửa lại. Tuyệt đối không thêm write path
  mới cho `shadow_reviews`; insert hợp lệ duy nhất vẫn là `store_shadow.insert_review()` được gọi
  trong transaction của `approvals.decide`.
- **Dependency:** none.
- **Verification:** Pytest seed ba quyết định comparable (green+approved, red+rejected,
  green+rejected) → aggregate `comparable=3, matched=2, rate=2/3`, mismatch endpoint chỉ trả ca
  green+rejected đúng shape. Test biên `from` inclusive/`to` exclusive, lane, sort, limit, trang
  rỗng và mọi input/cursor sai; fixture hai row trùng `decided_at` chứng minh keyset không trùng/
  sót; đổi filter hoặc tenant khi reuse cursor bị từ chối. Anonymous `401`, RM/customer `403`;
  admin tenant B không thấy row tenant A. Static check trong production source chứng minh không
  có `UPDATE`/`DELETE` ledger và
  không có `INSERT INTO shadow_reviews` ngoài seam `insert_review`; chạy nguyên
  `backend/tests/test_shadow_reviews.py` không sửa kỳ vọng cũ.

### T20-2 — Tower tab “Đối chiếu shadow”

- **Assignee:** `dev-fe`.
- **Mô tả:** Thêm tab admin `shadow` trong `ControlTower.tsx` và component riêng dưới
  `frontend/src/components/stats/`. Bề mặt gồm KPI tổng (matched/comparable, rate hiển thị một chữ
  số thập phân), breakdown theo lane, line theo ngày từ `by_day`, và bảng ca lệch từ T20-1. Tái
  dùng primitive chart/KPI hiện hữu thay vì dựng hệ chart thứ hai; bổ sung type, REST client,
  mock backend và mock data qua cổng `conversationApi`. Row ca lệch là link đúng URL S19
  `/?tab=approvals&approval=<approval_id>`; navigation/reload phải đi lại parser + highlight sẵn
  có, không tạo cơ chế focus mới. Copy trung lập: “tín hiệu hiệu chỉnh”, không gán ca lệch thành
  lỗi của người quyết. `ControlTower` vốn chỉ được mount sau admin gate ở `App.tsx`; giữ ranh đó.
- **Dependency:** T20-1 (contract response chốt).
- **Verification:** Vitest component với aggregate `matched=2, comparable=3` hiển thị `66,7%`,
  đúng lane/day và bảng mismatch; row có exact `href` S19 và App/deep-link integration mở đúng
  phiếu được highlight. App-level test với session RM và customer chứng minh tab không render và
  cả aggregate/mismatch API đều zero-fetch. Empty/loading/error states quan sát được; test
  `ControlTower` và `App.deepLink.test.tsx` hiện hữu pass không sửa; `npm run typecheck` 0 lỗi.

### T20-3 — Contract, wording versioned và ledger consent

- **Assignee:** `dev-be` (PM + BA-S20 soạn/review nội dung; bank data-protection/legal owner là
  người duyệt bắt buộc trước pilot dữ liệu thật).
- **Mô tả:** Contract-first phụ lục consent cho cửa form hiện hữu. Tạo
  `configs/consent/pre-pilot.vi.md` với metadata máy đọc được (`version: v1`, purpose ổn định,
  trạng thái review) và nội dung tối thiểu: bên kiểm soát/xử lý được xác định, mục đích riêng cho
  sơ thẩm shadow/đánh giá tín dụng, loại + nguồn dữ liệu, bên nhận/chia sẻ, thời hạn giữ và cách
  xóa/hủy, quyền/nghĩa vụ chủ thể, kênh rút lại, và xử lý cloud/chuyển dữ liệu nếu có. Đổi chữ bắt
  buộc bump version; runtime tính
  SHA-256 trên đúng bytes hiển thị. File và UI phải ghi rõ pre-pilot, không tuyên bố DPIA/tuân thủ
  đầy đủ; controller, retention, deletion và withdrawal channel không được architect tự đoán —
  phải có owner ngân hàng chốt trước dữ liệu thật.
  Thêm migration Alembic reversible `consent_records` append-only với
  `{id, tenant_id, subject_type, subject_ref, purpose, wording_version, wording_checksum,
  granted, recorded_at, granted_at, actor, source, source_ref}`; `source_ref` giữ `card_id` như
  proof link dạng text (không FK cascade vì consent phải sống lâu hơn card). Check constraints cho
  enum/non-empty/SHA-256 và `granted_at` bắt buộc khi `granted=true`; unique
  `(tenant_id, source, source_ref, purpose)` chặn double-submit. DB trigger từ chối trực tiếp mọi
  `UPDATE`/`DELETE` trên bảng; downgrade chủ động drop trigger rồi drop table. V1 chỉ ghi grant; rút
  lại sau này phải là event row mới, không update row cũ. Không thêm bảng vào production
  `reset_demo` và không tạo API sửa/xóa.
- **Dependency:** none (song song T20-1/T20-2).
- **Verification:** Parser test đọc được v1 và SHA-256 deterministic; đổi một byte làm checksum
  đổi; malformed metadata/unknown purpose fail-closed. Migration up/down sạch trên `shb_test`,
  constraints reject enum/hash/time sai, tenant FK đúng; direct SQL `UPDATE`/`DELETE` bị trigger
  từ chối. Static test/grep production source không có update/delete path; `reset_demo.py` không
  chứa bảng.
  Contract có ownership hệ nguồn LOS/SAHA (consent upstream thuộc trách nhiệm hệ nguồn, envelope
  D-77 v1 không đổi) và checklist hard gate trước pilot thật: bank sign-off + DPIA/đánh giá tác
  động phù hợp; không có câu claim compliance.

### T20-4 — Checkbox bắt buộc + ghi hồ sơ/consent cùng transaction

- **Assignee:** `dev-be` + `dev-fe` (`dev-be` sở hữu atomicity, `dev-fe` sở hữu UX/type/client).
- **Mô tả:** `present_form` đọc wording v1 ở server, snapshot đúng
  `{required:true, purpose:"pre_pilot_shadow_preassessment", wording_version:"v1",
  wording_checksum, content_markdown}` vào form card để FE không copy wording thành source thứ hai.
  `FormCard.tsx` render nguyên snapshot,
  checkbox riêng không pre-tick, và disable nút nộp cho tới khi tick. Client chỉ gửi
  `consent_granted: true`; không được gửi/override version, hash, tenant, subject hoặc actor.
  `form_intake.py` lấy tenant + actor/subject từ claims và lấy wording metadata từ card server-owned;
  thiếu/false/metadata hỏng trả `400 consent_required|consent_wording_invalid` envelope 4-field.
  Trong **cùng transaction hiện hữu**, card flip + customer insert + user link + consent insert
  cùng commit/rollback; consent v1 dùng `subject_type=user`, `subject_ref=claims.sub`,
  `purpose=pre_pilot_shadow_preassessment`, `source=customer_form`, `source_ref=card_id`,
  `granted=true`. Form card legacy thiếu consent metadata fail-closed `409
  consent_wording_unavailable`, không âm thầm cho nộp. Wake MAIN chỉ sau commit.
- **Dependency:** T20-3.
- **Verification:** Pytest thiếu hoặc `false` → đúng error 4-field và không đổi card, không tạo
  customer/user link/consent; `true` → đúng một customer + một consent row có tenant, v1 và SHA
  khớp file/card. Monkeypatch seam consent insert nổ sau customer insert → toàn bộ transaction
  rollback, kể cả card status; retry thành công tạo đúng một row; double-submit sau commit giữ `409`
  và không nhân bản consent. Card chứa snapshot server-side;
  body giả version/hash/tenant bị schema từ chối hoặc bỏ qua, không ảnh hưởng record.
  Vitest chứng minh checkbox mặc định false, nút disabled trước tick, wording/version hiển thị,
  tick mới submit `consent_granted:true`, và form `submitted` vẫn read-only. Test FormCard cũ được
  cập nhật theo contract mới nhưng không xóa các regression hiện hữu.

### T20-5 — Gate API/DB độc lập

- **Assignee:** `tester-1` (không dùng fixture/test do dev viết làm bằng chứng duy nhất).
- **Mô tả:** Kiểm thử đối kháng contract, authz/tenant, filter/pagination mismatch và atomicity
  consent trên `shb_test`; kiểm migration hai chiều trên DB sạch. Tester đồng thời review traceability
  plan của PM: mỗi câu Objective/D-80 phải có gate tương ứng và không được claim DPIA/compliance.
- **Dependency:** T20-1, T20-3, T20-4.
- **Verification:** Một test/evidence độc lập seed đúng ba ca comparable cho `2/3`, chứng minh
  một mismatch và cross-tenant zero-row; curl lỗi cho đủ các invalid query/auth roles. SQL trước/sau
  form thiếu consent và forced-failure chứng minh zero partial write; migration `upgrade → downgrade
  → upgrade` sạch. Báo cáo ghi PASS/FAIL từng invariant và chỉ ra mọi sai lệch plan nếu có.

### T20-6 — Gate UI/E2E + full regression độc lập

- **Assignee:** `tester-2`.
- **Mô tả:** Trên stack local, đặt `auto_approve_threshold_vnd=0`, chạy ba ca xác định:
  green+approved (match), red+rejected (match), green+rejected (mismatch). Mở tab shadow, kiểm
  `66,7%`, lane/day và ca lệch; click row phải mở đúng phiếu S19 với highlight. Đăng ký khách mới:
  chưa tick bị chặn tại UI lẫn API, tick thì hồ sơ + consent row cùng có. Regression S18 receipt
  replay, S19 pending/decided doorbell allowlist, auth role và tenant isolation giữ nguyên. Tester
  review ngược source-of-truth/kickoff của PM trước khi ký gate; PM chỉ chốt sau khi review evidence
  độc lập của cả tester-1 và tester-2.
- **Dependency:** T20-1, T20-2, T20-3, T20-4. T20-5 và T20-6 chạy song song sau dev; không tester
  nào phụ thuộc evidence/sign-off của tester còn lại.
- **Verification:** Curl/SQL/screenshot cho từng bước; đúng ba comparable (không dùng
  `human-review`/yellow trong mẫu số); row click exact-ticket highlight; consent proof chứa version
  + SHA khớp bytes wording. Kết luận sprint phải ghi **PILOT NO-GO** cho tới khi bank data-protection/
  legal owner ký wording/controller/retention/withdrawal và hoàn tất DPIA cùng đánh giá chuyển dữ
  liệu áp dụng; technical gate S20 không thay thế các gate đó. Full suite `>= 807 pass + 17 skip`,
  0 fail; `ruff check`,
  `ruff format --check`, FE tests và `npm run typecheck` sạch; `git diff --check` pass.

---

## History — 2026-08-24 kickoff revision

Draft đầu có 4 task. Kickoff audit xác nhận `by_day` đã có từ S18; `ControlTower` không tự biết
role (admin gate nằm ở `App`); form chưa có đường truyền wording server-owned; consent schema thiếu
proof nội dung; và gate `2/3` chưa khóa ba ca comparable. Plan được sửa mức 10–30%: contract hóa
UTC/keyset/cursor, tách consent foundation khỏi form transaction, thêm checksum/DB trigger/non-claim/legal
owner, và tách hai gate độc lập để đúng roster hai tester.

## Kickoff — 2026-08-24

**Drift since plan:** Baseline tài liệu khớp `end_sprint_21.md` nhưng chưa có fresh suite tại thời
điểm kickoff. Endpoint tổng S18 đã có `by_day`; ledger đã tenant-scoped và insert atomic tại decide.
Frontend admin authorization nằm ở `App.tsx`, không nằm trong `ControlTower.tsx`. Existing form
card lưu field server-side nhưng chưa snapshot wording, và `form-submit` hiện commit customer/card/
user trong một transaction trước khi wake MAIN. Namespace S22 đã có evidence UX riêng, không liên
quan dispatch S20.

**Plan revisions:** T20-1 bỏ việc làm lại `by_day`, thêm contract-first, UTC half-open filters,
page object + filter-bound keyset cursor, stable sort và tenant/auth gates. T20-2 chuyển zero-fetch role test lên App-level và
bắt reuse exact deep-link S19. Consent được tách thành T20-3 (wording/proof/migration/contract) và
T20-4 (BE+FE atomic form), bổ sung SHA-256, server-owned card snapshot, no-client-version, DB
immutability trigger/source proof link và hard non-claim. Gate cũ tách thành T20-5/T20-6 cho hai
tester, khóa đúng ba ca comparable.

**Final task list (chốt dispatch):**

- T20-1 → `dev-be` — contract + mismatch API tenant-scoped, bounded và read-only.
- T20-2 → `dev-fe` — admin-only shadow tab, `66,7%` và exact-ticket drill-down.
- T20-3 → `dev-be` + PM/BA-S20 — wording v1 proof + append-only consent migration; bank sign-off
  vẫn là hard gate ngoài sprint trước pilot dữ liệu thật.
- T20-4 → `dev-be` + `dev-fe` — checkbox bắt buộc và customer/card/consent atomic một transaction.
- T20-5 → `tester-1` — gate API/DB/security/migration độc lập + review traceability PM.
- T20-6 → `tester-2` — gate browser/E2E/full-suite độc lập; PM review cả hai evidence trước chốt.

### History — PM cross-review correction (2026-08-24)

- **PM-01:** kickoff đã dispatch khi chưa chạy fresh full-suite. Mốc `807 + 17 skip` được sửa nhãn
  thành historical reference; không claim hồi tố rằng nó là baseline môi trường lúc dispatch.
  Tester-2 chạy gate fresh sau thay đổi đạt `949 pass + 17 skip`; con số này chỉ là acceptance gate.
- **PM-02:** source-of-truth ban đầu ghi T20-6 phụ thuộc T20-5, trái yêu cầu hai tester độc lập.
  Thực tế root đã cho hai tester chạy song song; dependency được sửa thành cả hai chỉ phụ thuộc task
  dev, rồi PM review hai báo cáo riêng trước khi đóng.
- PM cross-review xác minh độc lập: harness tester-1 `6/6`, migration DB sạch
  `upgrade → downgrade → upgrade`, backend `613 pass + 17 skip`; frontend đủ `336/336` khi chạy
  tuần tự. Default parallel Vitest có timing flake ở `App.test.tsx`, được ghi thành nợ reproducibility
  trong `end_sprint_20.md`, không bị che thành một fresh zero-fail claim của PM.
