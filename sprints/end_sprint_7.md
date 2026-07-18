# Sprint 7 — End

**Theme:** Port LAB legal CERTIFIED (3 trụ Bộ CA / CIC / lương) + ma trận thẩm quyền 3 tầng
verdict-aware (D-52 pain người ra đề: hồ sơ xanh agent tự duyệt). Chạy SAU S8 theo D-56.
**Commit:** 8a1ee38 (kickoff D-55) · 5caaa11 (D-58) · 25bd8d7 (T7-1) · de41787 (T7-2) ·
3d58c2c (T7-3+D-59) · 2069bbc (c019) · đóng = commit chứa file này. Giữa sprint (lệnh user
trực tiếp): 1de8768 (markdown chat D-60) · 1d37027 (merge PR #1 lobby 3D).

## Kết quả từng task

### T7-1 — done (data-layer, 25bd8d7)
- 3 bảng police_records/employment_records/assessments + 4 cột identity additive (migration
  nối tiếp — nguyên tắc "migration đã apply là bất biến" vào memory backend) + seed đủ (trap
  C013 Lòng≠Long intact, 6 assumption key) + **D-58**: labpack credit drift phát hiện empirical
  → re-sync `_assumptions` byte-identical LAB (diff toàn file: drift CHỈ ở đó, 0-hunk-logic
  sau thay). Architect verify độc lập từng số.

### T7-2 — done (port 5 tool + SKILL v3 + adapter WRITE, de41787)
- roles/legal rebuild wholesale từ LAB — **7/7 function byte-identical** (architect diff-body
  độc lập xác nhận); SKILL v3 không sửa 1 chữ; import share credit (D-55a, cùng object).
- PGConnAdapter WRITE khoanh vùng (D-55b): whitelist fail-closed chỉ `INSERT INTO assessments`
  (mọi câu ghi khác raise), lastrowid emulate RETURNING id, cùng-conn commit.
- classify e2e seed thật 4 lane (green/yellow-mismatch/red-fraud/DN-yellow), ledger id tăng.

### T7-3 — done (ma trận 3 tầng, 3d58c2c)
- `verdict.py`: <500tr auto trừ lane=red · 500tr–auto_max(2e9, đọc assumptions) auto NẾU
  lane=green (reason dẫn assessment #id) · >auto_max luôn người. **D-59**: decision suy từ
  lane (assessments không có cột decision — thêm cột là phá byte-identity N1; mapping tương
  đương đối chiếu LAB :329-332). BACKWARD KEY: assessments rỗng → hành vi y cũ, 16 gated test
  pass KHÔNG sửa. Verdict đọc conn riêng ngắn (không abort gated tx). Rider: reset_demo wipe
  folder neo cwd (206 mồ côi — trả lời câu user "nhiều folder rỗng").

### T7-4 — done (e2e tester + script v7)
- **Tester 5/5 PASS** (verify DB từng-bước-tại-lúc-chạy): ① legal 3 trụ sống qua chat (audit
  rows đủ 3 tool + classify ghi sổ) ② **xanh-tự-duyệt 594tr TRÊN ngưỡng** — auto-rule, reason
  "Hồ sơ XANH — assessment #9" NGUYÊN VĂN, receipt ③ C001 yellow honest-null ("chưa tra được
  công an" — không bịa) ④ regression L006 auto + L007 chờ người → duyệt → resume ⑤ fan-out
  SKILL v3 không dừng hỏi, tone khách, 0 thuật ngữ lộ.
- **Finding vàng → script v7 đã sửa:** mục đích "mở rộng kinh doanh" = conditional → YELLOW
  (đúng chính sách, không phải bug) — câu nhịp C đổi thành "MUA NHÀ Ở, tín chấp" (green thẳng,
  không vòng hỏi). Timing thật: nhịp C ~5' → tổng ~15' → mặc định cắt C5 về ≤13'.
- Seed c019→C019 (2069bbc — tổ hợp green + loan active L108 duy nhất, architect scan 30 khách).

### Ngoài sprint (lệnh user trực tiếp, §8)
- **D-60 markdown chat** (1de8768): assistant/streaming render react-markdown+gfm, XSS-safe
  AST (0 inject verify), user/system giữ plain. 95 FE test (+5).
- **Merge PR #1 lobby 3D** (1d37027): conflict chỉ package.json (dep-union) — Canvas
  canDecide(S8) + Lobby3D sống chung, tsc/95test/build verify. PR MERGED trên GitHub.

## Sự cố trong sprint (root-caused, đóng)
- **"DB bị dọn lén" giữa T7-4** = chính suite tester chạy thiếu TEST_DATABASE_URL →
  `test_reset_demo_wipes_conversation_dirs` wipe DB chính (PID nguyên — script DB thuần).
  1-fail suite = data-bẩn rehearsal của chính nó (xác nhận bằng re-run sạch 283). **Fix chặn
  máy đang hạ cánh:** destructive test skip khi thiếu env (backend micro-task, commit riêng).
- **Vite overlay JSONError** = architect merge PR đụng package.json lúc tester giữ dev server —
  lỗi phối hợp architect, ghi bài học: merge/sửa tree FE phải báo người đang cầm dev server.

## 3 Quality Gates
- [x] **Gate 1 — API**: không endpoint mới (verdict nằm trong tool-layer phanh) · test cũ pass ·
  4-field giữ (adapter raise PermissionError nằm dưới tool boundary) · không primitive ngoài
  SPEC (verdict = SQL đọc, không engine mới).
- [x] **Gate 2 — Function**: unit mới 42 (10 datalayer + 15 port + 17 verdict) · edge (string-key
  assumptions, C013 trap, DB-error 2 path, boundary 500tr/2e9/2e9+1, whitelist 7 kiểu câu ghi) ·
  fail-open/closed rõ (adapter fail-closed; verdict-đọc-lỗi fail về hành-vi-cũ có log) · ruff +
  format + tsc sạch · author≠checker giữ (tester e2e độc lập) · FE self-verify (markdown mock
  5174) · LOC: verdict 109, gated 327; legal 446 = ngoại lệ labpack-copy (note header).
- [x] **Gate 3 — Sprint**: số liệu TỰ CHẠY LẠI độc lập: **283 BE + 95 FE = 378 ≥ baseline 331**
  (tester re-run 283 xác nhận độc lập lần 2) · architect đọc trọn (verdict.py nguyên file, gated
  diff, adapter diff, legal byte-diff 7 function, script) · tester 5/5 live + suite · findings
  ghi (mục-đích-conditional, sự cố suite-tự-reset) · commit format · invariant SPEC §15 giữ
  (phanh 4-step tx + advisory lock 0 đổi, audit đủ mọi nhánh kể cả auto) · UNVERIFIABLE: không
  mục mới (sự cố đã root-cause đóng; guard = follow-up commit riêng, không phải waiver).

## Test counts
Baseline 331 (241 BE + 90 FE) → **378** (283 BE + 95 FE). Live: T7-4 5/5 + timing đo thật.

## Findings ngoài scope (mang theo)
- Guard destructive-test (backend đang làm — commit riêng ngay khi báo).
- Script cảnh 1 nói "constellation" — UI giờ là lobby 3D (PR #1): sửa chữ mô tả khi rehearsal
  trước giờ G (không đổi flow).
- Known-limitation: verdict match owner-mới-nhất không đối chiếu số tiền ca (D-59 note) ·
  amount-mismatch classify-vs-disburse chấp nhận demo-grade.

## Bài học sprint
- **2 nguồn đọc độc lập cùng ra 1 schema = tin được** (backend điều tra khớp phong bì 100%
  trước khi tao kịp trả lời — drift D-58 cũng do đối chiếu 2 nguồn mà lộ).
- **Câu demo phải đối chiếu CHÍNH SÁCH, không chỉ seed** (v3: tên khớp seed; v7: mục đích khớp
  restricted_purposes — cùng một lớp lỗi, mở rộng checklist script).
- **Luật vận hành chặn bằng máy, không bằng warning** (TEST_DATABASE_URL warning không cứu được
  người quên — destructive test phải tự skip).
