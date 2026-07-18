# Sprint 4 — Plan (DRAFT — chưa kickoff)

<!-- DRAFT do architect nháp cuối S3. Kickoff S4 = đọc lại SPEC §12 + patterns + end_sprint_3 +
     D-43 backlog, sửa IN-PLACE, append ## Kickoff. Không dispatch từ draft này. -->

**Objective:** Control Tower (màn admin) + trace/status/decisions/flows (deliverable #4 đề #132) +
tương tác sub (F1/F2 D-43) + hoàn thiện nợ S3.
**Theme:** Đài điều khiển — admin thấy mọi việc + can thiệp per-agent.
**Gate S4 (dự kiến):** admin thấy trace tool-call + thinking mọi sub + duyệt phiếu từ queue + click
sub → full-conv + interrupt 1 sub cụ thể (không đụng sub khác) + cost meter per-agent.
**Baseline test count:** 160 (end S3) + FE.

## Tasks (draft — chốt ở kickoff)

### T4-0 — Loop-edge bound (nợ S3, defensive) [làm sớm]
- **Assignee:** backend
- **Mô tả:** bound guard B re-dispatch (ops#2 fail bền → không loop vô hạn). attempt-state: retry-counter/
  tried-marker (approvals cột `exec_attempts` hoặc registry). ops#2 fail N lần → dừng re-dispatch, báo main
  "giải ngân lỗi bền, cần người". Migration nếu cần cột.
- **Verify:** test ops#2 fail bền (loan lỗi) → re-dispatch ≤N lần → dừng, không loop. Happy-path không regress.

### T4-1 — Control Tower màn admin (SPEC §12) [GATING]
- **Assignee:** frontend + backend
- **Mô tả:** màn riêng admin: approval queue (GET /api/approvals?pending list) + live map traces + audit
  view (tool_calls) + cost meter per-agent + trạng thái đầy đủ (empty/streaming/waiting/error/abstain).
- **Verify:** admin thấy queue phiếu + duyệt từ queue + trace tool-call mọi sub. browser.

### T4-2 — F1 thinking + toolcall trace UI (D-43)
- **Assignee:** backend + frontend
- **Mô tả:** BE emit SSE `thinking` (SDK ThinkingBlock) + `toolcall` live per sub/main (§9 CONTRACT sẵn) ·
  FE khối trace collapsible trong chat.
- **Verify:** thinking + toolcall render live, collapsible. browser.

### T4-3 — F2a click-sub full-conv + huỷ sub (D-43)
- **Assignee:** frontend + backend
- **Mô tả:** click sub panel phải → box chat = FULL conversation sub (D-20 SubAgentView ref) + nút HUỶ
  sub đang chạy (interrupt §4.3 + /interrupt §11).
- **Verify:** click sub → full-conv · huỷ 1 sub không đụng sub khác. browser.

### T4-4 — Provider (c) per-conv + model dropdown UI (D-45b)
- **Assignee:** backend + frontend
- **Mô tả:** model/provider chọn PER-CONVERSATION: migration cột provider/model vào conversations (NULLABLE
  — null→server-default) + đọc provider từ conv mọi lượt (create + 2 resume path, missing-key fail loud) +
  FE dropdown (GET /api/models sẵn — B).
- **Verify:** tạo conv chọn zai → resume dùng zai (consistency). dropdown disable has_key=false.

### T4-5 — Polish/dọn nợ S3
- **Assignee:** frontend
- **Mô tả:** 2-card "Biên nhận giải ngân" trùng (MAIN present 2 lần → dedup) · immediate-stop mạnh hơn nếu cần.

### T4-6 — Tester: gate S4 Control Tower
- **Assignee:** tester
- **Mô tả:** verify trace/queue/interrupt/cost + loop-bound + provider (c) resume-consistency. author≠checker.

---

## F2b (stretch — sau F2a): user CHAT THẬT với sub
- D-43 lật D-23: port `say()` interject LAB (sub-session đa-lượt, hiện one-shot). Luồng bàn giao chính
  vẫn qua Main (§3). Chỉ làm nếu S4 core xong sớm.

## Nợ mang sang từ S3 (xử ở S4)
- **Loop-edge guard B** (T4-0) — ngoại lệ S3, bound bằng attempt-state.
- **Provider (c)** (T4-4) — SHB_PROVIDER server đủ standalone; per-conv là tiện lợi.
- **Queue Control Tower** (T4-1) — dời từ T3-3 (nguyên khối §12).
- **2-card-trùng, immediate-stop** (T4-5) — polish.
- **Verify quy trình:** mỗi verifier live-SDK dùng loan RIÊNG hoặc tuần tự (bài học contamination S3).

---

## Kickoff — 2026-07-18

**Drift/spot-check code hiện có (đọc SPEC §9/§10/§11/§12 + spot-check backend):**
- `tasks.cost` CÓ sẵn (store.py) — cost meter phần data có nền.
- **`tool_calls` table CHƯA có migration** (SPEC §10 append-only audit) → T4-1/audit cần tạo migration + emit tool_call rows.
- `toolcall` SSE + interrupt rải rác code — cần kiểm sâu lúc dispatch từng task (đừng giả định có sẵn).
- **F2b (chat-sub) cần sub-session ĐA LƯỢT** (hiện one-shot D-33) — stretch, xác nhận lại chi phí trước khi build.

**Revisions (team-lead route — F1/F2 D-43 user đặt = ưu tiên CAO, user track):**
- Nâng F1 + F2a lên song song với Control Tower (không để cuối). User đặt cái này, ưu tiên hiển thị.
- T4-0 loop-bound (ngoại lệ S3) làm SỚM + độc lập (gate gating, backend một mình) — hạ ngoại lệ trước.
- Provider (c) + dropdown = độc lập, làm song song (không chặn Control Tower).

**Thứ tự dispatch (gating trước → fan-out):**
1. **T4-0 loop-bound** (backend, độc lập, làm ngay — hạ ngoại lệ S3).
2. **T4-1 tool_calls audit + toolcall SSE** (backend — nền cho trace/Control Tower; gating cho F1+audit).
3. Fan-out sau T4-1: **F1 trace UI** (BE emit thinking + FE render) · **F2a click-sub+huỷ** (FE+BE interrupt) · **Control Tower màn** (FE queue+map+audit+cost) · **provider (c)+dropdown** (BE+FE, độc lập).
4. **F2b chat-sub** (stretch — sau F2a, cân sub-đa-lượt).
5. **T4-6 tester gate S4** — pre-scaffold từ Exports, verify cuối.

**Bài học S3 mang sang:** verify live-SDK dùng loan RIÊNG/tuần tự (nhiễm chéo) · commit runtime → restart :8000 → báo FE/tester · verify độc lập không tin count · altitude happy-path (không leo edge-case thành blocker).
