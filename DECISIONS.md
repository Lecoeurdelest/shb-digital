# DECISIONS — sổ ngoài-dự-tính (mới nhất trên cùng)

> ① VƯỢT-SPEC: tình huống spec không lường. ② TỰ-QUYẾT: phương án agent chốt khi vắng người.
> Format: `quyết gì — vì sao — cách đổi`. NGƯỜI đọc lại async + override (human-wins).
> Entry đã tiêu hóa vào kit thì xoá — sổ chỉ giữ quyết định CÒN SỐNG (lịch sử đầy đủ: git log).

- **D-58 · Labpack diverge khỏi LAB → RE-SYNC TOÀN FILE về bản LAB hiện tại, không vá tay từng
  function** (architect, T7-1 18/7) — backend phát hiện empirical: `roles/credit/functions.py`
  md5 413a634d ≠ LAB fba6455b (`_assumptions` labpack thiếu graceful-skip value chữ → crash khi
  seed key legal; LAB gốc có try/float/continue). `seed_from_lab._filter_rows` hoá ra là
  workaround cho bản stale này. Quyết: (1) diff toàn file labpack vs LAB, dán summary; (2)
  re-sync TOÀN FILE (T7-2 classify import credit_assess kỳ vọng hành vi LAB hiện tại — sync nửa
  file = frankenstein 2 version); (3) chỉ được đổi phần prod BẮT BUỘC đổi (import path — như
  D-55 legal), 0 sửa logic tay; (4) suite phán — test credit cũ lệch số → tester xét (hành vi
  LAB certified là chuẩn, test theo hành vi cũ thì sửa test có note). Bỏ filter 2 key sau sync.
  — vì sao: labpack cam kết byte-identical là RANH N1/D-27 — diverge âm thầm = mất căn cứ
  certify; vá tay từng function tái phạm đúng lỗi đó. — cách đổi: nếu diff LAB quá rộng làm vỡ
  gate cũ → dừng, báo architect xét scope.

- **D-57 · S9 "KHÁCH MỚI + VÒNG ĐỜI HỒ SƠ": signup + form intake + mail Gmail thật + bell**
  (người chốt 18/7 "ok em cứ code còn app password anh gửi sau" — từ input mentor) — (a) app cho
  người MỚI đăng ký: register account → form intake card (thu họ tên/CMND/thu nhập/mục đích...)
  → tạo hồ sơ customers mới + link owner_id; khách mới tra 3 trụ → không bản ghi → lane YELLOW
  "chưa xác minh" → qua người duyệt (hành vi ngân hàng thật, khớp LAB legal honest-null); khách
  CŨ seed = có sẵn hồ sơ. (b) mail thông báo duyệt/giải ngân qua Gmail SMTP + App Password
  (smtplib stdlib, `SMTP_USER`/`SMTP_APP_PASSWORD` trong .env gitignored — NGƯỜI gửi creds sau,
  code no-op sạch khi env thiếu); gửi best-effort async, KHÔNG chết resume. (c) bell in-app phía
  khách (poll — pattern useApprovalBadge) = lưới khi venue mất mạng. Thứ tự: S7 (3 trụ) TRƯỚC →
  S9. — vì sao: mentor pain "user không phải lúc nào cũng ở app" + "app đăng ký thì làm gì có
  thông tin". — cách đổi: lật thứ tự/scope ở kickoff S9.

- **D-56 · ĐẢO D-54: 2 PERSONA — app là CỬA KHÁCH HÀNG, duyệt là việc NGÂN HÀNG** (người chốt
  18/7, discuss với architect) — flow đúng thiết kế gốc: khách vào app tự chat → đội chuyên gia
  số xử lý → khoản vừa/nhỏ agent TỰ DUYỆT theo ma trận thẩm quyền → chỉ khoản lớn/vượt hạn mức
  bắn về đội ngân hàng duyệt. Cụ thể: (a) role `customer` = KHOANH — chỉ thấy ca của mình,
  KHÔNG quyền duyệt (decide quay lại bank-only, đảo D-54), MAIN được inject danh tính khách;
  (b) role bank (`admin` hiện hành) = toàn quyền — thấy mọi ca + Tower + duyệt ⇒ "2-vai-1-account"
  là TẬP CON miễn phí của tách; (c) demo 2 CỬA SỔ cạnh nhau (khách trái, ngân hàng phải — phiếu
  bay real-time), fallback 1-account bank; (d) **S8 (persona split) làm TRƯỚC S7 (LAB port)** —
  người chốt "backend dừng rồi có thể làm s8 trước", tree sạch, T7-1 hoãn nguyên dispatch.
  — vì sao: ngân hàng muốn tích hợp app cho khách vào trực tiếp; engine giữ 100%, chỉ thêm lớp
  persona. — cách đổi: đảo lại thứ tự sprint bất kỳ lúc nào; ma trận v1 = rule 500tr hiện có,
  S7 chồng lane LAB sau.

- **D-55 · Port LAB legal CERTIFIED: byte-identical TRỪ đúng 1 dòng import; adapter mở WRITE
  có kiểm soát** (architect, kickoff S7 18/7) — (a) `roles/legal/functions.py` chép nguyên bản
  LAB (skill v3 · tool a354fd), CHỈ đổi `from .credit import ...` → import từ labpack credit
  của prod (layout roles/<role>/ tách thư mục; user 18/7 đã chốt "share tool tốt nhất" — import
  server-side python = share, không dup); (b) PGConnAdapter (D-27, vốn read-only) mở thêm
  INSERT+commit+lastrowid CHỈ cho bảng `assessments` (emulate qua `RETURNING id`) — LAB code
  giữ nguyên, quyền ghi khoanh vùng; (c) 2 TẦNG ngưỡng SONG SONG: verdict-hồ-sơ (lane/decision
  từ assessments, auto_approve_max_vnd=2e9 LAB) là điều kiện CẦN mới, rule-tiền 500tr disburse
  hiện hành GIỮ NGUYÊN là điều kiện đủ — thắt chặt, không nới (chi tiết Logic ở dispatch T7-3).
  — vì sao: thước LAB đã trả $35 train + certify, sửa nội dung = vứt certify; adapter khoanh
  vùng giữ nguyên tắc gated-path-raw-psycopg2. — cách đổi: lật ở kickoff sau / khi LAB drop
  bản mới (version 4 dấu trong AGENT-legal-DONE.md).

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

- **D-54 · SPEC §11/§12 mô tả LỆCH quyền duyệt — người sửa 18/7: USER NÀO CŨNG DUYỆT ĐƯỢC mọi
  nghiệp vụ; Control Tower = màn GIÁM SÁT/THỐNG KÊ** — người: "user ở đây vẫn được quyền approve
  mọi nghiệp vụ; Tower kiểu thống kê cost, history tool agent." Nhất quán D-39 (người dùng app =
  nhân viên cấp cao có quyền). Giá trị phanh KHÔNG đổi: điểm là tool không tự chạy — cần NGƯỜI bấm,
  không phải cần đúng chức danh. Sửa: decide + approvals list + audit + interrupt require_admin →
  require_user (no-cookie vẫn 401); Tower đổi cách kể = giám sát & thống kê (audit/cost/trace, tiện
  thể duyệt gom); duyệt CHÍNH vẫn tại card trên canvas trong luồng user. SPEC §11 "admin" đọc là
  "user đã đăng nhập". — Đổi: sau này có phân quyền thật (RM/giám đốc) → thêm role check lại.
- **D-53 · T5-1 polish 2 quyết (architect 18/7):** (a) **font SELF-HOST** (15 woff2 Be Vietnam Pro
  → public/fonts, BỎ Google Fonts CDN — mạng venue thi không tin được, demo không phụ ngoại cảnh
  như seed-reset/provider-standalone; verify 0 request gstatic). Gốc: tokens khai font nhưng
  index.html không import → toàn app fallback system-ui, lệch typography lớn nhất so design.
  (b) **canvas "Đội làm việc" 2D-tiles → SPATIAL CONSTELLATION** (Main giữa glow + sub tỏa góc +
  đường nối chấm SVG, active=chảy xanh) — CSS/SVG THUẦN trong timebox 1 buổi, KHÔNG three.js
  (D-24 3D vẫn hoãn); behavior giữ (click→SubAgentView). Đòn bẩy demo cảnh-1. — Đổi: quay lại
  tiles (CSS class) / nâng 3D S-sau.
- **D-52 · Track nghiệp vụ tín dụng (pain point người ra đề) = ĐỢI LAB TRAINING → PORT; S5 tiếp
  demo-prep + features/polish (NGƯỜI chốt 18/7)** — người ra đề + mentor cho pain: luồng Tín dụng
  → Pháp lý-tuân thủ (QUAN TRỌNG NHẤT — duyệt hồ sơ từ 3 nguồn: Bộ CA/thân nhân-tiền án · CIC ·
  lương/quá trình làm việc) → phân tầng duyệt (vay lớn NGƯỜI duyệt · hồ sơ XANH agent tự duyệt) →
  Vận hành tổng hợp cuối. Architect assess: đáng làm (pain người chấm = rubric ngầm). Người chốt:
  **tool/skill 3-nguồn = TRÍ KHÔN = LAB đang training — check rồi PORT vào** (đúng N1/D-18: LAB
  thả functions+SKILL, vỏ mount tự ăn), vỏ KHÔNG tự chế. LAB chưa xong → S5 tiếp features + polish
  UI/UX. Khi LAB drop: port tools → dạy MAIN luồng tuần tự (prompt) → phanh phân tầng (vỏ, rule
  threshold+verdict-xanh) → sửa demo-script cảnh 1-2. — Đổi: LAB xong sớm → kéo track lên ngay.
  - **Bổ sung (người, cùng ngày): LAB KHÔNG train MAIN — chỉ train riêng legal → MAIN = VIỆC VỎ,
    làm NGAY không đợi:** (a) dạy MAIN_SKILL luồng nghiệp vụ TUẦN TỰ (Tín dụng trước → kết quả
    chuyển Pháp lý KÈM bàn giao trong brief → Vận hành tổng hợp CUỐI) — vỏ sở hữu MAIN_SKILL
    (tiền lệ D-46), verify hành vi bằng ca thật. (b) phanh PHÂN TẦNG phần vỏ: rule threshold
    (amount < ngưỡng → AUTO-APPROVE tại tầng tool, vẫn phiếu+audit "duyệt tự động rule"; vượt →
    chờ người như hiện tại) — phanh là của vỏ (D-18). (c) verdict hồ-sơ-xanh từ legal LAB ghép
    vào rule khi LAB drop.
- **D-51 · Model picker Ở COMPOSER cạnh nút gửi (NGƯỜI chốt 18/7) + "+Ca mới" = DRAFT, ca tạo
  LAZY lúc gửi câu đầu** — người chốt vị trí picker; hệ quả kỹ thuật: BE lưu provider/model per-conv
  lúc TẠO → picker-chọn-sau-khi-bấm-Ca-mới (eager cũ) = model không áp (FE round-trip đầu verify SAI
  thứ tự, architect nghi dây đứt, FE đính chính + fix). **Lazy-create:** "+Ca mới" mở draft (không
  POST) → picker+composer hiện → gõ câu đầu → createConversation(title, provider, model) → picker
  LOCK sau lượt đầu (model chốt per-conv). Backend confirm pattern, không cần PATCH endpoint. Verify
  đúng thứ tự user thật: draft → chọn zai/glm → câu đầu → conv provider="zai" ✓. — Đổi: BE cho đổi
  model per-turn → bỏ lock + eager lại được.
- **D-50 · ĐỔI MÔ HÌNH (NGƯỜI chốt 18/7): chuyên gia = AGENT RIÊNG BIỆT bền (không phải subagent
  dùng-1-lần); MAIN chỉ là ĐIỀU PHỐI VIÊN + cửa nói chuyện với user — LẬT anti-pattern #15
  claude-sdk.md** — người: "agent ở đây là 1 agent riêng biệt chứ không hẳn là 1 subagent; main
  chỉ là người điều phối hoặc nói chuyện trực tiếp với user." Như chi nhánh thật: chuyên gia =
  nhân viên THẬT có danh tính + ký ức việc mình làm, không phải thời vụ gọi-1-lần.
  - **Hệ quả giải cùng lúc:** (a) Hướng-2 "A nhận biên bản" hết nghịch lý — agent Ops của ca là
    MỘT con bền, duyệt xong RESUME đúng nó (nhớ mình xin phiếu), không còn "B lạ". (b) F2b chat-
    với-sub thành tự nhiên (agent bền chat được). (c) Kỹ thuật = port cơ chế MAIN-resume có sẵn
    (S1, landmine đã xử): session lưu theo **(conv, role)** — dispatch role lần 2 cùng ca =
    RESUME session role đó thay spawn mới.
  - **Phạm vi đề xuất (architect, chờ người xác nhận):** bền theo CA trước (mỗi hồ sơ 1 đội, không
    rò thông tin giữa khách — khớp compliance); toàn-cục sau nếu cần.
  - **Docs sửa chủ đích khi build:** claude-sdk.md #15 → "sub disposable là MẶC ĐỊNH cho task
    độc lập; sub-resume per-(conv,role) cho agent bền (D-50)". §3 MAIN-bền/SUB-tươi → cập nhật.
  - **Timing:** S4 đóng bình thường; build ở S5/sau demo ("pass hết task hiện tại trước" — người
    chốt cùng ngày). — Đổi: người thu hẹp lại (chỉ 2 ca resume-sau-duyệt + chat) / mở toàn-cục.
- **D-49 · Đợt T4-2/3/4 — các quyết nhỏ (architect signoff 18/7):** (a) interrupt `target=main`
  SKIP → 400 target_not_supported (SPEC §11 body target mở rộng sau — chỉ huỷ sub trước). (b) compare
  poll "SETTLED" (idle/done VÀ không task queued/running, HOẶC waiting_approval/failed) — break ở idle-
  lần-đầu = so sánh lúc main mới giao việc, demo tệ hơn single. (c) malformed-uuid từ ngoài → catch
  InvalidTextRepresentation Ở STORE (→None→404 tự nhiên) thay validate router — nhất quán _exists_sync
  T3-2, mọi caller hưởng; rà đủ 3 API (interrupt/decide 500→404, audit 400 sẵn). (d) thinking SSE
  LIVE-only không persist (SPEC không đòi bảng thinking; reload chỉ toolcall từ audit). (e) T4-5
  card-trùng = PROMPT-fix không present-dedup (dedup theo title có thể nuốt card hợp lệ — đổi card
  semantics rủi ro N5 không đáng polish). — Đổi: từng mục theo nhu cầu demo.
- **D-48 · tool_calls audit (T4-1): thêm `conv_id` + SSE toolcall thêm `id` — mở rộng tương thích
  SPEC §9/§10 (architect signoff 18/7)** — (a) `conv_id` vào tool_calls: main tool có task_id=null →
  không join tasks được → cần conv_id filter audit theo ca. SPEC §10 là cột TỐI THIỂU; thêm cột phục
  vụ query không phá invariant append-only. (b) `id` vào SSE toolcall {id, task_id, tool, summary,
  cost}: FE dedup (live SSE + reload GET /api/audit chồng → id khớp tránh trùng). (c) `cost`=null
  per-tool CHẤP NHẬN — SDK chỉ expose per-TURN (ResultMessage) → cost meter dùng tasks.cost; per-tool
  defer, KHÔNG giả số. — Đổi: LAB/SDK expose per-tool cost → wire lại.
- **D-47 · Race resume-dispatch = guard A/B re-dispatch TỪ task_done (không đua trước) — N2 tầng điều
  phối** (architect chốt + advisor + tester verify, 18/7) — race: admin duyệt NHANH hơn Ops-lần-1 return
  → resume-dispatch (approval_decided) đua trước unregister → orch_dispatch created:false → MAIN đọc
  task_done STALE → báo "vẫn chờ" (sai), phiếu approved treo. Cơ chế cũ dựa MAIN tự phục hồi = NÃO gánh
  lỗi VỎ (vi phạm "vỏ đưa thông tin ĐÚNG LÚC"). **Fix (`_resume_dispatch_guard` đầu `_turn_runner`, commit
  cd1bd24):** A) approval_decided(approved)+role còn running → SKIP MAIN (grant = approval row approved-
  chưa-used, ZERO state mới). B) task_done+grant+role vừa free → server re-dispatch ops#2 (fire-forget) +
  SUPPRESS MAIN report → ops#2 claim→'used'→grant tự clear. KHÔNG đụng _report ordering. **Verify:** cô
  lập L102 5/5 GREEN + transcript (MAIN dispatch 1 lần created:true, guard-B server-side, không stale-read)
  = tất định bằng CƠ CHẾ không may nhờ MAIN. ("flaky" ban đầu = nhiễm chéo test harness L007 chung, không
  phải sản phẩm.) **HỞ treo S4:** guard-B KHÔNG có trần re-dispatch → ops#2 fail BỀN → task-storm (money-safe,
  rollback atomic; bound cần migration attempt-state = hố S3 → T4-0). — Đổi: bound loop / đổi grant sang
  registry field.
- **D-45 · Provider cho SDK = PORT pattern `battle/core/runtime/providers.py` (KHÔNG chế bánh xe)** (người
  chốt 18/7 "battle đã giải provider, env còn hiệu lực, đừng tự chế") — ROOT bug :8000 treo khi
  dispatch: shb `ClaudeAgentOptions` KHÔNG set `env=` → SDK rơi về CLI auth bundled (giống provider
  `claude-cli` subscription của battle); nếu server thiếu CLI auth / hết quota → `query()` HANG (không
  fail nhanh) → main treo, 0 dispatch. **Battle đã giải:** `env={ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN,
  ANTHROPIC_API_KEY}` per-session vào `ClaudeAgentOptions.env` (KHÔNG đụng process env → đa-provider song
  song). Config: `battle/configs/providers.yaml` (claude-cli subscription default · zai=GLM · wrap=GPT) +
  secret `battle/.env` (`${VAR}` interpolate). Probe 18/7: zai SỐNG (trả model list), wrap host nội bộ
  không reachable ngoài psa.team. **Quyết:** port Providers registry (yaml+.env parser + resolve_env) vào
  shb backend; MAIN/SUB options nhận provider_env. Provider mặc định = claude-cli (subscription, env rỗng
  — chạy như hiện tại NẾU server có CLI auth); fallback đa-provider (zai) khi cần floor/không CLI auth. —
  Đổi: người chọn provider khác / chỉ dùng CLI auth (thì fix treo = đảm bảo CLI auth có trên server).
  - **D-45b · Model/provider CHỌN ĐƯỢC trên UI + env setup (người chốt 18/7):** (1) **DEFAULT = blunder/
    subscription** (claude-cli, env rỗng — CLI auth máy chủ, đơn giản nhất, không cần key). (2) **User
    chọn model trên UI** — dropdown đơn giản: `GET /api/models` trả list (name/kind/models/has_key — KHÔNG
    lộ key, port `Providers.public_view()` battle) → FE dropdown → chat/conversation nhận `model?`/`provider?`
    optional (bỏ trống = default). (3) **ENV setup:** `.env` shb khai provider default + biến key (mẫu
    `.env.example`); `providers.yaml` khai 3 kind: `subscription` (blunder/CLI, env rỗng) · `api` custom
    (base_url+key, vd zai/wrap) · `api native` (Anthropic thẳng, ANTHROPIC_API_KEY). Port nguyên pattern
    battle (`POST /sessions` nhận provider param + `GET /models` + `_base_.yaml` model ladder). — Đổi:
    người khoá 1 model (bỏ dropdown) / đổi default sang api-native.
- **D-44 · Sửa `roles/operations/SKILL.md` khớp T3-1 (disburse ĐÃ mount) — KHÔNG vi phạm N1** (tester
  tìm 18/7, architect quyết) — SKILL.md operations dòng cũ nói "giải ngân CHƯA có, sprint sau" NGƯỢC
  thực tế (T3-1 mount disburse thật). Rủi ro: Operations sub đọc skill trước tool-list → có thể từ
  chối gọi tool / trả "chưa hỗ trợ" (loại lỗi skill-lệch-thực-tế đã thấy gate S2). **N1 GIỮ:** file
  này là STUB VỎ TỰ VIẾT (D-35 "vỏ viết, LAB đè khi đẻ thật") — KHÔNG phải skill LAB thật → sửa cho
  khớp cơ chế vỏ (phanh disburse) là việc của vỏ, không đụng trí-khôn LAB. Khác D-36 (present-skill):
  D-36 dùng file provisional CẠNH vì không được đụng SKILL gốc; đây SKILL gốc là của vỏ nên sửa thẳng.
  Thêm mục "Giải ngân (disburse — CÓ PHANH)": gọi tool thật, lần đầu bị chặn = ĐÚNG quy trình (không
  nói "chưa hỗ trợ"), sau duyệt gọi lại chạy thật + biên nhận. — Đổi: LAB đẻ operations skill thật →
  xoá stub này (cả mục disburse), swap skill LAB.
- **D-46 · Dạy MAIN_SKILL route "giải ngân" → dispatch disburse (KHÔNG vi phạm N1 — vỏ tự viết)**
  (backend tự-quyết 18/7, đã báo architect+FE; đảo được — prompt text) — LỖ HỔNG routing tìm khi
  e2e S3 qua chat: hệ hỗ trợ disburse ở MỌI tầng (ops CÓ tool + allowed_tools, ops SKILL D-44 CÓ mục
  giải ngân, phanh+phiếu+card+resume đủ) TRỪ chỗ MAIN định tuyến. `main_session.py` MAIN_SKILL dòng cũ
  mô tả `operations = "lộ trình xử lý hồ sơ"` DUY NHẤT → user nói "Giải ngân L001 5 tỷ" thì main dịch
  về brief gần nhất nó biết = "lập lộ trình timeline" → ops chạy ops_plan, KHÔNG gọi disburse → KHÔNG
  có phiếu (FE chờ mãi không thấy ticket). **Fix hẹp:** dạy main operations có HAI loại việc, phân
  biệt theo yêu cầu — "lộ trình/timeline" → brief ops_plan; "GIẢI NGÂN/chuyển tiền" (có mã khoản +
  số tiền) → brief nói THẲNG "thực hiện giải ngân... Gọi tool disburse" (KHÔNG viết "lộ trình", nếu
  không model co về ops_plan vì chữ "giải ngân" ở cả hai). **N1 GIỮ:** MAIN_SKILL là "vỏ TỰ VIẾT
  (mỏng)" (comment dòng 37 file) — điều phối/routing là VIỆC CỦA VỎ, không đụng trí-khôn LAB. **Verify
  THẬT (không tin diff skill):** chạy lại repro `chat "Giải ngân khoản vay L001 số tiền 5 tỷ đồng"` →
  main brief ops = "Thực hiện giải ngân... Gọi tool disburse" ✅ → ops gọi disburse → phiếu pending +
  card approval canvas ✅ → admin decide approved → resume → giải ngân thật (loan='disbursed',
  used_at+receipt SET, no-double) ✅. Suite test_gated+test_approvals 27 passed sau edit. — Đổi:
  LAB/architect đổi cơ chế routing, hoặc design chốt disburse trigger qua NÚT pipeline thay vì chat.
- **T3-2 THI HÀNH · Resume (admin decide → event đánh thức main) — REUSE handle_room_event, KHÔNG
  chế cơ chế mới** (backend T3-2, architect Logic) — khép vòng phanh: người bấm Duyệt/Từ chối UI →
  API decide → main giao lại Ops → gọi lại disburse → wrapper bước 2 claim → chạy. (1)
  `store_approvals.py` tách (D-34 — store.py 409 LOC): `list_pending(conv_id?)` + `decide(id,
  decision, decided_by, reason)` ATOMIC một chiều `UPDATE…WHERE status='pending' RETURNING` →
  rowcount 0 (2 admin bấm/double-wake) → None → API 409 (đã quyết) / 404 (không tồn tại, phân biệt
  qua approval_exists). (2) API `app/api/approvals.py`: GET /api/approvals?status=pending (admin) +
  POST /api/approvals/{id}/decide (admin, body {decision:approved|rejected, reason?}) → 400 decision
  lạ. (3) `_emit_and_wake`: SSE approval.decided {phieu:{id,action,status,decided_by,reason}} + ĐÁNH
  THỨC main qua `handle_room_event(conv_id, "approval_decided", payload)` — CÙNG đường task_done sub
  (§4.4, KHÔNG chế mới). Cả approved LẪN rejected đánh thức (main báo user). (4) `run_main_turn` nhánh
  event `approval_decided`: prompt nói THEO HÀNH ĐỘNG + tham số (KHÔNG phiếu-id §15) — approved→giao
  Ops gọi lại, rejected→báo user. CTX reset D-33 đã có (approval_decided qua run_main_turn giống
  task_done — KHÔNG thêm contextvar mới). Verify: decide atomic + 400/404/409 + đánh thức reuse +
  prompt + HTTP thật (decide→200 approved, 2 lần→409). 14 test. D-42 (agent không block/poll) giữ.
  — Đổi: LAB đẻ role duyệt riêng, hoặc đổi decide semantics.
- **T3-1 THI HÀNH · Phanh wrapper THREAD-CONN (1 conn/tx xuyên claim+inner+receipt) — chống
  money-doubling cơ bản (D-40)** (backend T3-1, advisor + architect review) — `app/orch/gated.py`:
  (1) `payload_hash` 1 hàm (float-normalize + None/non-biz drop + sort — verify equivalence
  int/float/order/ts cùng hash, 1tỷ≠5tỷ). (2) `_gated_txn` = LÕI ĐỒNG BỘ 1 psycopg2 conn (raw
  %s, KHÔNG PGConnAdapter — adapter chỉ cho LAB read tool `?`), 1 tx, 4 bước, KHÔNG await bên
  trong, chạy qua `asyncio.to_thread` (D-22 không block loop). **INVARIANT: receipt-save TRONG
  CÙNG tx với claim+inner → `status='used' ⟺ receipt present`** — inner throw → rollback → phiếu
  về 'approved' (retry sạch); tách tx = money-doubling window. (3) SSE STRICTLY SAU commit
  (`_gated_txn` trả to-emit struct → handler emit sau to_thread — rollback không emit card ma).
  (4) card approval type='approval' NGOÀI present enum (vỏ tự sinh §6, id vỏ-inject). (5)
  GATED_WHITELIST={disburse} wire ở mount loop (name in whitelist → gated handler; read giữ
  per-call). disburse stub vỏ (D-18) ghi loans.status='disbursed'. Migration approvals (8e8edc5b9187,
  server_default uuid + composite index key, downgrade plain drop). Verify 4 nhánh + invariant
  rollback + card SSE (11 test). D-40: atomic claim + biên nhận CÓ, KHÔNG crash-injection gate.
  N1 giữ (disburse fn nhận conn vỏ cấp). — Đổi: LAB đẻ ops disburse thật → swap GATED_TOOLS['disburse'].
  - **Hở đã biết (deferred/acceptance — advisor review, KHÔNG phải bug, ghi để không thành gap im
    lặng):** (a) **Race sinh phiếu-RÁC (tester tìm 18/7, FIX bằng advisory-lock)** — 2 gọi disburse
    đồng thời (mỗi gọi conn/tx riêng qua to_thread, READ COMMITTED không thấy phiếu đối thủ) → lệnh
    thua rớt bước 4 → đẻ phiếu pending + card GIẢ. **Money invariant GIỮ** (13/13 tester + 5/5 architect,
    luôn đúng 1 disbursed; biên nhận bước 1 + claim atomic chặn double-spend). Rác cosmetic, KHÔNG tiền
    đôi. **FIX: `pg_advisory_xact_lock(hash(conv_id,action,ph))` đầu `_gated_txn` — serialize per-key,
    con thua chờ con thắng commit → thấy used/pending → không đẻ giả; cứu CẢ 2 variant.** (partial-
    unique-index KHÔNG đủ: `used` không nằm trong index → variant gọi-sau-used lọt → dùng advisory-lock.)
    lock_key = `int(sha256(f"{conv_id}:{ph}")[:15],16) & 0x7FFF...` — **sha256 KHÔNG `hash()` Python**
    (PYTHONHASHSEED randomize → không deterministic cross-process; D-38 `--reload` spawn process mới +
    tương lai đa-worker). Hành vi con-thua sau fix: chờ lock → thấy phiếu `used` bước 1 → trả **biên
    nhận cũ** (disbursed:true + hint "ĐÃ thực thi"), KHÔNG execute lần 2 → verify 10× `[EXEC,RECEIPT]`,
    execute_thật=1, used=1, total_phiếu=1 (0 rác), loans disbursed 1 lần. (Assert test đo invariant
    bằng `used_count==1`/phân biệt EXEC-no-hint vs RECEIPT-có-hint, KHÔNG `disbursed_count==1`.)
    (b) **`amount` default=0** → disburse thiếu amount vẫn chạy,
    card duyệt hiện amount trống → admin duyệt mù. Chấp nhận demo (Ops luôn gửi amount); siết =
    đổi schema `amount required`. (c) **Bằng chứng "no-double" đến từ CƠ CHẾ** (phiếu `used` +
    row-lock EvalPlanQual claim, advisor xác nhận đúng), KHÔNG từ đếm side-effect — vì disburse stub
    chỉ set `status='disbursed'` (idempotent, không có sổ tiền để trừ đôi). Đúng scope stub; LAB đẻ
    disburse có side-effect đếm được → test phải assert count.
- **D-42 · Luồng CHỜ-DUYỆT: agent KHÔNG block/poll — chặn→báo main→KẾT THÚC LƯỢT; đánh thức là
  T3-2** (người hỏi 18/7, architect trả) — Ops gọi disburse → wrapper trả `approval_required` +
  hint "Đã gửi chờ duyệt — báo main và kết thúc lượt". Agent KHÔNG đứng đợi (không deadlock để né →
  **KHÔNG cần auto-approve**). Người bấm Duyệt trên UI → API decide (T3-2) → **event đánh thức main**
  → main giao lại Ops → gọi lại disburse → wrapper bước 2 claim → chạy. "handler resume" người thấy
  thiếu = T3-2 (đã plan, dispatch ngay sau commit T3-1), KHÔNG phải bế tắc. Auto-approve sẽ phá đúng
  deliverable #3 (phanh = két cần chìa) → mất thứ để demo. Nếu cần đường-tắt-test lúc T3-2 chưa xong:
  thêm env `DEV_AUTO_APPROVE` tách bạch (default OFF, giống D-39), KHÔNG đụng lõi phanh — chờ người
  xác nhận có muốn không. — Đổi: người muốn auto-approve thật → bật env, lõi phanh nguyên.
- **D-40 · S3 PHANH = HAPPY-PATH demo (bấm-duyệt-trên-UI chạy được); atomic/biên nhận = code cơ
  bản theo spec KHÔNG đào sâu; BỎ crash-injection gate** (NGƯỜI chốt 18/7 — nắn altitude) — demo
  = luồng: agent gọi disburse → két CHẶN → thẻ approval hiện UI → admin BẤM duyệt → giải ngân chạy
  (loans.status='disbursed') → xong. Đây là 80% giá trị + thứ giám khảo bấm-nút-thấy.
  - **Chống-giải-ngân-đôi (atomic claim + biên nhận):** là xử lý trường hợp LỖI (retry mạng đứt /
    race 2-gọi-đồng-thời) — chỉ xảy ra app THẬT production tải cao. Demo happy-path KHÔNG gặp. Trong
    demo "giải ngân" = ghi 1 dòng DB (loans.status), KHÔNG tiền thật → đôi = ghi status đôi vô hại.
  - **VẪN LÀM MỨC CƠ BẢN** (rẻ, ăn điểm nghiệp vụ bank — code đi-kèm wrapper 4-bước, viết 1 lần là
    có): biên nhận theo key + atomic UPDATE…WHERE claim. KHÔNG phải việc riêng, KHÔNG tốn thêm mấy.
  - **BỎ (robustness production, quá tay demo 48h):** test dàn cảnh crash-giữa-chừng / kill server
    chứng minh không-đôi. Gate S3 KHÔNG ở ca crash-injection.
  - **GATE S3 = happy path:** agent gọi giải ngân → két chặn (approval_required + phiếu pending +
    card approval UI) → admin bấm Duyệt → event resume → giải ngân chạy → loans.status='disbursed'.
    Bấm Từ chối → không giải ngân. Atomic/biên nhận CÓ trong code (spec) nhưng KHÔNG điều kiện gate.
  - **Vai:** mọi người vào thẳng ADMIN full quyền (D-39 skip-auth — người cấp cao dùng tool gated).
    Bỏ phân biệt RM/admin ở luồng demo (người chat = người duyệt = admin). — Đổi: người muốn 2-vai
    thật (RM xin, admin duyệt riêng) hoặc kéo crash-robustness vào scope.
- **D-39 · DEV skip-auth (`DEV_SKIP_AUTH`) → vào thẳng vai ADMIN full quyền; flag OFF = auth như
  cũ** (NGƯỜI yêu cầu — architect design; dispatch SAU verdict gate S2) — dev/demo nội bộ tiện:
  bỏ login, mọi request = admin seed. **Thiết kế (1 chỗ, an toàn):**
  - **BE:** env `DEV_SKIP_AUTH` (bool). Deps `require_user`/`require_admin` (app/auth/deps.py) —
    đầu hàm: flag ON → trả THẲNG claims admin seed (`{username:'admin', role:'admin'}`), bỏ qua
    cookie/JWT. Flag OFF → auth JWT như cũ. Skip CHỈ ở deps layer (1 chỗ, không rải). Default env
    trong docker-compose dev = ON (lệnh user "hiện tại tất cả vào admin"); code default OFF (an toàn
    — flag phải bật tường minh).
  - **AN TOÀN (architect thêm):** boot log CẢNH BÁO khi ON — "⚠️ DEV_SKIP_AUTH ON — mọi request =
    admin, KHÔNG dùng prod/demo thật". Tránh lọt prod im lặng. Prod/demo = env OFF.
  - **FE:** boot check `GET /api/auth/me` (hoặc /config) → BE trả admin không cần cookie → FE skip
    màn login, vào Workspace vai admin. Flag OFF (BE 401) → login flow như cũ (T1-4++ GIỮ, không vứt).
  - **Test:** auth test cũ giữ (flag OFF); thêm test flag ON → require_* trả admin.
  - **Sequencing:** dispatch code SAU verdict gate S2 (:8000 --reload, sửa code = reload = phá gate).
    Nhét commit đóng S2 nếu gọn, hoặc task đầu S3. — Đổi: người siết bỏ skip-auth (chỉ login thật).
- **D-38 · DEV SERVER: 1 canonical `:8000` chạy `uvicorn --reload`, chủ = backend, CẤM mọc port**
  (NGƯỜI chốt — thay/mạnh hơn D-37) — root cause 3-server-lạc (8000/8002/8004): server không
  auto-reload → fix xong server stale → agent né restart (sợ giẫm phiên + sandbox không pkill) →
  mọc port mới → suýt gate trên code cũ + 2 chỉ-dẫn-port đâm nhau. **Luật:** (1) MỘT server
  `:8000` `--reload` (code fix tự nạp, hết stale, hết lý do mọc port); (2) chủ = **backend** (dựng
  detached + health-check); restart cứng (đổi env/migration) → báo 1 câu trước; (3) **CẤM agent tự
  mở port mới** cho verify — mọi e2e/browser đánh :8000; unit/integration dùng in-process
  (TestClient/ASGI), không cần port; (4) server cũ lạc → backend dọn (có quyền kill), giữ :8000.
  **Lưu ý --reload:** reload wipe in-process state (registry/room) — chấp nhận dev (boot-cleanup xử
  cờ mồ côi §8); gate-run cần state nguyên → chạy xong đừng sửa file giữa chừng. — Đổi: người cho
  nhiều server song song (thì scope _cleanup_orphans theo instance-id). *(D-37 gộp vào đây.)*
- **D-37 · DEV: 1 SERVER CANONICAL cho live-SDK test (không multi-server-cùng-DB)** (architect
  phân xử T2-4 — tester phát hiện) — `_cleanup_orphans` (§8 boot-cleanup) UPDATE tasks running
  toàn DB ở MỌI boot() = ĐÚNG thiết kế 1-worker prod (registry sống trống sau restart → task
  running DB là cờ giả). NHƯNG multi-server-dev-cùng-1-Postgres → mỗi boot bắn tasks running của
  server khác ("server restart" oan). **KHÔNG sửa code** (prod 1-worker đúng — §1/§8). **Quy ước
  dev: 1 server canonical DUY NHẤT sống cho live-SDK/gate test** — port 8000 (CLAUDE.md §1), khởi
  từ commit HEAD mới nhất, FE + tester cùng trỏ. Kill server cũ trước khi khởi mới (tránh code cũ
  + stomp). — Đổi: nếu cần nhiều server dev song song → scope `_cleanup_orphans` theo instance-id
  (thêm cột/env), nhưng KHÔNG cần cho demo 1-worker.
- **D-33 ĐÓNG (T2-2 concurrency test GREEN) · inline-await giữ, KHÔNG cần §6-spawn** (backend
  T2-2 — advisor: green đóng note, chỉ red mới license convert) — test STAGGERED 3× (`tests/
  test_concurrency_d33.py`): main-turn CHẬM giữ slot in-flight → 2 sub delay khác nhau báo
  task_done KHI main busy → mỗi task_done ĐÚNG 1 main wake, no lost/double, board consistent.
  + 4-sub no-event-lost. → inline-await `_report→handle_room_event` AN TOÀN dưới concurrency
  thật. D-33 note S2 tech-debt ĐÓNG — không convert §6-spawn (convert re-open spine cho lợi ích
  không có). 2-line switch vẫn để dành nếu S3+ đổi. — Đổi: RED ở test tương lai → convert.
- **T2-2 · Legal mount THẬT + products/ops STUB (skill vỏ có present) — 4 role đủ** (backend
  T2-2) — legal.py byte-identical LAB (diff xác nhận) mount qua adapter D-27 (verdict clear chạy
  thật); 4 bảng legal (legal_requirements/owner_documents/collateral_legal/restricted_purposes)
  migration + seed từ LAB (9/71/7/6 rows). products/ops = STUB vỏ-viết (isMock:true MỌI return,
  1 tool/role, SKILL vỏ CÓ present type=options/timeline — D-35). discovered_roles = {credit,
  legal, products, operations}. Legal skill LAB KHÔNG present → legal real-card = bonus (không
  provisional cho legal S2 — D-35 nợ LAB). — Đổi: LAB đẻ products/ops thật → xoá stub (mount không đổi).
- **D-36 THI HÀNH · Provisional present-skill `roles/<role>/SKILL.present.md` (vỏ viết, file CẠNH)
  → real-sub card GATING** (user nới ranh D-35; backend thi hành T2-1, verify live trong timebox)
  — vỏ ĐƯỢC viết bản mồi dạy sub gọi present, NHƯNG file TÁCH (`SKILL.present.md`) mark
  `<!-- PROVISIONAL — LAB đè -->`, KHÔNG sửa `SKILL.md` gốc LAB (N1 giữ). `mount_role` đọc
  SKILL.md + append SKILL.present.md nếu tồn tại. LAB drop skill thật có present → xoá file
  provisional, mount tự bỏ append (drop-in, 0 dòng code đổi). **Verify LIVE:** credit sub
  tool_calls=[cust_get,credit_assess,credit_cic_get,PRESENT] → card metric task_id=task.id
  (vỏ-inject) items có source → real-sub card từ BONUS lên GATING. Nguyên tắc D-36: thiếu
  skill/tool → dựng CƠ BẢN + PROVISIONAL mark + đi tiếp, KHÔNG flag-chờ-LAB. — Đổi: LAB dạy
  present trong skill thật → xoá provisional.
- **CONTRACT §3/§4 +cards (T2-1, D-30 đổi-shape-báo-trước):** GET full-state thêm `cards[]`
  (canvas reload — canvas-present §4); SSE `card` event S1→S2 dùng. `interface Card {id, conv_id,
  task_id, type, ts, ...data}` (data=title/items/sources agent bơm; id VỎ-inject §15). FE thêm
  render cards; tester cập nhật assert full-state 3-key→4-key. — Đổi: người đổi shape canvas.

- **D-36 · Tool/skill THIẾU → vỏ dựng bản CƠ BẢN (PROVISIONAL) để hệ chạy — LAB bổ sung/đè sau**
  (NGƯỜI chốt 18/7, nới ranh D-21/D-35) — việc của đội là HOÀN THIỆN SYSTEM + tính năng; tool/skill
  KHÔNG BAO GIỜ là lý do block. Thiếu skill/tool cho tính năng hệ cần (vd skill chưa dạy `present`)
  → vỏ VIẾT BẢN CƠ BẢN đủ chạy, đánh dấu `PROVISIONAL — LAB đè` (comment đầu file/section riêng,
  không trộn vào phần LAB gốc), LAB nuôi bản thật thay sau (drop-in). Ranh vẫn giữ: KHÔNG sửa đè
  file LAB gốc đã copy — bản provisional để CẠNH/append tách biệt, swap sạch. — Đổi: người siết
  lại "chỉ LAB được viết skill".

- **D-35 · Gate S2 (canvas) = MAIN present + STUB-role present (vỏ-controlled); real-sub card
  (credit/legal) = BONUS không-gate — vì skill LAB KHÔNG gọi present (N1 cấm vỏ sửa)** (architect
  chốt kickoff S2 — advisor bắt + grep verify) — `present` là việc VỎ (T2-1), nhưng AI-GỌI-present
  là SKILL = việc LAB (N1). Grep xác nhận: credit SKILL + legal SKILL (copy từ LAB world không có
  canvas) KHÔNG gọi present → real-sub card KHÔNG xuất hiện, và N1 CẤM vỏ sửa skill thật để thêm.
  → Gate mechanism trên vỏ-controlled: (a) MAIN skill (vỏ tự viết) thêm present-call; (b) stub role
  products/ops SKILL (vỏ viết) có present-call. Real credit/legal card = bonus.
  - **CẬP NHẬT (D-36 nới ranh — architect quyết gate):** vỏ ĐƯỢC viết PROVISIONAL present-skill cho
    credit/legal (file cạnh `SKILL.present.md` append lúc mount, mark `PROVISIONAL — LAB đè`, KHÔNG
    sửa file LAB gốc) → **real-sub card NÂNG từ bonus lên GATING** nếu provisional làm được trong
    timebox ~30ph (T2-1). Không kịp → giữ gate vỏ-controlled (main+stub), provisional ở T2-sau.
    Nợ LAB (skill thật dạy present) VẪN còn — provisional chỉ là mồi tạm, drop-in thay sạch. — Đổi: LAB cập nhật
  SKILL dạy present → real-sub card thành gating; hoặc người cho phép vỏ thêm 1 dòng present vào skill
  (phá N1 — cần user chốt).
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
  - **HỆ QUẢ inline-await (T2-4 tester bắt CTX_TASK leak):** inline path (sub done → _report →
    run_main_turn TRONG task sub, KHÔNG spawn) → contextvar KHÔNG auto-reset → `run_main_turn` phải
    reset TAY **ĐỦ 3 contextvar (CONV/ACTOR/TASK)**. T1-2 fix CTX_ACTOR nhưng SÓT CTX_TASK (anh em
    cùng họ) → MAIN present(document) stamp task_id sub thay null (vi phạm N5). Fix T2: reset cả 3.
    **Luật S3+:** thêm contextvar mới (vd CTX_APPROVAL) → PHẢI thêm reset ở run_main_turn (mirror).
    Architect nhận sót: discriminator #5 khi accept D-33 chỉ nói CTX_ACTOR, không liệt kê đủ.
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
- **D-43 · LẬT D-23 — user CHAT TƯƠNG TÁC THẬT với sub (kênh trực tiếp phụ), + click-sub→full-conv
  + huỷ sub đang chạy** (NGƯỜI chốt 18/7, human-wins — thay D-23 dưới đây) — backlog S4:
  - **F2a (S4 core, MUST):** click sub ở panel phải → box chat chuyển sang FULL conversation của sub
    (D-20 SubAgentView mock ref) + nút HUỶ sub đang chạy (interrupt per-agent §4.3 + API /interrupt
    §11 — đường huỷ đã có trong spine sub_tasks).
  - **F2b (S4 stretch SAU F2a):** user chat THẬT với sub (không chỉ note UI-only như D-23). Kỹ thuật:
    port pattern `say()` interject của LAB `core/runtime/session.py` (interject vào SDK session sống,
    lock serialize — đã chạy thật). Cần sub-session đa lượt (hiện one-shot). **Luồng bàn giao CHÍNH
    vẫn qua Main** (§3/§4.3 giữ cho verdict/report); chat-sub = kênh tương tác trực tiếp PHỤ, không
    thay Main-giao-việc. — Đổi: người thấy chat-sub gây loạn luồng → tắt F2b, giữ F2a giám sát+huỷ.
- **D-23 · [LẬT bởi D-43 18/7] "Nhắn riêng cho sub" = UI-only, KHÔNG có API/endpoint riêng** (team-lead chốt 18/7,
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
