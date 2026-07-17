# Sprint 2 — Plan (DRAFT — chưa kickoff)

<!-- DRAFT do architect nháp cuối S1. Kickoff S2 (khi user ra lệnh chạy) = architect đọc lại
     SPEC/DECISIONS/end_sprint_1, sửa IN-PLACE, append ## Kickoff. Không dispatch từ draft này. -->

**Objective:** Canvas sống + đội đủ 4 sub — present-tool (N5, card chỉ từ tool-call) + 7 card type +
4 chuyên gia dispatch song song (credit thật; legal/products/ops = stub cùng contract) + bảng việc/
live map. Nối build-order §16 bước 3.
**Theme:** Canvas + đội đủ (mở NGANG sau khi spine dọc đã sống S1).
**Gate S2 (D-29 spine-sống):** ca "DN X vay 5 tỷ" → Main dispatch ≥2 sub SONG SONG → mỗi sub
present card (metric/checklist…) lên canvas → Main tổng hợp document. Card có nguồn, id vỏ-inject.
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
- D-33 inline-await → chuyển §6-spawn khi T2 thêm concurrency thật (4 sub song song = đúng lúc xét).
- D-34 store per-call conn → thống nhất pool nếu churn.
- Waiver S1: 2 UI-interaction Chrome-flaky → re-verify đầu S2 (Chrome MCP session mới).
- §9 main-retry → làm nếu ca song song lộ nhu cầu bền lượt main.
