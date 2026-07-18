# Sprint 2 — End

**Theme:** Canvas + đội đủ 4 chuyên gia — present-tool (N5 card từ tool-call) + 7 card type + credit/legal THẬT + products/ops stub dispatch song song + canvas render.
**Commit:** 333d6a2 (T2-1+T2-2) · a6aaed9 (CTX_TASK fix) · a653eeb (T2-3 canvas) · 961ba1f (smoke) · e6790fe (kickoff chore).

## Kết quả từng task

### T2-1 — done (present-tool THẬT + cards + MAIN skill present)
- **Bằng chứng:** bảng cards migration; present_tool enum 6 loại (approval ngoài enum N2); **id VỎ-inject fix 2 lớp** (N5/§15 bug tester bắt → handler lọc _VO_OWNED + _card_to_dict vỏ-field thắng, không additionalProperties phá N3); D-36 provisional SKILL.present.md → real-sub card GATING. Tester PASS độc lập.
- **Deviation:** D-36 provisional present-skill (vỏ mồi, file cạnh, N1 giữ SKILL.md gốc).

### T2-2 — done (đội đủ 4 role + concurrency D-33)
- **Bằng chứng:** discovered_roles = {credit, legal, products, operations}. credit+legal THẬT (thân hàm byte-identical LAB, verify inspect.getsource); products/ops stub vỏ + SKILL vỏ có present. **D-33 concurrency ĐÓNG:** staggered test 3× (backend) + 24× (tester độc lập) GREEN → inline-await an toàn, không §6-spawn. Fix bug D-31 downgrade (orphan FK, round-trip base↔head).
- **Deviation:** D-33 đóng (inline-await giữ); D-34 store per-call conn (S3 tách).

### T2-3 — done (FE canvas 7-card + citation + live map)
- **Bằng chứng:** CardRenderer 1-switch 7 type + default N3-defensive (type lạ không crash); cardUtil MIXED-safe; CitationChip; SSE card upsert + full-state cards[]. 37 vitest, typecheck 0, jscpd 0. **Waiver S1 ĐÓNG** (2 UI-interaction verify Chrome workaround → flaky không app-bug).
- **Deviation:** 3D→2D placeholder (D-24, S5); approval→placeholder (S4).

### CTX_TASK fix (a6aaed9) — done (bug re-entrant, tester bắt)
- **Bằng chứng:** D-33 inline path → run_main_turn reset CTX_ACTOR nhưng sót CTX_TASK → MAIN present stamp task_id sub thay null. Fix reset cả 3 contextvar. Verify: unit mutation-lock + tester live end-to-end. **SỰ CỐ:** commit 3497a1f thiếu fix (race mutation-test working-tree chung) → tester bắt → amend a6aaed9 (chưa push, git show verified). Bài học: commit phải git-show verify; mutation-check cách ly worktree.

### T2-4 — done (tester independent verify + gate S2)
- **Bằng chứng:** verify độc lập T2-1/T2-2/T2-3 + id-injection re-verify + D-33 24× + CTX_TASK mutation cô lập. Gate S2 browser (conv 17fe336a evidence): 2 sub song song → real card (credit metric + legal 4 card) + MAIN document task_id NULL + citation + 6 card không đè + console sạch. Automated smoke 3 test (default-run) + regression-lock CTX_TASK.

## 3 Quality Gates

- [x] **Gate 1 — API**: cards schema · present/card SSE integration · test cũ pass · resource trần · error 4-field.
- [x] **Gate 2 — Function**: 89 BE + 37 FE unit/integration assert observable · edge (type lạ/MIXED/id-injection) · error path 4-field · ruff+tsc sạch · **FE Chrome self-verify gate S2 browser real card (:8000 canonical a6aaed9)** · PROD LOC max 409 (store.py — mềm +10% pass, S3 tách) · jscpd 0.
- [x] **Gate 3 — Sprint**: end_sprint count re-run độc lập (BE 89, FE 37 = 126) · architect đọc trọn function (present_tool/CardRenderer/room/CTX reset — không chỉ diff) · tester 100% + browser · test 126 ≥ baseline 94 · findings ghi (D-33/34/37/38/39) · commit format feat/fix/test/chore · invariant SPEC §15 (N5 id-vỏ, N3 vỏ-mù) giữ · UNVERIFIABLE đóng (automated smoke committed, không manual-only).

## Test counts

- **Baseline (đầu S2):** 94 (69 BE + 25 FE)
- **Sau S2:** BE **89 passed** + 3 skipped (2 gate-live opt-in + 1 sub-smoke) · FE **37 passed** = **126 test** (≥94)

## Findings ngoài scope (flag cho sprint sau)

- **D-33 inline-await chi phí ẩn:** re-entrant path cần reset TAY đủ contextvar ở run_main_turn — S3+ thêm contextvar (CTX_APPROVAL?) phải thêm reset. Comment tại site.
- **D-34 store.py 409 LOC:** S3 tách module (conv/msg/task/card/legal CRUD).
- **Nợ LAB (D-35):** credit/legal SKILL thật chưa dạy present (đang dùng provisional D-36 mồi tạm). LAB drop skill thật → xoá provisional.
- **Chrome MCP `computer` click** không trigger React synthetic (tool-flaky) — workaround form_input+js. Không app-bug.

## Ngoại lệ đã ký

- **none** (waiver S1 "2 UI-interaction Chrome-flaky" ĐÃ ĐÓNG ở T2-3: verify Chrome workaround tab-mới+key → xác nhận flaky không app-bug, điều kiện xét lại thoả). Không còn ngoại lệ treo.
