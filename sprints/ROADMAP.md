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

## Sprint 8 — 2 persona: cửa khách + bàn duyệt ngân hàng ✅ ĐÓNG (82883bb·06585e4·09c55c7·ac966b4+đóng)
- **Theme (user chốt 18/7 — đảo D-54):** app = cửa KHÁCH (customer khoanh: ca mình 404-hide,
  không duyệt, MAIN inject danh tính "anh/chị") vs NGÂN HÀNG (admin: mọi ca + Tower + duyệt +
  badge phiếu-bay poll). Engine giữ 100% — seam sẵn từ S1/S4.
- **Gate:** ✅ tester matrix 7/7 + e2e 2-phía (decide 403 · 404-hide · phiếu-bay → duyệt →
  receipt về khách · inject sống không lộ thuật ngữ) + rehearsal delta C1 2'10" (câu
  không-khai-mã PASS) · 331 test (241 BE + 90 FE). Waiver §6b: 2-cửa-sổ-cùng-lúc (giới hạn
  tool verify — bù HTTP-isolation; người verify tay trước giờ G).
- **Nợ → sau:** tool-level scoping chặt (known-limitation) · deviation inject query-per-turn.

## Sprint 7 — LAB legal 3-nguồn + ma trận verdict ✅ ĐÓNG (25bd8d7·de41787·3d58c2c·2069bbc+đóng)
- **Theme:** port legal CERTIFIED (3 bảng + 4 cột identity + 5 tool byte-identical + SKILL v3 +
  adapter WRITE khoanh vùng D-55b) + ma trận 3 tầng verdict (D-59: <500tr trừ red · xanh
  500tr-2e9 tự duyệt dẫn assessment #id · >2e9 người; assessments rỗng = hành vi cũ).
- **Gate:** ✅ tester 5/5 live (3-trụ audit đủ · xanh-tự-duyệt 594tr auto-rule nguyên văn ·
  C001 honest-null · regression · fan-out) + suite 378 (283 BE + 95 FE ≥ 331). D-58 drift
  labpack bắt + re-sync. Script v7 (câu mục-đích-mua-nhà — finding chính sách conditional).
- **Ngoài sprint (user trực tiếp):** D-60 markdown chat · merge PR #1 lobby 3D.

## Sprint 9 — Khách mới + vòng đời hồ sơ ⏳ (draft `plan_sprint_9.md`, D-57 — sau S7)
- **Theme (mentor input, người chốt):** register khách mới → form intake card → hồ sơ mới →
  3 trụ honest-null → yellow → người duyệt → MAIL Gmail thật (app password người gửi sau,
  no-op sạch khi thiếu env) + bell in-app (lưới mất mạng).

## Sprint 9 — Khách mới + vòng đời hồ sơ ✅ ĐÓNG (5059e1a→6ec86bc + merges, cùng S10)
- **Gate:** ✅ tester e2e vòng đời 6 bước local + **6/6 PASS trên PROD digital.tinhdev.com**.
  465 test (355 BE + 110 FE). Mail HTML brand BANK Digital verify Gmail thật ×2 vòng.
- 6 fix prod trong sprint: cross-owner (A) · restart-script (B) · provider-disable (C) ·
  image-configs (D) · **READ-SCOPE leak (E — nặng nhất dự án)** · mock-banner (F) +
  effective-default + UV_NO_SYNC + durable volume UID/GID.

## Sprint 10 — Docker + deploy `digital.tinhdev.com` ✅ ĐÓNG SỚM trong S9 (user lệnh "deploy lẹ")
- Compose shb132-prod (8011/3011 cô lập, volumes SDK/conv/PG) + tunnel swap (backup, web mẫu
  vốn chết trước) + seed snapshot D-62 + seed-if-empty + Dockerfile durable. Còn nợ nhẹ S10:
  1 vòng "restart container GIỮA ca đang chạy trên VM → resume nhớ" chấm chính thức (local đã
  pass; ghép vào vòng rehearsal trước giờ G).
- **Đích (team-lead khảo sát 18/7):** GCP `dev-vm` us-east1-b (Ubuntu 24.04 · 5GB RAM free ·
  23GB disk · Docker 29 + Compose v5 sẵn). Domain → Cloudflare → cloudflared systemd →
  `localhost:3010` (hiện web mẫu — GIỮ tới khi #132 xanh rồi mới chuyển tunnel, rollback dễ).
  **VM PROD DÙNG CHUNG** (cairn-prod chiếm 80/443, shopquantum 3002/8003) → #132 CÔ LẬP: port
  riêng (FE:3011 API:8011 dự kiến) + docker network riêng, KHÔNG đụng container khác.
- **Bước:** clone repo → compose up port riêng → verify nội bộ → sửa `/etc/cloudflared/config.yml`
  digital.tinhdev.com → FE-port + restart cloudflared (external/one-way — verify từng bước).
  Provider: standalone zai/wrap qua `SHB_PROVIDER` (VM không có CLI auth — D-45b).

## Sprint 12 — Port RETRIEVAL 4 TẦNG từ LAB ⏸️ HOÃN (D-63, người chốt 19/7: xếp SAU — LAB đang training nguồn, chưa khoá; KHÔNG kickoff tới khi người báo LAB drop bản certified)
- **⚠️ Hệ quả thứ tự (S10 deploy trước S12):** image S10 CHƯA cài sentence-transformers/pyvi —
  S12 xong phải REBUILD image + redeploy (ghi thành bước cuối S12; model embedding cache vào
  volume để venue không cần mạng).
- **Nguồn (LAB đã build + QA đối kháng 18/7 — KHÔNG phải xây mới):**
  `../shb-digital-experts/missions/shb-132/RETRIEVAL-README.md` (swap §7 = 3 thao tác) +
  `../battle/de-archive/note-discuss-wiki-compare-132.md` (thiết kế sếp chốt). DOER-test 5/5,
  QA 7 hướng PASS, benchmark embedding có biên lai.
- **4 tầng:** SQL (có sẵn) · wiki 18 trang + document-graph `[[link]]`/hiệu-lực (trap gói-Tết
  tựa văn-bản-chết) · entity-graph `party_relations` + `legal_related_exposure` CTE (trap
  C013 qua-trần-đơn-vỡ-trần-NHÓM B002/B004/L901) · vector notes 544 ghi chú
  (bkai vietnamese-bi-encoder + pyvi, LOCAL CPU, BLOB+numpy trong tool — KHÔNG pgvector,
  KHÔNG mạng, SQL portable).
- **Việc port:** retrieval.py → `wiki_*`+`notes_search` vào common (mọi role) +
  `legal_related_exposure` vào legal pack · SCHEMAS/ANNOTATIONS · migration 4 bảng + seed-từ-
  file wiki + copy `wiki/` · deps sentence-transformers+pyvi (image S10 phải cài + cache model).
- **⚠️ 2 cửa kickoff:** (1) SPEC §14 "không vector" — sếp ĐÃ LẬT CÓ CHỦ ĐÍCH phạm vi hẹp
  interaction_notes (note-discuss 18/7, ghi D-entry khi kickoff); (2) SKILL bổ sung per-role —
  legal SKILL v3 là bản CERTIFIED KHÔNG SỬA (D-55) → đoạn retrieval cho legal phải về LAB
  certify (v4) hoặc tách lớp inject vỏ — blocker về LAB, không tự vá.

## Sprint 11 — Cleanup + Documentation ⏳ (user chốt thứ tự 18/7: SAU S10, TRƯỚC S12)
- **Theme:** dọn repo (archive nháp, chuẩn hoá docs/, README) + bộ tài liệu thi. Nguồn
  methodology: `../battle/de-archive/METHODOLOGY-132.md` → port `docs/METHODOLOGY.md` (khuôn:
  định kiến → cơ chế thật → lựa chọn → trade-off khai thật).
- **Đối chiếu THẬT khi port (S11 chạy TRƯỚC S12):** §3 RAG 4 tầng khai trạng thái thật tại
  thời điểm viết — "4 tầng thiết kế + build CERTIFIED ở LAB (DOER 5/5, QA 7 hướng), tầng
  SQL+wiki nào đã trong SYSTEM, phần còn lại port S12" — không nói vống, không giấu; doc nói
  "pgvector" → sửa theo bản thật (BLOB+numpy local). S12 xong → 1 lượt cập nhật doc nhỏ.
- **Theme:** đóng gói compose full-stack (BE + FE build + PG đã có service). **SỐNG CÒN — SDK
  lưu session trên DISK, PHẢI mount volume ra ngoài** (người nhắc đích danh): (1) `~/.claude/`
  của user trong container (transcripts resume — mất là MAIN lú toàn bộ ca); (2)
  `backend/data/conversations/` (neo cwd per-ca); (3) PG data (đã volume); (4) `.env` keys.
  - Claude CLI phải có trong image; provider deploy = api-kind (zai/wrap qua `SHB_PROVIDER` —
    D-45 "lúc deploy set lại provider default là xong"; subscription claude-cli cần CLI-login
    tương tác, không hợp container → không làm default deploy.
  - Gate: container restart GIỮA ca → resume vẫn nhớ (bằng chứng thật) · e2e trong container ·
    **user + tester cùng verify** trước khi coi là deploy-ready.

---

## Map 5 deliverable đề #132 → sprint trả

| # | Đề #132 đòi | Sprint trả | Đáp bằng |
|---|---|---|---|
| 1 | demo ≥2-3 chuyên gia phối hợp 1 request phức tạp | **S2** | ca DN X 5 tỷ → credit+legal+products+ops dispatch song song → canvas |
| 2 | planner phân rã → executor | **S1** | Main + orch_dispatch + event-wake (spine) ✅ |
| 3 | tool-use thật, hành động cụ thể gated | **S3** | toolpack lab + `disburse` gated (phanh) |
| 4 | dashboard traces/status/decisions/flows | **S4** | Control Tower + SSE toolcall + audit |
| 5 | so sánh single-agent vs multi-agent | **S5** (nếu kịp) | endpoint compare 2 bản chạy cùng câu, render 2 cột |

## Sprint 13 — Admin thống kê + hồ sơ-lý-do-AI ⏳ (user chốt 19/7 — NGAY SAU S11, full-auto)
- **Theme (lead chốt scope, ref hình-dạng shopquantum-admin — KHÔNG copy code):** gộp vào Control
  Tower: tab "Tổng quan" (GET /api/stats today|7d — phiếu duyệt/chờ/từ chối + hồ sơ theo lane +
  delta; KpiCard/SparkLine viết lại cho stack này) + nâng audit → "Hồ sơ + lý do AI" (assessment
  3 trụ + reason ma trận D-59 — data sẵn, chỉ trình bày). 1 dòng UI "demo: admin gộp vai".
- **RÀO:** chỉ endpoint ĐỌC + màn trình bày — không bảng mới/cost-USD/health/tách-route.
- **Plan:** `plan_sprint_13.md` (draft — kickoff chỉnh khi S11 đóng). Thứ tự: S11 → S13 → S12
  (retrieval, chờ LAB drop — D-63).

## Sprint 11 — Cleanup + docs + nâng điểm ✅ ĐÓNG (f7e9332→32d88af + đóng, 19/7)
- **Gate:** ✅ CI GitHub Actions xanh khách quan (badge, bắt false-green-secret run#1) · refactor
  gated 0-đổi-hành-vi (41 money-test, SQL byte-identical) · METHODOLOGY/README-60s · google-auth
  LIVE + flaky gap=0 + dark/light default-LIGHT + logout-thoát-thật (bug FE bắt) · kịch bản
  nghiệp vụ 7/7 PASS prod (`docs/business-test-scenarios.md` — kiêm regression) · script v9
  (finding seed-amounts lớp 3). 477 test (357 BE + 120 FE). 2 waiver §6b.

## Sprint 13 — Admin thống kê + hồ sơ-lý-do-AI ✅ ĐÓNG (9ea0335 · fb8cec2 + đóng, 19/7)
- **Gate:** ✅ tester 8/8 luồng nghiệp vụ (Luồng 8 mới: KPI verify bằng SỰ KIỆN TƯƠI approved/
  auto nhảy cả UI+API; panel lý-do khớp chính xác assessment thật). 497 test (367+130), CI xanh.
  Rào giữ trọn (chỉ-đọc, 0 bảng mới). False-alarm 8a root-caused: cleanup-DB ≠ bug — note vận
  hành "reset → KPI 0 nhảy live trong demo = kể chuyện" vào scenarios doc.
