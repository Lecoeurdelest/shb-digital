# Sprint 6 — End

**Theme:** Demo-safety cluster (user chốt "fix UX-treo khi SSE cái này trước đi"): UX-treo SSE-đứt
+ đóng ngoại lệ race-status S5 + tách DB test + restart-sạch + smoke e2e liền mạch.
**Commit:** bb17cd8 (UX-treo cluster) · ca59f5b (tách-DB + pkill) · 750ccf8 (smoke + hardening) ·
66c3aeb (đóng)

## Kết quả từng task

### T6-1 — done (UX-treo SSE-đứt — phân tầng + fix, bb17cd8)
- **Root thật (thực nghiệm kiểm soát):** `EventSource.onerror` KHÔNG nổ khi server chết SIGKILL
  (không FIN) → code reconnect+refetch của FE (ĐÚNG, có sẵn) không bao giờ được gọi — treo là
  FE không biết stream đã chết, không phải thiếu logic.
- **Fix:** heartbeat = **data-frame** `{"type":"ping",...}` mỗi 15s (CONTRACT §4 data-only —
  comment-frame vô hình với EventSource native) + FE **watchdog 25s** (im lặng → close +
  reconnect + refetch-on-reconnect — code cũ nay chạy thật) + `type='ping'` không render.
- **Kèm cụm:** boot-cleanup **time-scope** (`queued_at < boot_time` — chỉ chôn task thế hệ
  trước, hết oan-sai task mới) + conv stuck 'running'→'idle' (giữ waiting_approval) +
  **guard-B write-war** (`failed{reason='server restart'}` = cờ hạ tầng, bị done/timeout thật
  đè; terminal thật bất biến) — **đóng ngoại lệ race-nhấp-nháy-status S5**.
- **Verify:** tester kill-mid-flight → hệ TỰ LÀNH (FE tự reconnect + refetch, task thế hệ cũ
  chôn đúng, task mới sống); suite + live chain.

### T6-2 — done (tách DB test, ca59f5b + 750ccf8)
- **Bằng chứng:** `TEST_DATABASE_URL` override TRƯỚC app import → suite chạy `shb_test`
  (auto-setup CREATE DB + migrate + seed_lab + seed_users, idempotent); không set env → DB
  chính + WARNING. Architect verify độc lập: 224 pass trên shb_test, DB demo 0 rác mới (64 rác
  nằm đúng shb_test). Edge half-setup (thiếu users → 401 oan) đóng bằng `_db_ready` kiểm cả
  users. Đóng luật vận hành "không pytest trên DB demo" bằng CODE thay vì kỷ luật miệng.

### T6-3 — done (restart-sạch pkill, ca59f5b)
- **Bằng chứng:** `fuser -k` chỉ giết CHILD giữ port → uv-wrapper PARENT sống sót (nghi gốc
  finding #2: 2-process → 2-boot-cleanup → mystery `failed{server restart}` trên task mới).
  Fix: `pkill -f "uvicorn app.main.*$PORT"` (cả parent+child) + assert-0 process trước start +
  kill -9 fallback. Guard-B là lưới an toàn bất kể nguồn ghi.
- **Deviation:** xác nhận live 2-process = lần restart kế bằng script mới (đếm process, dán
  output) — không blocking, guard-B đã chặn hậu quả.

### T6-4 — done (smoke e2e 5-deliverable liền mạch, 750ccf8 — tester viết)
- **Bằng chứng:** 1 test live-SDK opt-in `RUN_LIVE_SDK=1` đi TRỌN 5 deliverable một lượt
  (fan-out → auto-approve → phiếu-decide-resume → audit → compare), loan cô lập L109/L111,
  evidence-preserving khi fail, helper `_wait_for_settled` (idle + mọi task chung-cuộc — bịt
  "thoáng-idle" fan-out từng gây FAIL oan + giết sub ngầm). **PASS live 4'25"** — regression
  demo vĩnh viễn, chạy trước mỗi lần demo thật.

## 3 Quality Gates
- [x] **Gate 1 — API**: heartbeat giữ envelope CONTRACT §4 (data-frame only, không event:/id:) ·
  không endpoint mới · test API cũ pass · 4-field error không đổi · không primitive ngoài SPEC
  (watchdog/ping = SSE thuần, không WebSocket).
- [x] **Gate 2 — Function**: unit/integration mới (guard-B, time-scope, ping, watchdog +4 FE,
  smoke opt-in) · edge (SIGKILL không-FIN, task queued trong khe boot, test-db half-setup) ·
  fail-open/closed nói rõ (cờ hạ tầng bị đè, terminal thật bất biến) · ruff 0 lỗi + tsc sạch ·
  không test tự-xác-nhận (tester viết smoke, author≠checker) · FE self-verify browser
  (watchdog reconnect) · LOC ≤400 · không copy-paste (smoke tái dùng pattern, dedupe ghi chú).
- [x] **Gate 3 — Sprint**: số liệu TỰ CHẠY LẠI độc lập: **224 BE (shb_test) + 78 FE = 302 ≥
  baseline 288** · architect đọc trọn (conftest, restart-server.sh, smoke 316 dòng, cụm
  bb17cd8 đã đọc khi commit) · tester 100% + kill-mid-flight live + smoke live PASS ·
  phát hiện ngoài-scope ghi (dưới) · commit format · invariant SPEC §15 giữ (phanh/audit
  không đổi) · UNVERIFIABLE: 1 mục → sổ ngoại lệ (dưới).

## Test counts
Baseline 288 (214 BE + 74 FE) → **302** (224 BE + 78 FE), re-run độc lập trước commit đóng.
Live: kill-mid-flight tự-lành + smoke 5-deliverable 4'25".

## Sổ ngoại lệ (§6b)
- **Xác nhận live 2-process (finding #2)** — chưa restart bằng script mới nên chưa đếm được
  process thật; suy luận nguồn (fuser sót parent) từ `ps aux` + đọc script, chưa phải bằng
  chứng trực tiếp. — lý do chấp nhận: guard-B đã vô hiệu hậu quả (kết quả cuối luôn đúng),
  fix script đúng-bất-kể. — 18/7 — architect duyệt — xét lại: lần restart kế (đếm process,
  dán output vào memory backend).

## Ngoại lệ S5 ĐÓNG
- **Race 2-nguồn-ghi-status (nhấp-nháy failed):** root = boot-cleanup quét task mới trong khe
  boot (+ nghi 2-process khuếch đại). Đóng bằng time-scope + guard-B (bb17cd8) + pkill (ca59f5b).
  Tester verify kill-mid-flight: hết nhấp-nháy oan.

## Findings ngoài scope (S7)
- **LAB legal 3-nguồn ĐÃ CERTIFIED** (`shb-digital-experts/reports/AGENT-legal-DONE.md`, 18/7,
  sonnet ✗0 test-locked) — phong bì bàn giao sẵn: SKILL v3 + `legal.py` 5 tool (classify_profile
  WRITE → bảng assessments = verdict hook D-52 đã chừa chỗ). **= việc chính S7.**
- **`_wait_for_settled` nâng lên helper chung conftest** (thay dần wait_for_conversation_idle ở
  test fan-out — bịt gốc thoáng-idle toàn suite; hoãn vì refactor test trước demo rủi ro > giá trị).
- **Agent-bền D-50** (sub-session resume per-(conv,role), nền F2b) — sau demo (user chốt).

## Bài học sprint
- **Sự kiện "server chết" phải là data mà consumer THẤY được** — onerror không nổ khi không FIN;
  mọi cơ chế phát hiện đứt phải chủ động (heartbeat + watchdog), đừng tin callback lỗi của platform.
- **Luật vận hành tốt nhất là luật hoá thành code** (không-pytest-trên-DB-demo → TEST_DATABASE_URL;
  restart-sạch → pkill+assert trong script) — kỷ luật miệng chỉ sống được vài ngày.
