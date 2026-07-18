# Sprint hiện hành

**Sprint 2 — ĐÓNG** (2026-07-18). Canvas + đội đủ 4 chuyên gia: present-tool thật + 7 card +
credit/legal THẬT + products/ops stub song song + canvas render. Gate S2 PASS (browser evidence
conv 17fe336a). 126 test.

**Sprint 3 — ĐÓNG** (2026-07-18). PHANH end-to-end (KHÓ NHẤT — D-29): disburse gated → phiếu +
card + admin duyệt → event resume → giải ngân thật. Gate 4/4 browser+PG (happy/reject/decide-twice/
authz 12/12). Race resume-dispatch FIXED (guard A/B tất định). Bonus: provider standalone (demo Đà
Nẵng hết phụ CLI auth) + routing fix + card-sync. Ngoại lệ treo S4: loop-edge guard B (defensive).

**Sprint 4 — SẴN SÀNG** (chưa kickoff): Control Tower + trace + tương tác sub (F1/F2 D-43) +
loop-bound + provider (c) per-conv/model UI. Plan draft `plan_sprint_4.md`.

**Golden path:** `sprints/ROADMAP.md`. **Plan:** `plan_sprint_3.md` (đóng) · `plan_sprint_4.md` (draft).

**Lịch sử:**

| Sprint | Commit | Kết quả |
|---|---|---|
| — | b105bbe, 705ab94 | scaffold kit + kit S1 |
| 1 | e1a5633→f52b0ba, 67c274b | Spine sống: PG+mount credit+auth · orchestrator · chat+SSE gate S1 · FE API thật (DSCR 0.236). 94 test. |
| 2 | 333d6a2, a6aaed9, a653eeb, 961ba1f | Canvas + đội đủ: present thật + 4 role (credit/legal thật) + D-33 đóng + CTX_TASK fix + FE canvas 7-card. Gate S2 PASS browser. 126 test. Waiver S1 đóng. |
| 3 | 87d9e18, 3d3cf9d, a04df64, 44fdb4b, 2ab26a4, cd1bd24 | PHANH e2e: disburse gated + phiếu + resume + giải ngân thật. Gate 4/4 browser+PG. Race FIXED (guard A/B). Provider standalone (zai). Routing fix + card-sync + skip-auth. 160 test. Ngoại lệ: loop-edge S4. |
