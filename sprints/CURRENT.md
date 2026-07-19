# Sprint hiện hành

**Sprint 2 — ĐÓNG** (2026-07-18). Canvas + đội đủ 4 chuyên gia: present-tool thật + 7 card +
credit/legal THẬT + products/ops stub song song + canvas render. Gate S2 PASS (browser evidence
conv 17fe336a). 126 test.

**Sprint 3 — ĐÓNG** (2026-07-18). PHANH end-to-end (KHÓ NHẤT — D-29): disburse gated → phiếu +
card + admin duyệt → event resume → giải ngân thật. Gate 4/4 browser+PG (happy/reject/decide-twice/
authz 12/12). Race resume-dispatch FIXED (guard A/B tất định). Bonus: provider standalone (demo Đà
Nẵng hết phụ CLI auth) + routing fix + card-sync. Ngoại lệ treo S4: loop-edge guard B (defensive).

**Sprint 4 — ĐÓNG** (2026-07-18): Control Tower (deliverable #4) + trace F1 + SubAgentView/huỷ F2a +
compare (deliverable #5) + model picker 3 nhà (claude-cli/zai/wrap-GPT) + loop-bound (ngoại lệ S3 hết)
+ seed-reset. Gate tester trọn. 282 test. Sổ ngoại lệ RỖNG. **5/5 deliverable đề #132 có mặt.**

**Sprint 5 — ĐÓNG** (2026-07-18): Demo-prep + nghiệp vụ vỏ. Gate rehearsal PASS (Option A). Phanh phân
tầng + MAIN tuần tự bàn giao (pain người ra đề) + D-54 + polish offline-safe + compare-fix. 288 test.
**DEMO-READY** — script v4 + seed-reset + luật vận hành. Chờ: LAB legal 3-nguồn (port khi drop).

**Sprint 6 — ĐÓNG** (2026-07-18): Demo-safety cluster. UX-treo SSE-đứt FIXED (heartbeat ping
data-frame + FE watchdog 25s + time-scope cleanup + conv-idle + guard-B — ngoại lệ race S5 ĐÓNG,
tester kill-mid-flight: hệ TỰ LÀNH) + tách DB test (shb_test, hết rác demo) + restart-sạch pkill
+ smoke e2e 5-deliverable liền mạch PASS 4'25" (regression demo vĩnh viễn). 302 test (224+78).

**Sprint 8 — ĐÓNG** (2026-07-18, D-56 làm trước S7): 2 persona — cửa KHÁCH (customer khoanh,
404-hide, MAIN inject danh tính, card "chờ ngân hàng") vs NGÂN HÀNG (admin mọi ca + Tower +
duyệt + badge phiếu-bay poll). Đảo D-54. Gate: tester matrix 7/7 + e2e 2-phía + rehearsal delta
C1 2'10" (câu không-khai-mã PASS). 331 test (241+90). Script v6 hai-cửa-sổ. Waiver §6b:
2-cửa-sổ-cùng-lúc (giới hạn tool verify).

**Sprint 7 — ĐÓNG** (2026-07-18): LAB legal 3 trụ port trọn (5 tool byte-identical + SKILL v3
certified + adapter WRITE khoanh vùng) + ma trận thẩm quyền 3 tầng (hồ sơ XANH tự duyệt trên
ngưỡng, dẫn assessment #id). Tester 5/5 live + 378 test. Script v7. D-55/58/59/60 + PR #1 3D.

**Sprint 9 — ĐÓNG** (2026-07-18, kèm S10-deploy đóng sớm theo lệnh user): khách mới trọn vòng
đời (register → form card → C9xx → yellow honest-null → duyệt → MAIL brand BANK Digital + bell)
+ **DEPLOY CÔNG KHAI https://digital.tinhdev.com** (compose shb132-prod, tunnel, 6 fix prod:
cross-owner + READ-SCOPE leak + provider/image/env/volume) + merge PR#1/#2/#3 (lobby 3D, landing,
google-OFF) + brand D-61. Tester 6/6 PASS trên prod. 465 test (355+110).

**Sprint 11 — ĐÓNG** (2026-07-19): CI badge (bắt false-green-secret ngay run#1) + refactor
gated 0-đổi (41 money-test guard) + METHODOLOGY/README-60s + google-auth LIVE + flaky-fix
gap=0 + dark/light default-LIGHT + logout-thoát-thật + kịch bản nghiệp vụ 7/7 PASS prod
(script v9 sửa seed). 477 test (357+120). 2 waiver §6b (502-tunnel, cookie-đa-tab).

**Sprint 13 — ĐÓNG** (2026-07-19): admin thống kê — Tower 6 tab (Tổng quan default: 7 KPI +
delta + AUTO-đếm-riêng + poll) + Hồ sơ-lý-do-AI (criteria 3 trụ + basis). Tester 8/8 luồng
(scenarios doc = checklist giờ G). 497 test (367+130). False-alarm 8a root-caused (cleanup ≠ bug).

**Sprint 14 — ĐÓNG** (2026-07-19): LOOP DOGFOOD 2 persona (user chốt full-auto). 16 finding —
14 fixed re-verified PROD (7🔴: credential-lộ D-64, form-mất-data, +Ca-mới race, phiếu-vô-danh,
badge first-tick, từ-chối-không-lý-do đứt-mạch-BE, bell-dropdown-clip) + cache-stale nginx +
runbook §4b. 514 test (352+162). Prod dọn về baseline demo nguyên văn (biên lai theo số).
B-05 deferred (gu user).

**Sprint 15 — ĐÓNG** (2026-07-19): UX wave user chốt — fix bug switch zai↔wrap prod (effective_
default + compose-đè-.env D-66) · composer ModelSelect kiểu Claude + switch PER-TURN · CRUD
conversation (rename + delete 1-tx giữ audit D-67) · markdown spacing. 549 test (369+180).
PROD 4/4. Sự cố tree-chung + :8000×3 → luật mới (soát --cached; D-38 graceful-5s).

**Hàng đợi:** S12 ĐANG CHẠY (T12-1 xong chờ smoke · T12-2 BE 2 blocker đã chốt · T12-3 porter
worktree · T12-4 spec sẵn) · S16 FE T16-3 đang chạy, BE-part sau S12 · rehearsal tay giờ G
(+ hard-refresh §4b + badge 10s + 1 click Google chính chủ) · B-05 chờ gu user.

**Golden path:** `sprints/ROADMAP.md`. **Plan:** (chờ sprint kế — S12 khi LAB drop).

**Lịch sử:**

| Sprint | Commit | Kết quả |
|---|---|---|
| — | b105bbe, 705ab94 | scaffold kit + kit S1 |
| 1 | e1a5633→f52b0ba, 67c274b | Spine sống: PG+mount credit+auth · orchestrator · chat+SSE gate S1 · FE API thật (DSCR 0.236). 94 test. |
| 2 | 333d6a2, a6aaed9, a653eeb, 961ba1f | Canvas + đội đủ: present thật + 4 role (credit/legal thật) + D-33 đóng + CTX_TASK fix + FE canvas 7-card. Gate S2 PASS browser. 126 test. Waiver S1 đóng. |
| 3 | 87d9e18, 3d3cf9d, a04df64, 44fdb4b, 2ab26a4, cd1bd24 | PHANH e2e: disburse gated + phiếu + resume + giải ngân thật. Gate 4/4 browser+PG. Race FIXED (guard A/B). Provider standalone (zai). Routing fix + card-sync + skip-auth. 160 test. Ngoại lệ: loop-edge S4. |
| 5 | 66ffbc2, 5434874, 8dff186, 111458e, 5513813, 5d3810b + đóng | Demo-prep: script v4 + rehearsal PASS + phanh phân tầng + MAIN tuần tự + D-54 + polish. 288 test. DEMO-READY. |
| 4 | dcf3ac3, ad4f1b1, a9e931c, be8560d, 5da3667, 13860c2 | Control Tower + trace F1 + SubAgentView/huỷ F2a + compare + picker 3 nhà model + loop-bound + seed-reset. Gate tester trọn. 282 test. Ngoại lệ RỖNG. 5/5 deliverable có mặt. |
| 6 | bb17cd8, ca59f5b, 750ccf8, 66c3aeb | Demo-safety: UX-treo SSE fixed (ping+watchdog+time-scope+guard-B, race S5 đóng) + tách DB test + pkill restart-sạch + smoke e2e liền mạch 4'25". 302 test. |
| 8 | 82883bb, 06585e4, 09c55c7, ac966b4 + đóng | 2 persona D-56 (đảo D-54): cửa khách + bàn duyệt bank + MAIN inject + badge phiếu-bay + script v6 hai-cửa-sổ. Matrix 7/7 + e2e 2-phía + rehearsal delta. 331 test. |
| 7 | 25bd8d7, de41787, 3d58c2c, 2069bbc + đóng | LAB legal 3 trụ (byte-identical + SKILL v3 + adapter WRITE D-55b) + ma trận 3 tầng verdict D-59 (xanh tự duyệt trên ngưỡng). Tester 5/5 live. 378 test. Kèm D-60 markdown + PR #1 lobby 3D. |
| 9+10 | 5059e1a→6ec86bc + merges + đóng | Khách mới vòng đời trọn (form/mail/bell) + DEPLOY digital.tinhdev.com + 6 fix prod (read-scope leak E) + landing/google + brand D-61. Tester 6/6 PROD. 465 test. |
| 11 | f7e9332→32d88af + đóng | CI badge + refactor gated 0-đổi + METHODOLOGY/README + google LIVE + flaky gap=0 + dark/light LIGHT + logout thật + scenarios 7/7 prod + script v9. 477 test. |
| 13 | 39e7deb, 9ea0335, fb8cec2 + đóng | Admin thống kê: /api/stats+assessments + Tower tab Tổng quan (7 KPI) + Hồ sơ-lý-do-AI. Tester 8/8. 497 test. |
| 14 | 58d3774→2940295 + đóng | LOOP DOGFOOD 2 persona: 16 finding, 14 fixed CHỐT PROD (7🔴) + cache-fix §4b + D-64. Double-evidence B-01/07, race A-07 thật. 514 test. Prod về baseline sạch. |
| 15 | af8782b, 1068300, 4e59331 + đóng | UX wave: fix switch zai↔wrap + ModelSelect per-turn + CRUD conv (D-67) + markdown. 549 test. PROD 4/4. D-66. |
