# ROADMAP — Golden path S1→S5 (SYSTEM #132 Digital Expert Guild)

> Đường LỚN + gate toàn cục. Chi tiết task = `plan_sprint_X.md` (draft khi sprint trước đóng —
> plan là nháp 70-80%, chỉnh ở kickoff). ROADMAP giữ đường + gate, **cập nhật CÙNG commit đóng
> mỗi sprint**. Nguồn: SPEC §16 build-order + D-29 roadmap. Kim chỉ nam: prove-spine-first
> (dọc sống trước, mở ngang sau) · gate = spine-sống vỏ-controlled (D-29, không phụ thuộc tool LAB).

---

## Sprint 1 — Spine sống ✅ ĐÓNG (commit 67c274b, pushed)
- **Theme:** Lát cắt dọc: RM login → chat → Main dispatch Credit → sub tool thật (PG) → event → tổng hợp có nguồn → SSE → FE.
- **Gate:** ca DSCR C001 end-to-end THẬT — DSCR có nguồn tool (không nhẩm), render qua UI. ✅ (DSCR 0.236 thật qua UI, auth seam cash in)
- **Plan:** `plan_sprint_1.md` · **End:** `end_sprint_1.md` (94 test, 1 waiver Chrome-flaky đã đóng ở S2).

## Sprint 2 — Canvas + đội đủ ✅ ĐÓNG (333d6a2/a6aaed9/a653eeb/961ba1f)
- **Theme:** present-tool (N5 card từ tool-call) + 7 card type + 4 chuyên gia dispatch song song (credit/legal thật · products/ops stub) + canvas + live map.
- **Gate:** ca "DN X vay 5 tỷ" → ≥2 sub SONG SONG → real-sub card + main document + stub present canvas (id vỏ-inject) → FE render. ✅ (browser evidence conv 17fe336a: 2 sub song song, 6 card, document task_id NULL, 126 test)
- **Plan:** `plan_sprint_2.md` · **End:** `end_sprint_2.md`. D-33 đóng, waiver S1 đóng.

## Sprint 3 — PHANH end-to-end ⏳ PLANNED (phần KHÓ NHẤT — attention lớn nhất, D-29)
- **Theme:** gate cưỡng chế tầng tool (N2) — `disburse` gated → phiếu (pending→approved→used) + biên nhận chống-thực-thi-đôi + atomic claim UPDATE…WHERE + payload_hash chuẩn hoá + card approval (chỉ vỏ sinh) + admin duyệt → event resume.
- **Gate (dự kiến):** "giải ngân 5 tỷ khi chưa duyệt" → két CHẶN (approval_required) → admin duyệt → Ops gọi lại → thực thi ĐÚNG 1 lần; gọi lại sau thành công → biên nhận cũ (không thực thi đôi).
- **Nợ mang sang:** D-33 inline-await (nếu §9 main-retry/concurrency cần → chuyển §6-spawn) · store.py tách module.

## Sprint 4 — Control Tower + trace ⏳ PLANNED
- **Theme:** màn Control Tower (admin): approval queue + live map traces + audit view (tool_calls) + cost meter + interrupt per-agent + trạng thái đầy đủ (empty/streaming/waiting/error/abstain).
- **Gate (dự kiến):** admin thấy trace tool-call của mọi sub + duyệt phiếu từ queue + interrupt 1 sub cụ thể (không đụng sub khác) + cost meter per-agent.

## Sprint 5 — Polish + demo ⏳ PLANNED
- **Theme:** UI theo mock (lobby 3D nếu kịp — D-24) + demo-script + seed-reset + compare endpoint (single vs multi-agent) nếu kịp.
- **Gate (dự kiến):** demo-script ca "DN X vay 5 tỷ" chạy mượt end-to-end trước giám khảo + seed-reset 1 lệnh.

---

## Map 5 deliverable đề #132 → sprint trả

| # | Đề #132 đòi | Sprint trả | Đáp bằng |
|---|---|---|---|
| 1 | demo ≥2-3 chuyên gia phối hợp 1 request phức tạp | **S2** | ca DN X 5 tỷ → credit+legal+products+ops dispatch song song → canvas |
| 2 | planner phân rã → executor | **S1** | Main + orch_dispatch + event-wake (spine) ✅ |
| 3 | tool-use thật, hành động cụ thể gated | **S3** | toolpack lab + `disburse` gated (phanh) |
| 4 | dashboard traces/status/decisions/flows | **S4** | Control Tower + SSE toolcall + audit |
| 5 | so sánh single-agent vs multi-agent | **S5** (nếu kịp) | endpoint compare 2 bản chạy cùng câu, render 2 cột |
