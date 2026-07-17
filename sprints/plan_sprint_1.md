# Sprint 1 — Plan

**Objective:** Lát cắt DỌC sống (prove-spine-first): SCAFFOLD NỀN đủ cho 1 luồng (auth + 1 chat
endpoint + 1 role credit + 1 SSE) → RM chat → Main dispatch → sub → event → Main tổng hợp CÓ NGUỒN
→ SSE → FE chat thô. Nối build-order §16 bước 1+2.
**Theme:** SPINE SỐNG trên NỀN scaffold — nền (stack/contract/auth/FE/BE khung) trước, spine sau.
**Gate S1 (D-29):** SPINE SỐNG — ca chạy end-to-end, DSCR có nguồn tool. KHÔNG phụ thuộc chất
lượng tool LAB: credit thật chạy được (D-28 đã xử) = dùng; giở chứng → stub. Gate ≠ "credit-thật-3.709".
**Baseline test count:** 0 (greenfield — end_sprint phải > 0, mọi task mới có test).

## Tasks (làm theo dependency)

### T1-1 — Hạ tầng: PG minimal + conn adapter + mount_role(credit) [GATING]
- **Assignee:** backend
- **Mô tả:** Dựng `backend/app/` skeleton (FastAPI + `/api/health`) + docker-compose db (PG15) +
  Alembic migration bảng NGHIỆP VỤ nhỏ nhất (`customers, loans, cic_records, assumptions`) +
  bảng VẬN HÀNH tối thiểu (`conversations, messages, tasks`) + load seed-values từ SQLite LAB
  (`../shb-digital-experts/missions/shb-132/seed/shb-132.db`) sang PG. **Conn adapter (D-27)**:
  class bọc pooled psycopg2 conn cấp `.execute(sql,params)` (rewrite `?`→`%s`) trả cursor row
  factory 3-mode (index + `dict(row)`). `roles/credit/` = copy `functions.py`(credit+customers)
  + SCHEMAS/REGISTRY/ANNOTATIONS + `SKILL.md` từ LAB (D-08, KHÔNG sửa logic). `mount_role(credit)`
  → MCP server in-process + envelope 4-field + bad_param. `credit` = credit_assess/credit_cic_get
  + cust_search/cust_get (D-17).
- **Dependency:** none (gating — chạy một mình trước)
- **Verification:** (1) `docker compose up -d db` + `uv run alembic upgrade head` → 7 bảng tồn
  tại; `SELECT count(*) FROM assumptions` = 9, `customers` ≥ 26. (2) Gọi
  `REGISTRY['credit_assess'](adapter_conn, owner_id='C001')` qua adapter → `found:true`, DSCR non-null
  (= 3.709, income 30tr / pay 8.088tr). (3) Gọi qua `mount_role` MCP in-process với param sai tên
  → `bad_param` 4-field, fn KHÔNG chạy. (4) `pytest` xanh.

### T1-2 — Orchestrator spine: dispatch nền idempotent + event-wake + slot/queue + SDK close-on-done/resume
- **Assignee:** backend
- **Mô tả:** TÂM ĐIỂM thiết kế. `orch_dispatch(role,title,input)` fire-and-forget + idempotent
  `(conv,role)` (multi-agent §3/§4) · `_run_sub` + `_report` 1-điểm-hội-tụ (invariant mọi kết cục
  = đúng 1 event, §5) · slot/queue 1-lượt/phòng không-nuốt-lệnh-người (§2) · `handle_room_event`
  wake→work→sleep (§1) · SDK client: connect/disconnect CÙNG task đã connect (cancel-scope),
  close-on-done, resume từ `sdk_session_id` (tham chiếu `session.py`). Main options: system_prompt
  điều phối (skill mỏng vỏ tự viết — KHÔNG phải skill nghiệp vụ), allowed_tools = orch_* + common.
  Sub: mount_role(credit) + common (calc/present placeholder present ở S1 chỉ cần calc). Model
  main=sonnet sub=haiku (D-16). ContextVar attribution (§7 lab-joint).
- **Dependency:** T1-1 (cần mount_role + adapter)
- **Verification:** (1) test idempotent: gọi orch_dispatch 2 lần cùng role → lần 2 `created:false`,
  registry 1 task (multi-agent §4 case đinh). (2) test invariant: sub done/failed/timeout đều sinh
  đúng 1 event `task_done` (mock sub 3 kết cục). (3) test slot: 2 event vào phòng bận → 1 chạy 1
  xếp hàng, user_message không bị dedup. (4) `pytest` xanh.

### T1-3 — Vòng lõi chat + SSE: /chat → main → dispatch credit → sub thật → event → tổng hợp → stream
- **Assignee:** backend
- **Mô tả:** API `POST /api/conversations` + `POST /api/conversations/{id}/chat` (đẩy user_message
  vào phòng) + `GET /api/conversations/{id}/sse` (stream in-process 1-worker, header
  `X-Accel-Buffering: no` + heartbeat) + `GET /api/conversations/{id}` (full state). SSE events
  S1: `chat.delta` (stream chữ main) + `task.created`/`task.status` (bảng việc). Ghép spine T1-2:
  main nhận câu hỏi credit → dispatch credit → sub gọi credit_assess THẬT → event → main tổng hợp
  trả lời CÓ SỐ + trích nguồn tool. Persist messages/tasks vào PG.
- **Dependency:** T1-2
- **Verification:** (1) `curl POST /chat` câu hỏi C001 → SSE trả `chat.delta` có DSCR 3.709 + nhắc
  nguồn credit_assess. (2) `GET /conversations/{id}` trả messages+tasks đúng shape. (3) end-to-end
  ca gate chạy thật (tester T1-5 xác nhận). (4) `pytest` integration xanh.

### T1-4 — FE chat thô (sidebar ca | chat | stream)
- **Assignee:** frontend
- **Mô tả:** React+Vite+TS skeleton + port tokens `design/workspace/shared.jsx` object `T` →
  `frontend/src/tokens.css` (D-14). Màn Workspace TỐI GIẢN S1: sidebar ca (list/tạo) | khung chat
  (gõ câu hỏi → hiển thị stream `chat.delta` của main + badge task running/done từ `task.status`).
  Login đơn giản (2 account seed user/admin — hoặc bypass auth S1 nếu chưa có, ghi deviation).
  KHÔNG canvas/card (S3), KHÔNG 3D (D-24, placeholder 2D). Tự-verify bằng Chrome.
- **Dependency:** T1-3 (cần API+SSE shape) — bắt đầu skeleton+tokens song song, ghép SSE sau
- **Verification:** browser: mở app → tạo ca → gõ câu hỏi C001 → thấy stream chữ main + DSCR
  hiển thị. FE tự chụp Chrome xác nhận. `npm run typecheck` sạch.

### T1-5 — Tester: pre-scaffold + validate ca gate end-to-end
- **Assignee:** tester
- **Mô tả:** Pre-scaffold từ Exports T1-1/T1-2 (3 ca đinh spine: idempotent-2-lần, invariant-3-kết-cục,
  slot-không-nuốt-tin + ca DSCR gate). Sau khi T1-3 xong: validate ca GATE THẬT end-to-end (không
  nhận lời khai implementer). Verify tool-layer: gọi thẳng `REGISTRY[tool](adapter_conn,**kw)` +
  qua mount_role MCP (D-25). Query PG trực tiếp (`DATABASE_URL`) đối chiếu tasks/messages persist.
  Mỗi FAIL → feedback thi-hành-được (expected/actual/repro/nghi-vấn/mức-độ).
- **Dependency:** T1-1 (pre-scaffold), T1-3 (validate end-to-end)
- **Verification:** **GATE S1** (tester chạy THẬT): câu hỏi "khách C001 (Nguyễn Văn An) lương 30tr,
  đang trả nợ 8tr/tháng — DSCR?" → Main trả DSCR = 3.709 tính bằng credit_assess (KHÔNG nhẩm), có
  citation nguồn tool. Ca end-to-end thật, không mock. + suite spine 100% pass.

---

## Kickoff — 2026-07-18

**Drift since plan:** Kickoff đầu (không có plan cũ). Drift so với giả định onboard:
- **D-27 phát sinh (mức nặng):** psycopg2 conn KHÔNG chạy credit.py như-là kể cả sau `?`→`%s` —
  `.execute()` không tồn tại trên psycopg2 conn + 3 kiểu row-access xung khắc mọi cursor stock.
  → conn ADAPTER ở lớp cấp-conn của vỏ (N1-sạch, D-21 A2). Đã verify bằng đọc credit.py thật +
  liệt kê 3 điểm phủ. Đây là mount Logic backend KHÔNG được improvise → viết vào T1-1 Logic.
- **DSCR gate reproducible-confirmed:** query seed → **C001 income 30tr, active pay 8.088tr/th,
  DSCR=3.709** khớp nguyên văn câu gate. Trao C001 làm anchor cho tester (gate không bị bounce
  vì unmeetable). Verification assert "DSCR non-null, nguồn credit_assess", không hard-code value.
- **CLAUDE.md gitignored:** lệnh/layout ghi CLAUDE.md §1 (nội bộ) + song song DECISIONS D-26
  (tracked) để có bản version-controlled.

**Plan revisions:** Plan viết mới toàn bộ ở kickoff này (greenfield). T1-1 nhận thêm ràng buộc
adapter D-27 vào Logic. Gate S1 (T1-5) anchor C001.

**Final task list (chốt dispatch):**
- T1-1 → backend — GATING: PG 7 bảng + seed + conn adapter D-27 + mount credit; adapter chạy credit_assess(C001)=3.709
- T1-2 → backend — spine: dispatch idempotent + invariant 1-event + slot/queue; 3 test đinh xanh
- T1-3 → backend — vòng lõi chat+SSE: /chat→main→credit thật→event→tổng hợp có số+nguồn
- T1-4 → frontend — chat thô: tokens + sidebar|chat|stream; browser thấy DSCR
- T1-5 → tester — pre-scaffold 3 ca spine + GATE S1 end-to-end C001 DSCR=3.709 có nguồn

---

## Kickoff REVISION — 2026-07-18 (nắn altitude + đổi trục + sửa điều phối)

**Drift since first kickoff (2 sự cố lớn giữa sprint):**
1. **Nắn altitude (user + team-lead):** đội xoáy quá sâu vào tool/skill LAB — thứ quan trọng là
   SYSTEM. LAB mới có 1 agent demo, còn nhiều phần. → **D-29**: gate mỗi sprint = SPINE SỐNG (không
   phụ thuộc chất lượng tool LAB); LAB-timebox 30ph/sự cố; roadmap stub-first. Adapter+mount+PG =
   SYSTEM thật (giữ). Sự cố `legal_docs_source` (D-28) là bug tool LAB — architect lỡ phân xử sâu
   (ghi cả D-entry dài) = đúng loại lệch altitude cần tránh từ giờ.
2. **Sự cố điều phối (user bắt):** architect lỡ dùng tool `Agent` spawn 2 subagent ẩn danh
   (backend/frontend) TRONG KHI roster teammate đã SỐNG sẵn → 2 con cùng role đè file. 2 con spawn
   đã KILL theo lệnh user; file chúng viết vẫn trên đĩa (kế thừa được, verify trước khi dùng).
   **Luật cứng (D-29 bài học):** dispatch = SendMessage tới roster teammate theo TÊN, KHÔNG spawn
   Agent cho role đã có. Task Cairn #1/#4 reset về pending → giao lại roster teammate qua SendMessage.
3. **Thứ tự Sprint 1 đổi (team-lead):** task đầu = SCAFFOLD NỀN (compose+FastAPI+auth+PG+CONTRACT+FE
   khung), rồi spine, rồi nối dọc. "Không có nền thì không cắm gì." T1-1 nhận thêm: **auth JWT 2
   account seed** + CONTRACT là điểm đồng bộ FE/BE.
4. **CONTRACT chốt (D-30):** `docs/CONTRACT.md` = 1 nguồn sự thật API+SSE+envelope (FE/BE đang tự
   đoán shape → lệch). Đã đẩy cả 2 phía.

**Plan revisions:**
- Objective/Theme/Gate sửa in-place (đầu file): gate = SPINE SỐNG, không "credit-thật-3.709".
- T1-1 re-scope: + auth JWT + CONTRACT; đấu-credit-thật-ra-số DỜI khỏi gate T1-1 (D-29 — bonus, không điều kiện).
- Dispatch: T1-1→roster-backend, T1-4→roster-frontend (qua SendMessage, kế thừa disk state + verify lại).
  T1-2/T1-3→backend sau; T1-5→tester. KHÔNG spawn Agent.

**Final task list (chốt dispatch — bản 2):**
- T1-1 → backend — SCAFFOLD NỀN: compose+FastAPI+auth JWT(2 acc)+PG 7 bảng+seed(D-28)+adapter D-27+mount credit; theo CONTRACT.md
- T1-2 → backend — spine (tâm điểm): dispatch idempotent + invariant 1-event + slot/queue + SDK close-on-done/resume; 3 test đinh
- T1-3 → backend — vòng lõi chat+SSE theo CONTRACT: /chat→main→credit→event→tổng hợp có nguồn→SSE
- T1-4 → frontend — chat thô: kế thừa scaffold+tokens+types đã có (verify); browser thấy DSCR (mock→thật)
- T1-5 → tester — pre-scaffold 3 ca spine + GATE S1 SPINE SỐNG end-to-end có nguồn (C001 DSCR=3.709 = anchor)
