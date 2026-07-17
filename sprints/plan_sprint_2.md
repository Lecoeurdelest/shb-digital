# Sprint 2 — Plan (DRAFT — chưa kickoff)

<!-- DRAFT do architect nháp cuối S1. Kickoff S2 (khi user ra lệnh chạy) = architect đọc lại
     SPEC/DECISIONS/end_sprint_1, sửa IN-PLACE, append ## Kickoff. Không dispatch từ draft này. -->

**Objective:** Canvas sống + đội đủ 4 sub — present-tool (N5, card chỉ từ tool-call) + 7 card type +
4 chuyên gia dispatch song song (credit thật; legal/products/ops = stub cùng contract) + bảng việc/
live map. Nối build-order §16 bước 3.
**Theme:** Canvas + đội đủ (mở NGANG sau khi spine dọc đã sống S1).
**Gate S2 (D-29 spine-sống, vỏ-controlled surfaces ALONE):** ca "DN X vay 5 tỷ" → Main dispatch
≥2 sub SONG SONG (staggered completion) → **MAIN present(document) + STUB-role present(card)** lên
canvas (id vỏ-inject) → Main tổng hợp. Card có nguồn. **Real-sub card (credit/legal) = BONUS, KHÔNG
gate** (skill LAB không gọi present — N1 cấm sửa skill thật; xem Kickoff). Concurrency: sub xong
KHI main-turn in-flight → mỗi task_done = đúng 1 main wake, no lost/double, board consistent, 3×.
**Baseline test count:** 94 (69 BE + 25 FE — end S2 phải ≥).

## Tasks (draft — chốt ở kickoff)

### T2-1 — present-tool + canvas persist + SSE card
- **Assignee:** backend
- **Mô tả:** `present(card)` tool chung (common server) — validate shape tối thiểu {type,title,items} +
  persist bảng `cards` + SSE `card` + id vỏ-inject (canvas-present.md §1). Bảng `cards` migration.
- **Verification:** sub gọi present → card vào DB + SSE bắn + id vỏ sinh (không model bơm). unit test shape-reject.

### T2-2 — 4 sub song song + stub 3 role (legal/products/ops)
- **Assignee:** backend
- **Mô tả:** stub `roles/{legal,products,operations}/` cùng contract (functions + SCHEMAS, data giả đúng
  shape, isMock:true — lab-joint §4). Main dispatch nhiều role → chạy song song (semaphore per-phòng đã có).
- **Verification:** ca dispatch credit+legal → 2 sub song song → 2 task_done event → Main tổng hợp. cap không đè.

### T2-3 — FE canvas render 7 card type + live map + bảng việc
- **Assignee:** frontend
- **Mô tả:** canvas cột phải render 7 card (1 switch theo type, canvas-present §3) + citation chip (source) +
  live map 4 sub (placeholder 2D grid, D-24) + bảng việc. Ráp SSE `card` thật.
- **Verification:** Chrome: ca 5 tỷ → thấy card metric/checklist render + chip source bấm được. typecheck sạch.

### T2-4 — Tester: verify canvas + song song + gate S2
- **Assignee:** tester
- **Mô tả:** verify present persist+SSE, 4-sub-song-song không race, card id vỏ-inject (model không bơm),
  gate S2 end-to-end. Browser card render.
- **Verification:** GATE S2 (§ trên) + suite ≥94.

---

## Findings/nợ mang sang từ S1 (xử ở S2 nếu chạm)
- D-33 inline-await → **S2 là lúc TEST (không refactor preemptive)**: gate exercise sub-xong-khi-main-in-flight
  (staggered) → green closes D-33 note; chỉ red mới license §6-spawn convert. (advisor traced holds under 4 sub.)
- D-34 store per-call conn → thống nhất pool nếu churn.
- Waiver S1: 2 UI-interaction Chrome-flaky → re-verify đầu S2 (Chrome MCP session mới).
- §9 main-retry → làm nếu ca song song lộ nhu cầu bền lượt main.

---

## Kickoff — 2026-07-18

**Drift since draft (spot-check + advisor):**
1. **present là STUB ở S1** (common_tools.py trả 'ok') → T2-1 làm present THẬT (persist cards + SSE + id inject).
   Bảng `cards` chưa có → T2-1 migration.
2. **S2 AUTH-SEAM (advisor bắt — điểm nặng, verify NGAY):** `present` là việc VỎ, nhưng AI-GỌI-present là
   SKILL = việc LAB (N1). Grep xác nhận: **credit SKILL + legal SKILL (LAB) KHÔNG gọi present** (copy từ world
   không canvas). MAIN skill (vỏ) cũng chưa. → **Real-sub card KHÔNG appear được, N1 cấm sửa skill LAB.**
   Giải: gate trên (a) MAIN present [vỏ tự viết skill — TÔI thêm present], (b) STUB-role present [vỏ viết
   SKILL stub — include present]. Real credit/legal card = BONUS. **Flag team-lead: LAB-skill cần dạy present.**
3. **Legal LAB CÓ thật** (legal.py + skills/legal) → mount THẬT opportunistic (test mount_role role thứ 2),
   30-min timebox, stub fallback (D-18+D-29). NHƯNG legal-real KHÔNG trên critical path gate.
4. D-33: S2 là lúc TEST concurrency (staggered), không refactor preemptive.

**Plan revisions:**
- Gate S2 sửa: vỏ-controlled ALONE (main+stub present), real-sub card = bonus. Concurrency staggered.
- T2-1 (present+cards): + MAIN skill thêm present-call (vỏ tự viết).
- T2-2 (stub roles): products/ops stub SKILL do VỎ viết CÓ present-call. Legal mount thật timebox (bonus).
- T2-2 concurrency test: staggered completion (stub delay) — test D-33 inline-await thật.

**Final task list (chốt dispatch):**
- T2-1 → backend — present THẬT (cards migration + persist + SSE + id inject) + MAIN skill thêm present. Card vào DB+SSE, id vỏ.
- T2-2 → backend — stub products/ops (SKILL vỏ-viết có present) + legal mount thật (timebox bonus) + 4-sub song song staggered (test D-33).
- T2-3 → frontend — canvas 7 card render + citation chip + live map 2D + bảng việc. Ráp SSE card. (+ re-verify 2 UI waiver S1)
- T2-4 → tester — gate S2 (main+stub present card, staggered concurrency 3×) + verify id-vỏ-inject (model không bơm).
