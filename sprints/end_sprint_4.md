# Sprint 4 — End

**Theme:** Control Tower + trace (deliverable #4) + tương tác sub (F1/F2a D-43) + compare (deliverable
#5 tối giản) + đóng nợ S3 (loop-edge bound, 2-card-trùng).
**Commit:** dcf3ac3 (T4-0+T4-1) · ad4f1b1 (T4-2/3/4) · a9e931c (T4-5) · be8560d (provider c) ·
5da3667 (seed-reset + wrap) · 13860c2 (T4-6 + dedupe) · {{đóng — điền}}

## Kết quả từng task

### T4-0 — done (loop-bound guard B — HẠ NGOẠI LỆ S3)
- **Bằng chứng:** cột exec_attempts + MAX=3, peek_grant/claim_exec_attempt atomic, vượt trần → exec_failed
  + signal deterministic → MAIN báo "lỗi bền cần người" (không cược model). Gate tester 6/6 live, log
  guard-B "lần 1,2,3 → exec_failed" đúng trần. Migration round-trip immutable-safe (architect tự chạy).
- **Deviation:** none. Ngoại lệ S3 loop-edge → BOUND, gỡ khỏi sổ.

### T4-1 — done (tool_calls audit + SSE toolcall — nền deliverable #4)
- **Bằng chứng:** bảng tool_calls append-only (source-check test 0 UPDATE/DELETE) + persist input+output
  (ToolResultBlock match) + SSE toolcall {id,task_id,tool,summary,cost} + GET /api/audit filter. Gate
  tester 4/4 đường thật. D-48: +conv_id (main task_id=null cần filter) + id (FE dedup) + cost=null
  per-tool (SDK chỉ per-turn — không giả số).
- **Deviation:** D-48 (signoff).

### T4-2 — done (F1 trace UI — D-43 user đặt)
- **Bằng chứng:** SSE thinking {task_id|null, text} live-only + FE TraceBlock collapsible + hydrate
  reload từ audit. Gate tester 4/4 (1 vòng FAIL reload → FE fix dây auditByConv + bug phụ race
  activeIdRef sửa gốc → re-verify PASS qua Network log).
- **Deviation:** MAIN-thinking không ép được trong ca test (model behavior, unit symmetric đủ).

### T4-3 — done (F2a SubAgentView + huỷ per-sub — D-43 MUST)
- **Bằng chứng:** gate §4.3 browser THẬT — huỷ credit → legal KHÔNG đụng + main báo đúng "X hủy, Y vẫn
  chạy" · double-cancel 409 · SubAgentView 2 sub data riêng (brief/trace/result). 1 vòng FAIL edge
  malformed-uuid → fix catch ở STORE 3 API (interrupt/decide 500→404, audit 400 sẵn — D-49c, xác nhận
  chéo architect+tester spot-check độc lập).
- **Deviation:** target=main skip → 400 (D-49a).

### T4-4 — done BE-half (compare single vs multi — deliverable #5 tối giản, user chốt)
- **Bằng chứng:** POST /api/compare gather 2 nhánh, poll SETTLED (D-49b — advisor bắt break-ở-idle-đầu
  = demo tệ hơn single). Verify live: single 11.4s chay "không có quyền truy vấn" vs multi 74.8s
  tool_calls=7 + cards=2 + DSCR 1.501 có nguồn. {{FE 2-cột — T4-6}}
- **Deviation:** LOC 164 (>150 target, ≤400 OK).

### T4-5 — done (dọn 2-card biên nhận trùng — nợ S3)
- **Bằng chứng:** 2 đầu khớp — main KHÔNG present lại (prompt predicate ops+done+disbursed) + ops PHẢI
  present biên nhận (SKILL mục 4 — gốc shirk: mục canvas cũ chỉ dạy ops_plan). Verify live: đúng 1
  document biên nhận từ ops, không đôi không rỗng. KHÔNG present-dedup (D-49e — N5).
- **Deviation:** none.

### T4-6 — done (FE đợt cuối 4 khối — deliverable #4 + #5 UI)
- **Bằng chứng:** gate tester độc lập từng khối: Control Tower duyệt-tại-chỗ e2e L112 (phiếu→duyệt ở
  Tower→resume→loans=disbursed PG) + audit filter + status/cost · compare 2-cột (SINGLE không-data vs
  MULTI 6-tool 2-card DSCR=1.501 + link ca thật PG-khớp) · ErrorBoundary console-0 xuyên phiên · model
  picker 3 provider — ca wrap/gpt-5.4-mini CHẠY THẬT (PG provider='wrap'). 74 vitest ×3 ổn định.
- **Deviation:** D-51 picker ở composer + lazy-create (user chốt vị trí; fix dây eager — FE đính chính
  round-trip sai thứ tự + fix trọn). Provider (c) BE làm luôn trong sprint (D-45b khép trọn a+b+c).

### Provider (c) + seed-reset + wrap — done (ngoài plan gốc, user thúc)
- **Bằng chứng:** per-conv provider/model (migration + resume-consistency, verify live zai) — MAIN-only
  override (sub giữ haiku) · seed-reset 1 lệnh (1041 approvals tích tụ→0, idempotent, nghiệp vụ giữ) ·
  wrap GPT (probe 1-token thật + gate ca gpt chạy). 3 nhà model.
- **Deviation:** wrap sub-fail (haiku không map GPT gateway) → chốt (a): multi=zai, wrap=main-only (finding S5).

## 3 Quality Gates

- [x] **Gate 1 — API**: interrupt/compare/models/audit endpoints mới có integration test · 4-field
  khắp (malformed-uuid 3 API rà sạch — xác nhận chéo architect+tester) · test cũ pass · resource trần
  · status codes đúng (404/409/400).
- [x] **Gate 2 — Function**: unit mới (guard 12 + audit 14 + thinking 5 + interrupt 8 + compare 5 +
  provider 8+) assert observable · edge (malformed/partial-timeout/double-cancel/settled) · error
  path fail-loud · ruff + tsc sạch · FE Chrome self-verify MỌI khối + tester gate độc lập · LOC ≤400
  (ControlTower 271, SubAgentView 146, files khác nhỏ) · không copy-paste (dedupe helper conftest).
- [x] **Gate 3 — Sprint**: end_sprint counts re-run độc lập (architect: 208 BE + 74 FE + ruff + tsc
  ngay trước commit đóng) · architect đọc trọn function (guard-B bound/audit persist/interrupt/
  compare settled/lazy-create — git-show mọi commit) · tester gate 100% (T4-2 4/4 sau 1 vòng FAIL-fix
  · T4-3 §4.3 + 1 vòng edge-fix · T4-6 4/4 · re-verify live 8/8 sau dedupe) · test 208+74=282 ≥
  baseline 206 · findings ghi (dưới) · commit format · invariant §15 giữ (N5 card vỏ, phanh, append-
  only audit) · UNVERIFIABLE: none treo (loop-edge S3 đã BOUND).

## Test counts
- **Baseline (đầu S4):** 160 BE + 46 FE = 206. · **Sau S4:** BE **208 passed** + 11 skipped · FE
  **74 passed** = **282** (re-run độc lập bởi architect ngay trước commit đóng). Live-SDK 8/8 sau dedupe.

## Findings ngoài scope (flag S5)
- **Provider (c) per-conv** — dropdown FE hiển thị, BE chưa nhận param (SHB_PROVIDER server đủ demo).
- **cost per-tool** — SDK chỉ per-turn; meter dùng tasks.cost (D-48).
- **F2b chat-sub + Hướng-2 sub-resume** — CHỜ user chốt lật anti-pattern #15 (claude-sdk.md) có điều
  kiện; DevCrew pattern đọc xong, đề xuất đã trình.
- **buffer/match tool_use seam test** (T4-1, non-block) — chốt (b): live-verified (6 rows input+output);
  seam-test hoãn tới khi run_sub_turn có runner-seam (mock toàn SDK stream = đầu tư sai chỗ cho nợ nhỏ).
- **wrap sub-fail (provider×model edge):** SUB_MODEL="haiku" hard-code → GPT gateway không map alias →
  sub qua wrap fail (zai map nên OK). Chốt (a): đa-provider multi-agent = zai (verified full); wrap =
  main-only + compare/single. S5 nếu cần: `sub_model` per-provider trong providers.yaml.
- **{{dedupe _wait_for_conversation_idle vào conftest — làm lúc đóng sprint}}**

## Ngoại lệ đã ký (§6b)
- **none.** Loop-edge S3 đã BOUND (T4-0) — sổ ngoại lệ RỖNG lần đầu từ S1.

## Bài học sprint (ghi để không lặp)
- **"Đã rà 3 API" ≠ rà 3 API** — implementer báo xong nhưng làm 1/3; 2 spot-check độc lập (architect
  curl + tester fetch, không hẹn trước) cùng bắt. Lưới verify 2 lớp là thật.
- **Dây-nối UI phải verify ĐÚNG THỨ TỰ USER THẬT** — 2 lần sprint này (trace-reload thiếu dây audit;
  picker eager model-chọn-sau không áp): UI đẹp + self-verify sai thứ tự = dây đứt không lộ. Câu hỏi
  "dữ liệu đi từ đâu tới đâu, user làm theo thứ tự nào" bắt cả hai.
- **Tree đứng yên khi tester verify** — 2 task chung file (main_session, Workspace) → commit gộp trên
  tree-đã-test; task song song phải ranh file từ đầu; code đổi giữa gate → báo tester tree-state ngay.
- **Server-stale 2 chiều** — [FIXED] kèm restart-time; verifier kiểm server-start trước khi kết luận curl.
