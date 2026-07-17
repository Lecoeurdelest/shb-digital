# DECISIONS — sổ ngoài-dự-tính (mới nhất trên cùng)

> ① VƯỢT-SPEC: tình huống spec không lường. ② TỰ-QUYẾT: phương án agent chốt khi vắng người.
> Format: `quyết gì — vì sao — cách đổi`. NGƯỜI đọc lại async + override (human-wins).
> Entry đã tiêu hóa vào kit thì xoá — sổ chỉ giữ quyết định CÒN SỐNG (lịch sử đầy đủ: git log).

## ① VƯỢT-SPEC

- (trống)

## ① VƯỢT-SPEC

- **D-21 · Data nghiệp vụ → POSTGRES (đúng cấu trúc system thật); tool/skill LÀ VIỆC LAB, vỏ
  cấp conn — cách A2** (người chốt 18/7 — ĐẢO SPEC §7/§10/§12) — SQLite của LAB là ĐỒ THÍ NGHIỆM
  (xoá/sửa/bơm liên tục để train, rẻ+nhanh), KHÔNG phải thành phần system thật. System thật build
  data nghiệp vụ (`customers·businesses·loans·collaterals·cic_records·assumptions` + legal tables)
  trong **1 Postgres** cùng render+audit (1 pool, sạch dưới 1 worker). Từ LAB dựng lại SCHEMA +
  seed-values trong PG; KHÔNG mount file `.db`.
  - **RANH GIỚI CỨNG N1 (người chốt 18/7 — "bạn chỉ lo system, tool+skill để LAB lo"):** đội build
    lo **VỎ** (mount_role, cấp conn, dispatch, event, phanh, canvas, UI) — **KHÔNG viết/sửa tool
    nghiệp vụ, KHÔNG viết skill**. TRÍ KHÔN (tool+skill) = LAB nuôi.
  - **Cách A2 (giữ N3 vỏ-mù + LAB-thả-file):** contract §7 giữ `fn(conn, **kwargs)->dict`; **vỏ
    truyền PG conn từ pool** (thay SQLite). **Tool LAB viết SQL PORTABLE** (ANSI: `%s`/param bind,
    KHÔNG cú pháp SQLite-riêng như `?`, `INSERT OR`, `strftime`). Vỏ KHÔNG đụng logic tool — tool
    nào lỡ dùng cú pháp SQLite-riêng → LAB sửa cho portable, không phải vỏ reimplement. LAB vẫn
    "thả file functions + dán SCHEMAS + xoá stub" (D-18 GIỮ NGUYÊN, chỉ đổi: conn giờ là PG,
    SQL portable).
  - **Write-back (tự quyết theo nghiệp vụ, decide-and-log):** `disburse` GHI NGƯỢC
    `loans.status='disbursed'` (nghiệp vụ thật). Biên nhận vẫn ở `approvals.receipt` = nguồn-sự-thật
    chống-thực-thi-đôi (§4.4); loan status là hệ quả. → business tables CẦN write path → PG đúng.
    (Tool ghi vẫn là LAB viết; vỏ chỉ cấp conn ghi-được thay vì read-only.) — Đổi: người nói disburse
    không chạm data nghiệp vụ.
  - **Sequencing (giữ prove-spine-first):** B2 dựng PG path NHỎ NHẤT — chỉ bảng `credit_assess`
    cần (customers/loans/cic/assumptions) — chạy thông xương sống (chat→dispatch→sub→tool THẬT→
    event→main) TRƯỚC; legal/products/ops + schema còn lại fan-out sau. KHÔNG front-load full
    migration trước xương sống.
  - — Đổi: người quay lại mount SQLite, hoặc chuyển sang A1 (báo LAB viết tool cho PG trực tiếp).
- **D-22 · Conn cấp cho tool LAB = psycopg2 SYNC conn chạy trong `run_in_executor`** (team-lead
  chốt 18/7, decide-and-log — backend nêu, verify nguồn LAB) — fn LAB là **hàm THUẦN SYNC**
  (`def credit_assess(conn, ...)` + `conn.execute().fetchone()`, DB-API style — verify tại
  `../shb-digital-experts/missions/shb-132/tools/functions/`). Interface §7 "fn thuần, không
  import SDK/async" GIỮ NGUYÊN. Vỏ `mount_role`: pool **psycopg2** (sync conn, `%s` param bind
  — DB-API giống SQLite `?`, fn gần như chỉ đổi placeholder), mỗi call `acquire` 1 conn rồi chạy
  `fn(conn, **kwargs)` qua `loop.run_in_executor` → **không block event loop** (khớp rủi ro (b)),
  giữ được fn sync (không ép LAB async). Ghi (disburse) = conn transaction ghi-được, bỏ ràng
  read-only. KHÔNG dùng asyncpg (async-only → ép fn async → phá interface). — Đổi: người/architect
  chọn asyncpg + LAB async, hoặc A1.

## ② TỰ-QUYẾT

- **D-33 · main lượt-2 (sau task_done) chạy INLINE `await` trong `_report` (không spawn §6) —
  ACCEPT S1, S2 tech-debt** (backend nêu T1-3 honest — architect ACCEPT sau advisor + verify code)
  — `_report` dòng `await _event_sink → handle_room_event` = main lượt 2 chạy trong task của sub
  (finally shielded). **S1-safe, verify 5 discriminator:** (1) semaphore đã release (async-with
  trong try, _report trong finally) → không giữ concurrency cap; (2) disconnect same-task (inline
  await giữ cùng task sub) → KHÔNG vi phạm landmine #1; (3) multi-sub không nest (try_acquire busy
  → enqueue, drain=ensure_future không await → depth hằng số); (4) shield không trap main-interrupt
  (interrupt qua main_clients cross-task, sub đã pop khỏi sub_tasks trước _event_sink); (5) audit
  attribution guarded (CTX_ACTOR.set('main') đầu run_main_turn — re-entrant fix). **KHÔNG refactor
  §6-spawn ở S1**: convert re-open spine vừa verify (chạy lại cancel-3×/race-5×) cho lợi ích chỉ
  hiện S2 (khi §9 main-retry + concurrency thật → main turn cần task riêng + retry riêng). Backend
  đã đánh dấu 2-line switch — đúng lúc-sửa là S2. Comment tại site `await _event_sink` để S2 builder
  không giả định §6 spawn. — Đổi: S2 khi thêm §9/concurrency → chuyển spawn.
- **D-34 · `store` per-call `psycopg2.connect` (bypass T1-1 pool) — note S1, revisit S2** (backend
  nêu T1-3) — store tạo conn mỗi call thay vì get_pool()/acquire()/release() của T1-1 → 2 connection
  strategy. Ổn dưới 1-worker S1 (bounded to_thread cap). S2 khi tải cao → thống nhất về pool. — Đổi:
  thống nhất pool ngay nếu thấy connection churn.
- **D-31 · `tasks.conv_id` + `messages.conv_id` = TEXT ràng-buộc-mềm (drop FK cứng);
  `conversations.id` VẪN uuid PK** (backend nêu T1-2 — architect RATIFY sau review spine) —
  conv_id là ĐỊNH DANH XUYÊN TẦNG dạng string (registry key idempotency `(conv_id,role)` +
  SDK cwd folder `data/conversations/<conv_id>/` sanitize + SSE topic + event routing), KHÔNG
  chỉ là FK con trỏ. FK uuid cứng cản: (1) test spine dùng conv_id tự do (`"tester-ca-a-conv"`)
  chứng minh mechanics KHÔNG cần tạo conversation thật; (2) conv_id đi qua nhiều tầng string.
  **RATIFY** vì: conversations.id vẫn uuid PK (referential ở tầng app — T1-3 tạo conversation
  trước chat, orchestrator đảm bảo conv tồn tại), ratify-ngay churn ít hơn revert (tester test
  against text + FE mock string đã có), đảo được (downgrade destructive 5↔5 sẵn). **CONTRACT §3
  cập nhật:** `OrchTask.conv_id`/`Message.conv_id` = string (khớp — FE đã dùng string). — Đổi:
  người muốn FK cứng referential integrity ở tầng DB (chấp nhận orchestrator tạo conversation
  uuid trước mỗi dispatch + tester sửa test dùng uuid).
- **D-30 · CONTRACT API+SSE+envelope chốt ở `docs/CONTRACT.md` = 1 nguồn sự thật FE↔BE**
  (architect chốt kickoff S1) — FE/BE tự đoán shape → lệch → ráp đau. BE define, FE ăn theo,
  1 codepath render. Nội dung hợp nhất SPEC §5/§9/§10/§11 + `frontend/src/types.ts` (con FE viết
  khớp SPEC tốt → dùng làm nền). Đổi shape → sửa CONTRACT.md TRƯỚC + báo cả 2 phía. — Đổi: người
  đổi API design.
- **D-29 · Gate mỗi sprint = SPINE SỐNG (không phụ thuộc chất lượng tool LAB) · LAB-timebox
  30ph · roadmap stub-first** (team-lead+user chốt 18/7 — nắn altitude) — (1) **Tiêu chí gate
  KHÔNG phụ thuộc tool/skill LAB**: gate S1 = "spine sống" (chat→Main dispatch→sub→event→tổng
  hợp CÓ NGUỒN→SSE→FE), KHÔNG phải "credit thật ra đúng số". Tool LAB chạy được thì dùng = bonus
  test đường-ghép; giở chứng → STUB ngay (đúng shape), ghi 1 dòng "chờ LAB", đi tiếp. (2)
  **LAB-timebox cứng**: mọi sự cố tool/skill LAB = tối đa ~30ph HOẶC 1 vòng trao đổi → quá thì
  stub+note, KHÔNG phân xử sâu, KHÔNG D-entry dài. (3) **Roadmap xoáy SYSTEM (90% công)**: S2
  canvas+present+4 sub song song (role chưa có = stub) · S3 PHANH end-to-end (khó nhất — attention
  lớn nhất) · S4 control tower+interrupt+trace · S5 polish+demo+swap tool thật. (4) **Nguyên tắc
  cứng: LAB KHÔNG BAO GIỜ là lý do 1 sprint SYSTEM chậm/chặn.** Adapter+mount_role+PG pool = SYSTEM
  thật (lớp cấp-conn của vỏ, N1) — giữ dù stub hay real. — Đổi: người kéo real-tool thành điều
  kiện gate, hoặc đổi thứ tự roadmap.
  - **Bài học điều phối (18/7 — user bắt lỗi):** architect ĐÃ SAI khi dùng tool `Agent` spawn
    subagent ẩn danh cho backend/frontend TRONG KHI roster teammate (backend/frontend/tester) ĐÃ
    SỐNG sẵn → 2 con cùng role đè nhau (roster-backend ∥ spawn-backend cùng ghi backend/). Luật
    cứng: **DISPATCH = SendMessage tới teammate roster theo TÊN, KHÔNG spawn Agent cho role đã có**
    (CLAUDE.md §4/§9 "mỗi role MỘT người — check roster trước khi spawn"). Team-lead điều phối
    roster; architect giao việc qua SendMessage. 2 con spawn đã kill theo lệnh user.
- **D-28 · Seed-load S1 KHÔNG nạp `assumptions.legal_docs_source` (assumption role legal);
  seed_from_lab.py chỉ nạp dòng value parse-được-float** (architect chốt kickoff S1 — phân xử
  technical sau khi backend phát hiện bug) — bảng `assumptions` LAB có dòng `legal_docs_source
  ='gia-thuyet-lab'` (CHỮ). credit.py `_assumptions()` làm `float(r[1])` trên MỌI dòng + chỉ
  `except sqlite3.Error` (KHÔNG bắt ValueError) → credit_assess CRASH trước khi tính DSCR. Đây là
  bug tích hợp cross-role nguồn LAB (dòng legal thêm ở commit sau, credit không lường). **Xử
  N1-sạch = seed-load lọc**: S1 chỉ mount credit (D-17/D-18) → `legal_docs_source` là assumption
  role LEGAL, ngoài scope credit → seed_from_lab.py chỉ nạp assumptions số (value parse float
  được) → PG `assumptions` = **8 rows** (không 9). KHÔNG sửa credit.py (giữ N1/D-27), KHÔNG chạm
  nguồn LAB (D-08 read-only).
  - **Nợ kỹ thuật khi mount LEGAL (sprint sau):** cần nạp `legal_docs_source` cho legal → LÚC ĐÓ
    hoặc LAB fix `_assumptions` lọc numeric (việc LAB, portable), hoặc tách bảng assumptions theo
    role. KHÔNG phải việc S1. — Đổi: người/LAB fix credit._assumptions cho lọc numeric ngay.
  - Bài học architect: verify gate phải CHẠY code-path thật (gọi credit_assess), không tính lại
    bằng SQL tay — kickoff tao verify DSCR bằng query tay nên miss bug này.
- **D-28b · S1 TẠO + SEED THẬT bảng `businesses`(5) + `collaterals`(7), không để rỗng/thiếu**
  (backend tự quyết T1-1 — decide-and-log; brief §A uỷ quyền "có thể tạo cho an toàn, ghi
  DECISIONS") — brief gốc nói "KHÔNG tạo businesses/collaterals ở S1 (prove-spine-first)", nhưng
  verify thực nghiệm: credit-pack (`cust_search`/`cust_get`/`credit_assess`) query 2 bảng này
  **VÔ ĐIỀU KIỆN** (cust_search luôn `SELECT ... FROM businesses`; credit_assess fallback DN;
  cust_get fallback + collaterals). Thiếu bảng → psycopg2 `UndefinedTable` → `db_error` **MỌI
  call 3/4 tool**, không phải "path hiếm C001". Tạo RỖNG cũng hết lỗi, nhưng cùng công sức nên
  seed THẬT (data có sẵn LAB, 5+7 rows) để cust_get(DN)/credit_assess(DN) chạy đúng — khớp ca
  demo "DN X vay 5 tỷ". Migration revision `53a8d21ecbe9` (down_revision đúng chuỗi); models +
  seed TABLES cập nhật; autogenerate-probe xác nhận KHÔNG drift model↔migration. Đảo được:
  drop 2 bảng + gỡ khỏi TABLES. — Đổi: người muốn giữ đúng "chỉ 7 bảng S1", chấp nhận
  cust_search/cust_get trả db_error tới sprint có businesses.
- **D-28c · Bảng `users` (auth) + uuid PK ops dùng `server_default=gen_random_uuid()`**
  (backend T1-1 — scaffold nền auth theo re-scope; decide-and-log) — CONTRACT §1 đòi 2 account
  seed + `POST /api/auth/login`. Thêm bảng `users(id uuid, username unique, pass_hash, role)`
  (SPEC §10) + migration `1aef6233c6ac`. **Bẫy đã xử:** SQLAlchemy `default=uuid.uuid4` là
  app-side (chỉ áp khi INSERT qua ORM); seed/audit/orchestrator INSERT qua **psycopg2 raw** (nhất
  quán seed_from_lab) → id NULL → NotNullViolation. Fix: `server_default=text('gen_random_uuid()')`
  ở cột id (DB-level, áp cho MỌI INSERT kể cả raw). Áp cho `users`; conversations/messages/tasks
  (do scaffold) hiện CHỈ có app-default → **T1-2/T1-3 khi INSERT raw phải hoặc tự sinh uuid trong
  Python, hoặc thêm server_default tương tự** (khuyến nghị: thêm server_default cho nhất quán —
  1 migration nhỏ). Ghi để orchestrator không vấp lại bẫy này. — Đổi: dùng SQLAlchemy ORM session
  cho mọi INSERT (thì app-default đủ, bỏ server_default).
  - **PHÁN QUYẾT ARCHITECT (chốt hướng a):** thêm `server_default gen_random_uuid()` cho
    conversations/messages/tasks NGAY đầu T1-2 (nhất quán users, an toàn bất kể raw/ORM, đảo
    được). Backend xử trong T1-2. Không để orchestrator tự-sinh-uuid-Python rải rác (2 nguồn).
  - **ĐÃ THI HÀNH (T1-2):** migration `448101c1915d` (alter_column server_default 3 bảng ops —
    autogenerate KHÔNG detect server_default trên bảng đã tồn tại, viết tay). Verify: INSERT raw
    3 bảng tự sinh id. no-drift.
- **D-32 · `mount_role.py` tự thêm REPO_ROOT vào `sys.path`** (backend T1-3 — bug fix ca
  end-to-end; decide-and-log) — `roles/` nằm ở repo root (D-26), `mount_role` `import roles.<role>
  .functions`. pytest có `roles` trên path nhờ pyproject `pythonpath=[".",".."]`, NHƯNG uvicorn
  chạy từ `backend/` KHÔNG có repo root trên path → `ModuleNotFoundError: No module named 'roles'`
  khi sub credit chạy qua server thật (ca end-to-end lộ, test không lộ vì pytest path khác). Fix
  N1-sạch: `mount_role.py` (điểm ghép LAB, biết REPO_ROOT) tự `sys.path.insert(0, REPO_ROOT)`
  idempotent lúc import → `import roles.*` chạy dù cwd nào. Verify: ca C001 end-to-end ra
  DSCR 3.709 có nguồn. — Đổi: cài `roles` thành package qua pip -e, hoặc set PYTHONPATH ở
  docker/entrypoint (thì bỏ dòng sys.path).
- **Auth cấu trúc (T1-1):** router/service/security/deps tách tầng (backend.md). JWT HS256
  (PyJWT) secret env `JWT_SECRET` (default dev-only, D-12 .env gitignored) qua cookie httponly
  `shb_token` (EventSource không set header — CONTRACT §1) + fallback Bearer header cho REST/test.
  Password bcrypt. 2 account seed pass=username (`user`/`admin`) — override qua env
  `SEED_USER_PASSWORD`/`SEED_ADMIN_PASSWORD`. Error 4-field toàn hệ qua `app/errors.py`
  (`ApiError` + validation handler → body trần, không bọc `{detail}`). `require_user`/
  `require_admin` deps sẵn cho endpoints T1-2+/S4.
- **D-27 · Conn cấp cho tool LAB = ADAPTER bọc psycopg2 conn "quack như sqlite3.Connection"
  (architect chốt kickoff S1 — decide-and-log; verify bằng đọc credit.py thật)** — psycopg2 conn
  KHÔNG chạy được `functions/credit.py` như-là kể cả sau `?`→`%s`, vì credit.py dùng: (a)
  `conn.execute(sql,args)` — psycopg2 connection KHÔNG có `.execute()` (chỉ `.cursor()`); (b)
  placeholder `?` — psycopg2 chỉ nhận `%s`; (c) row access HỖN HỢP trong cùng file (`dict(row)`
  ở `_one` + `row[0]/row[1]` ở `_assumptions` + `pay_row[0]` ở SUM) — KHÔNG cursor stock nào phủ
  cả 3 (RealDictCursor phá index, NamedTupleCursor phá `dict(row)`). **Fix N1-sạch = adapter ở
  LỚP CẤP-CONN của vỏ** (đúng D-21 A2 "vỏ chỉ đổi lớp cấp-conn, KHÔNG đụng logic tool"): 1 class
  bọc pooled psycopg2 conn cấp `.execute(sql, params)` (tự rewrite `?`→`%s`, mở cursor) trả
  cursor có row factory 3-mode (index + `dict(row)` như `sqlite3.Row`). credit.py copy vào
  BYTE-NGUYÊN, swap vẫn drop-file. **KHÔNG sửa credit.py** (vỏ chạm logic tool = phá N1, vỡ lại
  mỗi lần LAB re-drop). **KHÔNG chờ LAB viết portable** (kẹt spine, phá D-18 "vỏ chủ động không
  để LAB block"). — Đổi: LAB tự viết tool cho psycopg2 trực tiếp (A1), hoặc dùng SQLAlchemy Core
  làm lớp adapter thay vì tự viết.
- **D-26 · Lệnh/layout dev chốt: uv + pytest + ruff (BE) · vite+vitest+tsc (FE) · PG qua docker
  compose** (architect chốt kickoff S1 — decide-and-log, CLAUDE.md §1 đã cho quyền) — đã điền
  CLAUDE.md §1. Layout: `backend/app/` (FastAPI+orchestrator+mount+db), `frontend/`, `roles/<role>/`
  (SKILL.md+functions.py từ D-08), `docker-compose.yml`. DB dev `postgresql://shb:shb@localhost:5432/shb`
  (env `DATABASE_URL`). ruff check = "typecheck sạch" Gate 2. — Đổi: người/architect đổi toolchain.
- **D-23 · "Nhắn riêng cho sub" = UI-only, KHÔNG có API/endpoint riêng** (team-lead chốt 18/7,
  decide-and-log — FE+tester cùng hỏi; SPEC §11 im lặng) — mock có Composer trong SubAgentView
  nhưng SPEC §4.3 chốt "sub không nói với user, mọi bàn giao qua Main" + không liệt kê endpoint.
  → Cửa nhắn-sub là **cửa sổ GIÁM SÁT** (D-20): FE hiển thị trace sống của sub; ô "nhắn" là
  note lưu LOCAL (UI-only) hoặc để sau — KHÔNG tạo endpoint gọi thẳng sub (phá luật "chỉ Main
  giao việc"). Muốn tác động sub → user chat với Main, Main tự re-dispatch. — Đổi: người muốn
  kênh nhắn-sub thật (thì mới cần API + đổi luật §4.3).
- **D-24 · Lobby 3D = polish (B6), sprint đầu placeholder 2D được** (team-lead chốt 18/7,
  decide-and-log — FE hỏi) — three.js nặng; chức năng lõi (canvas card, approval flow, chat,
  trace) ưu tiên trước. Build-order §16 xếp "UI theo mock" ở B6 Polish. FE build placeholder 2D
  cho "phòng làm việc" (grid phòng ban + status dot) ở sprint chức năng, nâng 3D ở polish nếu
  kịp. Ghi deviation, không FAIL vì thiếu 3D sớm. — Đổi: người/architect kéo 3D lên sớm.
- **D-25 · Tester lấy PG conn trực tiếp để verify (đọc `.env`/docker-compose dev)** (team-lead
  chốt 18/7 — tester hỏi) — tester cần `SELECT` thẳng PG (không qua tool MCP) để đối chiếu
  `approvals.status`/`loans.status`/`tool_calls` append-only sau mỗi ca. Conn string dev = từ
  `docker-compose`/`.env` architect chốt ở kickoff (§1 CLAUDE.md). Đúng §5 (query lại row, kiểm
  field). Tool-layer verify: gọi thẳng `REGISTRY[tool](conn, **kw)` (test fn thuần contract §7)
  + gọi qua `mount_role` MCP in-process (test wrapper gated/envelope bad_param) — KHÔNG cần spawn
  SDK session thật. Tester hiểu đúng kiến trúc. — Đổi: architect cấp harness verify chuẩn khác.

- **D-16 · SDK auth = dùng auth máy (claude-cli subscription), KHÔNG env/key trong build**
  (người chốt 18/7) — port pattern `Providers` từ `battle/core/runtime/providers.py`:
  `providers.yaml` giữ 1 provider `claude-cli` (`kind: subscription`, `default: true`) →
  `resolve_env` trả env RỖNG → SDK dùng auth Claude CLI bundle của máy, không cần
  `.env`/API key. Model routing: **main=sonnet · sub=haiku**. Slot `wrap`/`zai` (base-url +
  key) COMMENT sẵn trong yaml — chỉ mở khi build PROD. — Đổi: người nói cắm provider thật.
- **D-17 · `customers` = tool CHUNG của role Credit, KHÔNG phải chuyên gia thứ 5**
  (người chốt 18/7) — 4 chuyên gia = 4 PHÒNG BAN (Credit/Legal/Products/Operations).
  "Khách hàng" là ĐỐI TƯỢNG trong câu hỏi RM (DN X vay 5 tỷ), không phải actor gọi vào hệ.
  LAB `customers.py` (`cust_search`/`cust_get`) → nhét vào toolpack `credit` (tra khách là
  input thẩm định — SKILL credit ghi rõ). — Đổi: người tách customers thành role riêng.
- **D-18 · Products + Operations = STUB cùng contract; VỎ chủ động không để LAB block**
  (người chốt 18/7) — role LAB đang build bên `../shb-digital-experts/` → mount stub trả
  data giả đúng shape, swap function thật khi LAB giao (§7: thả file + dán SCHEMAS + xoá
  stub, `mount_role` không đổi). Cùng cơ chế thì chỉ đổi biến/tên — bản chất nhiệm vụ giữ
  nguyên. **`disburse` (tool gated) build SẴN wrapper gated THẬT của VỎ** (phanh là của vỏ
  §4.4, không của LAB) để B4 chạy end-to-end; swap function khi Ops về. — Đổi: LAB giao bản thật.
- **D-19 · Người duyệt phanh = QUẢN LÝ (account admin), màn Control Tower** (người chốt 18/7)
  — nghiệp vụ thật: RM (user) xin giải ngân → phanh chặn → QUẢN LÝ duyệt (đúng đời thật quản
  lý duyệt cho nhân viên). 2 account seed đúng đề: `user`=RM · `admin`=quản lý·compliance.
  "Control Tower" = MÀN CỦA QUẢN LÝ, không phải actor kỹ thuật thứ ba. — Đổi: người đổi mô hình duyệt.
- **D-20 · Chat-với-sub = CỬA SỔ GIÁM SÁT, không phải kênh giao việc song song** (người chốt
  18/7) — UI: user CHỦ YẾU chat với Main; click 1 sub (panel phải: lobby 3D + chip phòng ban) →
  khung giữa chuyển sang view sub đó (trace sống + nhắn riêng + ⏹ dừng). Nhắn riêng cho sub
  KHÔNG phá luật "sub không nói với user": sub chỉ ghi nhận, kết quả VẪN về Main rồi Main trả
  user (§3). Mock `App.jsx` đã encode (`focus: planner|role`). — Đổi: người mở kênh sub trực tiếp.

- **D-08 · Nguồn tài sản LAB (reuse-copy READ-ONLY)** — copy từ repo anh em
  `../shb-digital-experts/missions/shb-132/`: `tools/functions/*.py` (credit, customers, legal)
  · cụm SCHEMAS trong `tools/server.py` · `skills/<role>/SKILL.md` · `seed/shb-132.db`. Không
  sửa gì bên nguồn. Nguồn VẮNG → hỏi người cấp, **cấm tự chế** (nhất là seed DB). — Đổi: người
  chỉ nguồn khác. *(Roster mount THẬT/stub đã chốt cứng ở D-17+D-18 — không còn "quyết lúc kickoff".)*
- **D-12 · Git: repo PUBLIC `tinhnguyen0110/shb-digital` (lệnh người 18/7)** — đã push init
  lên `https://github.com/tinhnguyen0110/shb-digital` (public). Branch: `master`. **`.mcp.json`
  GITIGNORED** (chứa key Cairn `ck_...` — không lên remote; `git add -A` từng suýt lọt, đã
  `git rm --cached`). Architect commit theo task + push nền như CLAUDE.md §6. — Đổi: người đổi
  visibility / xoay key Cairn.
- **D-13 · Design/mock = THAM KHẢO, không phải nguồn scope (người chốt 17/7)** — có thể thiếu
  hoặc thừa; scope build = TÍNH NĂNG trong SPEC. Đã mã hoá vào CLAUDE.md §1 + frontend.md +
  tester.md. — Đổi: người tuyên bố lại "mock là baseline cứng".
- **D-15 · Alert/notification ngoài (Discord/email) KHÔNG vào scope chính (người chốt 18/7)**
  — demo: toast in-app + badge + approval queue đủ; webhook Discord = TUỲ CHỌN nhét A6 nếu
  kịp (~30'), không phải sprint riêng. — Đổi: người kéo vào scope khi chốt backlog.
- **D-14 · Design bundle đã nhận (17/7), nằm tại `design/`** — export Claude Design: tokens
  ĐẦY ĐỦ (`design/workspace/shared.jsx` — object `T`: bộ màu run/pass/fail/warn/main + font),
  Workspace React mock + lobby 3D + seed snapshot, `design/Digital Expert Guild.dc.html`
  (Login + Tower + Approval). FE port tokens từ `T` → `frontend/src/tokens.css` ở dispatch
  đầu. Blocker B2 đóng. — Đổi: người cấp bản design mới đè vào `design/`.
