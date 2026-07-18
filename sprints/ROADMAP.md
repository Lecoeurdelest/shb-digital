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

## Sprint 3 — PHANH end-to-end ✅ ĐÓNG (87d9e18 · 3d3cf9d · a04df64 · 44fdb4b · 2ab26a4 · cd1bd24 · {{đóng}})
- **Theme:** gate cưỡng chế tầng tool (N2) — `disburse` gated → phiếu (pending→approved→used) + biên nhận chống-thực-thi-đôi + atomic claim + payload_hash + card approval (vỏ sinh) + admin duyệt → event resume → giải ngân thật.
- **Gate:** ca "giải ngân qua chat" → phanh CHẶN (approval_required + phiếu + card) → admin duyệt UI → event resume → Ops gọi lại → thực thi ĐÚNG 1 lần (loans=disbursed + receipt); gọi lại → biên nhận cũ. ✅ 4/4 nhánh browser+PG (happy/reject/decide-twice-409/authz 12/12). Race resume-dispatch FIXED (guard A/B, cô lập 3/3 + transcript).
- **Ngoài kế hoạch (làm thêm):** routing fix (D-46 MAIN route giải ngân) · **provider registry standalone** (D-45/45b — demo Đà Nẵng không phụ CLI auth, verify qua zai) · skip-auth (D-39) · card-sync atomic.
- **Ngoại lệ treo S4:** loop-edge guard B (ops#2 fail bền → re-dispatch loop; money-safe, bound cần migration attempt-state). **Nợ:** provider (c) per-conv + model dropdown UI · queue Control Tower · 2-card-trùng dọn · immediate-stop mạnh hơn.

## Sprint 4 — Control Tower + trace + tương tác sub ✅ ĐÓNG (dcf3ac3→13860c2, 7 commit)
- **Gate:** ✅ tester verdict — Control Tower duyệt-tại-chỗ e2e + trace thinking/toolcall live+reload +
  SubAgentView + huỷ-từng-con §4.3 + compare 2-cột (single-chay vs multi-6-tool-DSCR-có-nguồn) + model
  picker 3 nhà (ca GPT chạy thật). 282 test (208 BE + 74 FE). Sổ ngoại lệ RỖNG (loop-edge S3 bound).
- **Ngoài plan:** provider (c) per-conv + seed-reset 1 lệnh + wrap GPT + D-50 chốt mô hình agent-riêng-biệt.
- **Nợ → S5:** F2b/sub-bền (D-50, lật #15 khi build) · sub_model per-provider (wrap multi) · SSE-live queue.

## Sprint 4 (kế hoạch gốc — đã thay bằng trên) ⏳
- **Theme:** màn Control Tower (admin): approval queue + live map traces + audit view (tool_calls) + cost meter + interrupt per-agent + trạng thái đầy đủ (empty/streaming/waiting/error/abstain).
- **User thêm 18/7 (D-43 lật D-23; team-lead route — MUST):**
  - **F1 — thinking + tool trace trên UI user** (tracing dễ, tạm): BE emit SSE `thinking` (SDK ThinkingBlock — LAB session.py pattern) + `toolcall` live per sub/main (§9 CONTRACT sẵn) · FE khối trace collapsible trong chat. ~½ ngày. S3 xong sớm → nhét cuối S3; không thì mở màn S4.
  - **F2a — click sub → box chat = FULL conversation của sub + nút HUỶ sub đang chạy** (D-20 SubAgentView ref + interrupt §4.3 + /interrupt §11). = S4 core, user chốt MUST.
  - **F2b — user CHAT THẬT với sub** (kênh trực tiếp phụ, port `say()` interject LAB; cần sub-session đa lượt — hiện one-shot). S4 STRETCH sau F2a. Luồng bàn giao chính vẫn qua Main (§3).
- **Gate (dự kiến):** admin thấy trace tool-call + thinking của mọi sub (F1) + duyệt phiếu từ queue + click sub → full-conv + interrupt 1 sub cụ thể không đụng sub khác (F2a) + cost meter per-agent. F2b (chat-sub) = stretch, không chặn gate nếu one-shot chưa nâng.

## Sprint 5 — Demo-prep + nghiệp vụ vỏ ✅ ĐÓNG (66ffbc2→đóng)
- **Gate:** ✅ rehearsal Vòng-1-trọn PASS + mọi cảnh pass riêng (Option A). Script v4 5-cảnh (tên khớp seed,
  thoát hiểm 8 dòng). Phanh PHÂN TẦNG (<500tr auto-rule / ≥ chờ người) + MAIN tuần tự BÀN GIAO (D-52 pain
  người ra đề, phần vỏ) + D-54 user-nào-cũng-duyệt + font self-host + constellation + responsive máy chiếu
  + compare-treo fixed + restart-server.sh. 288 test.
- **Nợ → S6/sau demo:** UX-treo SSE-đứt (phân tầng + fix) · smoke e2e liền mạch · LAB legal 3-nguồn port ·
  agent-bền D-50 · race nhấp-nháy-status (ngoại lệ có soát).

## Sprint 6 — Demo-safety cluster ✅ ĐÓNG (bb17cd8 · ca59f5b · 750ccf8 · 66c3aeb)
- **Theme (user chốt "fix UX-treo trước đi"):** UX-treo SSE-đứt (heartbeat ping data-frame §4 +
  FE watchdog 25s + time-scope boot-cleanup + conv-idle + guard-B write-war) + tách DB test
  (TEST_DATABASE_URL → shb_test, luật-hoá không-pytest-trên-DB-demo) + restart-sạch pkill
  (parent+child, nghi gốc 2-process) + smoke e2e 5-deliverable liền mạch (regression demo vĩnh viễn).
- **Gate:** ✅ tester kill-mid-flight → hệ TỰ LÀNH (reconnect+refetch thật) + smoke live PASS 4'25"
  + 302 test (224 BE shb_test + 78 FE). Ngoại lệ race-status S5 ĐÓNG. Sổ ngoại lệ: 1 (confirm
  2-process lần restart kế — guard-B đã vô hiệu hậu quả).
- **Nợ → S7:** LAB legal port (CERTIFIED 18/7 — phong bì sẵn) · settled-helper chung ·
  agent-bền D-50 (sau demo).

## Sprint 8 — 2 persona: cửa khách + bàn duyệt ngân hàng 🔄 ĐANG CHẠY (D-56 — làm TRƯỚC S7)
- **Theme (user chốt 18/7 — đảo D-54):** app = cửa KHÁCH (customer khoanh: ca mình, không duyệt,
  MAIN inject danh tính) vs NGÂN HÀNG (bank: mọi ca + Tower + duyệt). Khoản lớn bắn về bank —
  demo 2 cửa sổ phiếu-bay real-time. Engine giữ 100%; seam sẵn (user_id S1, require_admin).
- **Gate:** live 2 cửa sổ khách-vay-lớn → badge bank → duyệt → khách nhận receipt · customer
  decide 403 + không thấy ca người khác · suite ≥302 + authz matrix · script v6 rehearsal.

## Sprint 7 — LAB legal 3-nguồn + verdict-xanh ⏸ HOÃN nối sau S8 (draft + kickoff `plan_sprint_7.md`)
- **Theme:** port legal CERTIFIED (migration police/employment/assessments + 6 assumptions +
  5 tool + SKILL v3) + wire verdict-xanh vào `_auto_approve_ok` (D-52) + script v5. = ma trận
  thẩm quyền nâng cao phục vụ chính D-56. T7-1 dispatch giữ nguyên.

---

## Map 5 deliverable đề #132 → sprint trả

| # | Đề #132 đòi | Sprint trả | Đáp bằng |
|---|---|---|---|
| 1 | demo ≥2-3 chuyên gia phối hợp 1 request phức tạp | **S2** | ca DN X 5 tỷ → credit+legal+products+ops dispatch song song → canvas |
| 2 | planner phân rã → executor | **S1** | Main + orch_dispatch + event-wake (spine) ✅ |
| 3 | tool-use thật, hành động cụ thể gated | **S3** | toolpack lab + `disburse` gated (phanh) |
| 4 | dashboard traces/status/decisions/flows | **S4** | Control Tower + SSE toolcall + audit |
| 5 | so sánh single-agent vs multi-agent | **S5** (nếu kịp) | endpoint compare 2 bản chạy cùng câu, render 2 cột |
