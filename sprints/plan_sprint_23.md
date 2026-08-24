# Sprint 23 — Plan

<!-- LUẬT SỐNG CÒN: Plan là source of truth duy nhất; kickoff EDIT IN-PLACE rồi APPEND section
     Kickoff ở cuối. Task-id: T23-<n>. Namespace S22 đã được dùng bởi evidence UX reframe nên gói
     segment mang số S23. D-81/D-82/D-83 được ratify tại kickoff 2026-08-24. Never dispatch từ
     plan stale; task = spec và mỗi task phải có verification MÁY-KIỂM-ĐƯỢC. -->

**Objective:** Mở segment tín chấp bằng config trên cổng case-intake D-77 nhưng giữ fail-closed:
event shadow chỉ tạo inbox/case/link/phiên rỗng cho middle-office, không tự chạy MAIN, không tạo
approval, không gọi tool nhạy cảm và không ghi `shadow_reviews`. Cán bộ phải chủ động bắt đầu qua
chat hiện hữu; context link được tối thiểu dữ liệu. Song song, chuẩn hóa reason-code, RFI và một
counter-offer có tool proof/citation trên dữ liệu nội bộ đã map. Không mở auto-approve cho segment
mới và không giả mapping external→internal.

**Theme:** SEGMENT = CONFIG — nhận segment mới mà không giả vờ đã có approval workflow.

**Fresh kickoff baseline (commit `48fa51b`):** `613 BE pass + 17 skip` và `336 FE pass` =
**949 pass + 17 skip** theo gate đóng S20. Caveat môi trường phải giữ trong mọi báo cáo: clean
`uv sync` chưa kéo optional `pyvi`, nên retrieval test chỉ đạt 613 sau khi test venv có
`pyvi==0.1.1`; PM từng thấy default parallel Vitest timing-flake `334/336` ở `App.test.tsx`, trong
khi tester default và PM serial đều đạt `336/336`, focused đạt `9/9`. Gate S23 phải ghi cả command,
môi trường và mọi lượt flake; không được dùng rerun để xóa evidence lượt đầu.

## Ranh không được nhập nhằng

- `case-intake auto_start: shadow` (D-77/D-81) = durable intake/read-model, **zero orchestration,
  zero approval và zero sensitive-tool execution** tại ingest. `shadow_reviews` S18 = ledger
  counterfactual của một approval đã được người quyết; không có approval thì không có sample.
- Mọi conversation được link từ intake đều là `preassessment_only`, kể cả product `SME_SECURED`.
  Product SME/internal **không link** giữ regression tiền hiện hữu. S23 không dùng dashboard S20
  làm proxy cho segment mới và không tạo approval giả để tăng mẫu số.
- Operator-start là một user message chủ động qua chat hiện hữu. Không thêm start endpoint, không
  gửi message hộ từ ingest và không persist linked context thành message.
- `external_party_id` chỉ là `party_reference`, không phải `customers.id`/internal owner. Full
  tool-backed bốn role trên case LOS và identity adapter external→internal được defer rõ sang S24.
  S23 chỉ cho memo thiếu-mapping/RFI/handover trung thực; `CO-01` chạy riêng trên owner nội bộ C009.
- Không thêm outbox, bảng notification, card type, scoring engine, hot-config UI hay schema event
  D-77 v1. RFI là best-effort sau commit; transport có thể lặp và crash-window có thể mất chuông.

## Roster và ownership

| Vai | Ownership S23 |
|---|---|
| PM | source-of-truth, dependency, review riêng evidence của hai tester trước khi đóng |
| BA-1 | config/tenant/two-shadow/tool-guard + D-81/D-83 contract review |
| BA-2 | taxonomy/memo/counter-offer proof + D-82 bench review |
| Dev-1 | T23-1, T23-2 và backend RFI/tenant/exact-case của T23-3 |
| Dev-2 | taxonomy/memo validator, exact-case FE của T23-3 và T23-4 |
| Tester-1 | T23-5 contract/security/DB độc lập; kiểm ngược PM |
| Tester-2 | T23-6 operator/E2E/bench/full-suite độc lập; kiểm ngược PM |

## Tasks (6, làm theo dependency)

### T23-1 — Config v2 tenant-bound + startup fail-closed + zero-auto ingest

- **Assignee:** `dev-1` (BA-1 chốt contract trước code).
- **Mô tả:** Sửa `docs/CONTRACT.md` §11a **trước**. Schema YAML v2 giữ source-level field v1 và
  thêm bắt buộc `tenant_slug` cùng `product_profiles` map theo product; mỗi entry khóa
  `{workflow_profile, auto_start}`. Product không có override fallback tuyệt đối về
  `workflow_profile/auto_start` source-level như v1. Parser v1 vẫn đọc nguyên, mặc định
  `tenant_slug=bank-digital-default` và `product_profiles={}`. V2 mở `UNSECURED_CONSUMER` và
  `UNSECURED_PUBLIC`; code bắt mọi product ngoài `SME_SECURED` resolve đúng
  `preassessment_only + shadow`, cấu hình khác raise `CaseIntakeConfigError` an toàn. Một source
  config thuộc đúng một tenant; same alias provisioning cho nhiều tenant defer, không đổi unique
  key DB trong sprint này.

  `tenant_slug` chỉ đến từ config đã khớp service credential, không body/query. Lifespan gọi
  `load_case_intake_config()` sau `validate_runtime_security()` nhưng trước `registry.reset_all`,
  orphan cleanup và `main_session.boot`. Loader chỉ validate cấu trúc/syntax; tenant slug được
  resolve thành đúng `tenant_id` trong transaction ingest. Slug không tồn tại hoặc DB lỗi trả
  `503 case_intake_not_ready` và rollback, không biến DB availability thành startup blocker.
  Mọi lookup/lock/insert/update inbox, link và conversation nhận cùng `tenant_id`;
  `_create_conversation` ghi tenant tường minh. Runtime reload config hỏng sau boot vẫn `503`.
  Ingest giữ zero wake MAIN/message/task/card/approval/shadow/tool call. Ratify D-81.
- **Dependency:** none.
- **Verification:** Contract test parse fixture v1 byte-for-behavior và v2 fallback/override;
  thiếu/sai `tenant_slug`, product profile unsafe, product ngoài allowlist hoặc non-SME mode khác
  `preassessment_only+shadow` fail 4-field/safe startup error. `with TestClient(app)` + unsafe YAML
  raises trước mock cleanup/boot (cả hai zero-call); runtime invalid trả `503`. Fixture hai tenant
  chứng minh credential source A chỉ ghi tenant từ slug A dù body/query bơm tenant B; conversation,
  link và inbox cùng tenant. Unknown tenant/forced DB failure → zero partial write. Event mới trả
  `202` và atomically tạo inbox+link+tối đa một conversation nhưng SQL/static spy chứng minh zero
  message/task/card/approval/`shadow_reviews`/tool/wake. Restart/retry không nhân conversation.

### T23-2 — Explicit operator-start + linked context allowlist + tool-layer guard

- **Assignee:** `dev-1` (BA-1 review choke-point).
- **Mô tả:** Contract-first bổ sung §11e/runbook: cán bộ admin mở phiên đã link rồi chủ động gửi
  user message qua chat hiện hữu; ingest không gửi hộ và không có API start mới. MAIN system prompt
  ở lượt chủ động gọi helper đọc `external_case_links` bằng `conversation_id + tenant_id`, JOIN
  nhất quán `e.conversation_id=c.id AND e.tenant_id=c.tenant_id`, không persist context thành
  message. Context chỉ có `{source_system, external_case_id_or_case_id, product_code,
  loan_amount_vnd, missing_field_codes, data_as_of}`. Chỉ inject raw `external_case_id` nếu qua
  identifier regex contract; nếu không dùng internal case UUID/placeholder. Missing fields được
  normalize thành code allowlist; không raw `party_reference`, assignee, document refs/content hay
  inbox payload. Serialize JSON trong delimiter và dặn model mọi value là data, không instruction.

  Guard code đặt **bên trong `_gated_txn`, ngay sau mở cursor**, trước cross-owner, advisory lock,
  receipt/idempotency branches và `gated_decision`. Nếu conversation có link tenant-consistent,
  cả `disburse` lẫn `ops_disburse` trả đúng error 4-field `preassessment_only`, không approval/card/
  receipt/tool execution hay mutation — bất kể product, threshold `0`/cao hoặc đã có row pending/
  approved/used. Conversation SME/internal không link giữ nguyên behavior. D-81 là rào tầng tool,
  prompt chỉ hỗ trợ hành vi.
- **Dependency:** T23-1.
- **Verification:** Chờ sau ingest vẫn zero message/task/card/approval; chỉ explicit admin chat mới
  tạo user message/turn. Tenant B không đọc context tenant A; malicious external id/missing code/
  document/party fields không xuất hiện trong prompt và raw value không thoát delimiter. Direct call
  hai gated actions trên linked conversation bị chặn trước mọi branch: test threshold `0`, threshold
  cao và fixture pending/approved/used receipt đều zero side effect/không replay receipt. Spy
  `gated_decision`, tool inner, approval/card insert đều zero-call. Non-linked SME fixtures giữ
  money/idempotency regression. Restart/retry không tự start và không tạo phiên thứ hai.

### T23-3 — Taxonomy runtime/write-time + RFI D-83 + exact-case deep-link

- **Assignee:** `dev-1` (RFI/API/DB) + `dev-2` (taxonomy validator/prompt + exact-case FE); BA-1
  review RFI và BA-2 review memo taxonomy.
- **Mô tả:** Sửa `docs/CONTRACT.md` trước cho ba seam:

  1. Tạo `configs/reason-codes.yaml` version 1 với group allowlist `HS_THIEU`, `CIC`, `THU_NHAP`,
     `PHAP_LY`, `TSDB`; gồm mã bắt buộc `HS_THIEU_DINH_DANH_NOI_BO`. Loader reject schema/group/id
     sai và duplicate; checksum dạng `sha256:<64hex>` trên canonical JSON của YAML đã parse/sort,
     không hash raw bytes. Lifespan load taxonomy sau runtime-security, cùng cửa T23-1 và trước
     registry reset/cleanup/boot. Allowed taxonomy được đưa vào prompt catalog runtime.
  2. `common_tools.present_tool` gọi validator **trước** `store.insert_card` chỉ khi
     `{type:'document', title:CREDIT_MEMO_TITLE}`. Bắt đúng sáu section theo đúng order; item thứ
     năm có `reason_codes` nonempty/unique và mọi id tồn tại. Server overwrite/inject
     `items[4].reason_taxonomy={version:1,checksum}`. Thiếu/lạ/sai order trả tool error 4-field
     `invalid_credit_memo`, `retryable:true`, zero DB/SSE. Generic document không bị đổi.
  3. Normalize `missing_fields` thành sorted unique safe codes; unknown raw code collapse thành một
     sentinel `additional_information`, không reject intake và không forward raw. Dưới case lock,
     service so prior normalized set với set mới. Chỉ receipt `accepted`, non-cancel, set mới nonempty
     **và khác prior set** tạo internal `rfi_candidate`; duplicate/stale/equal-version/new-version
     cùng set/complete đều không tạo. Transaction commit xong service trả internal candidate; API
     chỉ serialize receipt public rồi mới schedule best-effort. Webhook generic có **đúng hai key**
     `{missing_fields:[codes], deep_link:'<app>/?tab=cases&case=<link UUID>'}`; không event kind,
     amount/name/external id/party/CIC/document/content. App schedule tối đa một lần mỗi changed set;
     retry transport có thể trùng và crash sau commit có thể mất chuông. Không outbox/bảng mới.

  Thêm `GET /api/cases/{id}` admin-only trả cùng `CaseSummary`, tenant khác 404-hide. Public URL
  exact `/?tab=cases&case=<uuid>`; parser chỉ nhận root, đúng hai unique params, không hash/extra.
  Unauthenticated giữ URL qua login; admin mount tab `assessments`, exact fetch rồi merge/highlight
  target kể cả ngoài page 50. RM/customer không mount Tower và zero exact-case fetch. Approval
  deep-link S19/S20 giữ nguyên. Ratify D-83 và phần taxonomy của D-82.
- **Dependency:** T23-1 (song song T23-2).
- **Verification:** Loader tests malformed version/group/id/duplicate và deterministic checksum;
  lifespan taxonomy unsafe chặn trước cleanup/boot. `present` memo đúng được lưu với server-owned
  taxonomy proof; mọi mã lạ/missing/duplicate/sai section/order fail `invalid_credit_memo`, zero
  card/SSE; generic document regression pass. Matrix RFI first/new-changed/same/duplicate/stale/
  equal/cancel/complete chứng minh schedule count `1/1/0/0/0/0/0/0`; forced DB rollback zero
  schedule. Webhook body assert exact two keys và absence toàn bộ field cấm; unknown chỉ còn sentinel.
  API exact-case anonymous `401`, RM/customer `403`, tenant B/not-found `404`; FE malformed URL và
  non-admin zero-fetch, admin target ngoài page 50 exact-fetch + highlight. Regression
  `test_notify_channels.py`, approval doorbell payload và approval deep-link không đổi.

### T23-4 — Một counter-offer có reassessment + tool/wiki proof

- **Assignee:** `dev-2` (BA-2 review prompt/checker; không sửa vỏ/card/FE).
- **Mô tả:** Contract-first khóa counter-offer v1 trong item 5 của memo sáu mục: tối đa một offer,
  có structured proof song song human-readable content. Offer chỉ hợp lệ khi `product_suggest` tại
  **đúng proposed amount** trả candidate eligible, `credit_assess` chạy lại **cùng amount/type** trả
  eligible, và retrieval có citation wiki active cho mô tả + hiệu lực. Lãi/phí/hạn mức/kỳ hạn chỉ
  lấy từ `product_suggest`/catalog tool; wiki không là nguồn số, không được model nhớ/bịa. Không có
  đủ ba proof thì không sinh offer và checker fail nếu card vẫn claim.

  Fixture deterministic `CO-01` dùng owner nội bộ C009: `credit_assess(C009,600m,consumer)`
  ineligible DSCR `1.179`; `product_suggest(C009,600m,consumer)` có `eligible=[]`; thử candidate
  500m phải gọi `product_suggest` → P001 eligible và `credit_assess(C009,500m,consumer)` → eligible
  DSCR `1.371`; citation bắt buộc `goi-tieu-dung-chuan` + `qd-2026-laisuat`. Checker query **fresh
  card + tool_calls DB theo conversation**, không đọc response markdown bị truncate. `CO-01` chỉ là
  owner nội bộ đã map, không được kể thành case LOS. Ratify D-82.
- **Dependency:** T23-3.
- **Verification:** Script/checker tạo fresh conversation/card và đối chiếu tool_calls input/output:
  amount/type của `product_suggest` và reassessment khớp 500m/consumer, cả hai eligible, số offer
  đúng một, mọi số map về tool result, hai wiki id active hiện trong proof và reason code thuộc
  taxonomy. Negative fixtures thiếu candidate, reassessment, same-amount, eligible result hoặc một
  citation → zero offer hoặc checker FAIL. `XD-01` giữ title/sáu mục/sources; generic document/card
  renderer và one-role fixture không bị ép counter-offer.

### T23-5 — Gate contract/security/DB độc lập

- **Assignee:** `tester-1` (không dùng test dev làm bằng chứng duy nhất).
- **Mô tả:** Kiểm đối kháng config v1/v2/startup, tenant binding/idempotency, zero-auto/tool guard,
  memo write-time validator, RFI minimization/dedup/post-commit và exact-case authz. Review ngược PM:
  hai nghĩa shadow phải tách, không task nào dùng approval-shadow/dashboard làm proxy intake-shadow.
- **Dependency:** T23-1, T23-2, T23-3. Không phụ thuộc T23-6/sign-off tester-2.
- **Verification:** Evidence độc lập cho invalid config/taxonomy không boot; unknown tenant rollback;
  credential tenant A không ghi/đọc tenant B. Product mới ingest `202` nhưng zero MAIN/task/card/
  approval/shadow/tool; direct gated calls ở đủ threshold/existing-state zero side effect. Memo mã
  lạ zero write; RFI exact two-key một lần cho changed set và zero trước commit; exact-case tenant
  B 404. Static import/write-path check chứng minh không start endpoint/outbox/table/sample S20 mới.
  Báo cáo PASS/FAIL từng invariant và mọi divergence của plan PM.

### T23-6 — Gate operator/E2E + CO-01/full regression độc lập

- **Assignee:** `tester-2`.
- **Mô tả:** Trên stack local, ingest segment mới → exact-case/RFI → operator chủ động mở linked
  conversation và gửi chat. Vì chưa có external→internal mapping, output hợp lệ là RFI/handover hoặc
  memo sáu mục trung thực với `HS_THIEU_DINH_DANH_NOI_BO`; không bắt live model bịa full bốn-role,
  DSCR/product claim hay counter-offer cho case LOS. Chạy counter-offer **riêng** bằng C009 `CO-01`
  nội bộ. SQL segment mới phải zero approval/`shadow_reviews`/disbursement và không fake mapping.
  Regression D-77/SME non-linked, S18 ledger, S19 doorbell/deep-link và S20 dashboard/consent giữ
  nguyên. Tester review source-of-truth PM độc lập; PM review riêng cả hai tester sau khi cùng nộp.
- **Dependency:** T23-1, T23-2, T23-3, T23-4. Không phụ thuộc T23-5/sign-off tester-1; hai tester
  chạy song song sau dev.
- **Verification:** Curl/SQL/screenshot exact case/RFI + explicit operator turn; linked context chỉ
  allowlist và mọi output reason code hợp lệ. Memo thiếu mapping nếu có phải đúng sáu section và
  zero unsupported numeric/product claim. `CO-01` fresh card/tool_calls DB chứng minh P001 500m,
  reassessment DSCR `1.371`, exact two citations và tối đa một offer. SQL zero approval/shadow/
  disbursement/fake owner mapping cho segment. Full BE/FE ít nhất **949 pass + 17 skip**, 0 failure
  ở lượt ký; ruff/format/typecheck/`git diff --check` sạch. Báo cả precondition `pyvi` và mọi default
  parallel Vitest flake/rerun/serial result, không xóa lượt fail khỏi evidence.

---

## History — rewrite 2026-08-24 (>30% drift)

Draft ban đầu mang số S22 và gate `case-intake shadow → 4 role → approval decision →
shadow_reviews → dashboard S20`. Repo audit chứng minh chuỗi đó trái D-77: intake shadow hiện chỉ
tạo mapping/conversation, không chạy MAIN, tạo approval hay tool call; ledger S18 cũng không có
product code để chứng minh segment. Namespace `sprints/evidence/s22-ux-reframe/` đã tồn tại. Vì vậy
plan đổi thành S23 và rewrite: tách hai nghĩa shadow, thêm explicit operator-start + tool-layer
profile guard, contract hóa RFI/exact-case và loại dashboard S20 khỏi gate segment.

## Kickoff — 2026-08-24

**Drift since plan:** S20 đã đóng ở `48fa51b`; fresh current gate là `949 pass + 17 skip` với nợ
môi trường `pyvi` và timing-flake Vitest đã ghi trên. Audit BA tại commit này tìm tám seam draft còn
thiếu: chưa bind tenant từ service source; startup chưa validate config; context chưa xử lý text
external độc hại; guard chưa khóa trước mọi branch gated; memo chưa validate ở write-time; RFI chưa
khóa changed-set/post-commit/two-key payload; case chưa có exact deep-link; và CO-01 chưa khóa
same-amount reassessment/tool-owned numbers. Không có production drift nào cho phép nới zero-auto.

**Plan revisions:** Ratify D-81/D-82/D-83. T23-1 thêm `tenant_slug`, v2 product profile và thứ tự
startup; tenant DB existence kiểm trong ingest, không startup. T23-2 khóa explicit start, context
allowlist/delimiter và guard đầu `_gated_txn` cho mọi linked conversation. T23-3 thêm taxonomy
startup + memo write seam, RFI changed-set best-effort và exact-case URL/API. T23-4 sửa CO-01 thành
C009 `600m fail → 500m P001 + credit reassessment pass`, tool sở hữu số và wiki chỉ citation.
External identity/full LOS four-role defer S24. T23-5/T23-6 bỏ dependency tester-to-tester và chạy
song song; PM review hai evidence riêng.

**Final task list (chốt dispatch):**

- T23-1 → `dev-1` — contract/config v2 tenant-bound + startup/static fail-closed + zero-auto ingest.
- T23-2 → `dev-1` — explicit operator-start, linked context allowlist và sensitive-tool guard.
- T23-3 → `dev-1` + `dev-2` — taxonomy/write-time memo + D-83 RFI/exact-case contract/API/FE.
- T23-4 → `dev-2` — D-82 counter-offer C009 có same-amount tool reassessment + active wiki proof.
- T23-5 → `tester-1` — contract/security/DB adversarial gate độc lập + review PM.
- T23-6 → `tester-2` — operator/E2E/CO-01/full regression gate độc lập + review PM.

### History — PM cross-review closure (2026-08-24)

- **Implementation verdict: PASS.** T23-1→T23-6 đều đạt acceptance sau freeze cuối. Chữ ký
  regression là **677 BE pass + 17 skip + 348 FE pass = 1.025 pass + 17 skip**, cao hơn
  baseline `949 + 17 skip`. Lượt FE default-parallel trước chữ ký đạt `346/348` do hai
  timing-flake đã biết trong `App.test.tsx`; lượt serial ký đạt `348/348`. Không dùng
  rerun để xóa evidence fail.
- **Defect history được giữ nguyên:** Tester-1 bắt lượt đầu `1 failed, 4 passed` do
  equal `source_version` băm `missing_fields` sau normalize, làm hai raw payload khác nhau bị
  coi là duplicate. Root chuyển identity hash về raw case; regression rerun `23 passed` và gate
  targeted cuối `118 passed`. Privacy RFI cũng được harden để chuỗi/mã CIC chỉ còn
  sentinel an toàn.
- **Evidence T23-6 được remediated trước close:** báo cáo đầu có HTTP/SQL và FE
  tests nhưng thiếu literal browser screenshot mà plan yêu cầu. PM giữ gate mở; Tester-2
  bổ sung curl + Selenium trên stack local, chứng minh exact RFI target active/focused và explicit
  operator turn không có assistant/model output. Hai ảnh đã được PM mở kiểm trước
  khi ký.
- **Process verdict: PASS.** Dispatch dùng plan kickoff `825776d`; hai tester chỉ phụ thuộc task
  dev, chạy độc lập trên DB `:55432` và `:56432`, review ngược source-of-truth riêng. PM
  chờ cả hai evidence, review riêng và không lặp PM-01/PM-02 của S20.
- **Non-claims/defer:** không có provider credential nên không chạy/claim live-model; CO-01 là
  owner nội bộ C009 với tool/card/audit proof, không phải case LOS. External identity, full LOS
  four-role và adapter nguồn defer S24. Optional `pyvi` và Vitest timing-flake vẫn là nợ môi
  trường. Theo D-80, pilot dữ liệu thật vẫn **NO-GO**.
