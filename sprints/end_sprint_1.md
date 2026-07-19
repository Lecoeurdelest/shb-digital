# Sprint 1 — End

**Theme:** SPINE SỐNG trên NỀN scaffold — lát cắt dọc RM chat → Main → Credit thật (PG) → event
→ tổng hợp có nguồn → SSE → FE chat thô (API thật).
**Commit:** e1a5633 (T1-1) · 3ee4877 (T1-2) · ed2b302 (T1-3) · bcb0abe+c07fce2+f52b0ba (T1-4/harden/ráp-thật)
· c484146 (test mechanics) · chore: 705ab94/5501c65/093e218.

## Kết quả từng task

### T1-1 — done (scaffold nền: PG + adapter D-27 + mount credit + auth)
- **Bằng chứng:** `alembic upgrade head` → 9 bảng; `assumptions`=8 (D-28 lọc), customers=30, businesses=5,
  collaterals=7. `REGISTRY['credit_assess'](PGConnAdapter,'C001')` → dscr==3.709. Auth: login <tài khoản RM demo>→200
  cookie httponly, sai→401 4-field. Tester PASS độc lập.
- **Deviation:** D-28b (seed businesses/collaterals thật — query vô điều kiện), D-28c (server_default uuid).

### T1-2 — done (orchestrator spine — xương sống)
- **Bằng chứng:** `uv run pytest` 55 pass (lúc đóng T1-2). Invariant §5 (done/failed/timeout/cancel→1 event),
  idempotent §4 (race 5× không flaky), slot/queue §2, SDK 4 landmine. Tester: ca cancel/shield 3× liên tiếp.
- **Deviation:** D-31 (conv_id text ràng-buộc-mềm, ratify), D-33 (inline-await §6 accept S1), D-34 (store per-call conn).

### T1-3 — done (vòng lõi chat+SSE — GATE SPINE SỐNG)
- **Bằng chứng:** GATE S1 end-to-end (tester automated smoke `test_gate_s1_e2e.py`, RUN_LIVE_SDK opt-in, 3/3
  determinism): chat "DSCR C001?"→SSE→DSCR có nguồn, tool_calls truy vết (SSE↔PG khớp), main KHÔNG nhẩm.
  N2 live: ca lỗi thật → main báo "không thể nhẩm" thay vì bịa. Default `uv run pytest` 69 pass + 3 skip.
- **Deviation:** D-32 (mount_role sys.path). §9 main-retry không làm (optional S1, gap-có-chủ-đích).

### T1-4 (+harden +ráp-thật) — done (FE chat thô → API thật)
- **Bằng chứng:** 25 vitest pass, typecheck 0, jscpd 0. E2E API THẬT (architect curl verify): login→200 cookie
  httponly, no-cookie→401, with-cookie→200. **DSCR THẬT 0.236 render qua UI** (khác mock 3.709 = tool chạy
  thật xuyên login→REST→SSE→verdict). Auth seam finding (prove-spine-first) confirmed + fixed.
- **Deviation:** login uncontrolled FormData (best-practice password-manager). 2 tương tác UI → waiver (dưới).

### T1-5 — done (tester independent verify)
- **Bằng chứng:** verify độc lập T1-1/T1-2/T1-3 (đọc source trước, viết test lại không copy), gate S1 live +
  mechanics-stub (3 test default-run, 69 pass). Không UNVERIFIABLE treo.

## 3 Quality Gates

- [x] **Gate 1 — API**: error 4-field 1 shape (errors.py) · integration test (auth/sse/gate-e2e/mechanics) ·
  test cũ pass · resource trần + status code (201/202/401/404) · không primitive ngoài SPEC.
- [x] **Gate 2 — Function**: 69 BE + 25 FE unit/integration assert observable · edge (empty/None/malformed) ·
  error path 4-field · typecheck (ruff + tsc) sạch · **FE Chrome self-verify: đường lõi login→REST→SSE→verdict
  DSCR 0.236 verify browser thật; 2 tương tác input (+Ca mới click, Composer gõ) → waiver §6b (dưới)** · PROD LOC max 354<400, jscpd 0.
- [x] **Gate 3 — Sprint**: end_sprint count re-run độc lập (BE 69, FE 25) · architect đọc trọn function
  (pg_adapter/spine 9 file/emit/refetch — không chỉ diff) · tester 100% · test ≥ baseline(0) · findings ghi ·
  commit format feat/chore/test · invariant SPEC §15 giữ · UNVERIFIABLE đóng hết (waiver có sign-off).

## Test counts

- **Baseline (đầu sprint):** 0 (greenfield)
- **Sau sprint:** BE **69 passed** + 3 skipped (2 gate-live opt-in + 1 sub-smoke) · FE **25 passed** = **94 test**

## Findings ngoài scope (flag cho sprint sau)

- **Nợ kỹ thuật S2 (đã ghi DECISIONS + comment tại site):** D-33 inline-await §6 → chuyển spawn khi thêm
  §9 main-retry + concurrency thật. D-34 store per-call conn → thống nhất pool nếu churn. D-28c legacy: mount
  legal cần nạp legal_docs_source (credit._assumptions lọc numeric — việc LAB).
- **§9 main retry** chưa làm (optional S1) — làm khi cần bền lượt main.

## Ngoại lệ đã ký

- **2 tương tác UI (nút "+ Ca mới" click · Composer gõ câu) chưa verify qua Chrome MCP · lý do: Chrome MCP
  input-registration flaky (keyboard gõ→field trống; click→0 network request) — xác nhận ĐỘC LẬP 2 nguồn
  (frontend + tester, đều dùng `find`+ref không toạ độ, retry, kiểm network log). KHÔNG phải app-bug: wiring
  code đúng (onNew→createConversation, Composer onSend→sendChat) + unit test cover (fireEvent) + architect
  curl backend nhận request. Đường lõi login→REST→SSE→verdict ĐÃ verify browser thật · 2026-07-18 · architect
  duyệt · điều kiện xét lại: re-verify khi Chrome MCP ổn (session mới / extension restart / máy khác) — đầu S2.**
