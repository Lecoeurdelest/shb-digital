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
