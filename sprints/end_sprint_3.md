# Sprint 3 — End

**Theme:** PHANH end-to-end (N2 gate cưỡng chế tầng tool) — deliverable #3 đề #132. disburse gated
→ phiếu (pending→approved→used) + biên nhận chống-thực-thi-đôi + atomic claim + payload_hash + card
approval (chỉ vỏ sinh) + admin duyệt → event resume → giải ngân thật. Sprint KHÓ NHẤT cả hệ (D-29).
**Commit:** 87d9e18 (T3-0) · 3d3cf9d (T3-1 phanh) · a04df64 (T3-2 resume) · 44fdb4b (routing fix) ·
2ab26a4 (provider registry) · {{card-sync + đóng sprint — điền khi commit}}

## Kết quả từng task

### T3-0 — done (dev skip-auth D-39)
- **Bằng chứng:** flag ON no-cookie → 200 admin · flag OFF → 401 + auth cũ 9 pass · boot cảnh báo · skip CHỈ deps layer · default OFF. Committed 87d9e18 (git-show verified).
- **Deviation:** none.

### T3-1 — done (phanh wrapper gated — TÂM ĐIỂM)
- **Bằng chứng:** wrapper THREAD-CONN 1 tx (claim+inner+receipt) · INVARIANT status='used'⟺receipt · payload_hash 1 hàm (5e9≡5000000000, 1tỷ≠5tỷ) · advisory-lock chống race phiếu-rác (sha256-key, verify 10× [EXEC,RECEIPT] 0 rác) · card approval vỏ-sinh (N5/§15) · migration approvals. `uv run pytest tests/test_gated.py` → 12 passed. Committed 3d3cf9d (git-show verified: advisory-lock/receipt-invariant/migration trong commit).
- **Deviation:** advisory-lock thêm sau tester tìm race phiếu-rác (D-41a) — money-safe cả trước lẫn sau.

### T3-2 — done (API decide + event resume)
- **Bằng chứng:** decide ATOMIC (UPDATE…WHERE status='pending' RETURNING → 2 lần 409 chống double-wake) · đánh thức main REUSE handle_room_event §4.4 (không chế cơ chế mới) · _wake_guarded try/except-log · prompt approval_decided theo hành động §15 · store_approvals tách (D-34). `uv run pytest tests/test_approvals.py` → 15 passed. Committed a04df64 (git-show verified).
- **Deviation:** rejected CŨNG đánh thức main (báo user từ chối) — trong scope.

### Routing fix — done (MAIN + Ops route "giải ngân" → disburse, D-46/D-44)
- **Bằng chứng:** MAIN_SKILL operations 2-loại-việc (lộ trình vs giải ngân) · SKILL.md operations sửa "disburse CÓ" (stub vỏ D-35, không đụng LAB). Verify e2e THẬT (architect độc lập query PG): chat "Giải ngân L001 5 tỷ" → phanh chặn → phiếu+card → decide approved → resume → loans='disbursed'+used+receipt. Committed 44fdb4b (git-show verified).
- **Deviation:** none (fix lỗ hổng routing lộ khi e2e qua chat).

### Provider registry — done (D-45/45b — standalone không phụ CLI auth)
- **Bằng chứng:** port battle providers.py · resolve_env (subscription→rỗng, keyed→3 env, missing-key raise) · public_view không lộ key · GET /api/models. Verify STANDALONE (env sạch không CLAUDE_CODE_* + SHB_PROVIDER=zai): full demo path chạy qua zai. `pytest test_providers.py test_models_api.py` → 14 passed. Committed 2ab26a4 (git-show: no key leak).
- **Deviation:** (c) per-conv provider hoãn (SHB_PROVIDER mức server đủ standalone).

### T3-3 — done (FE approval panel + boot-check)
- **Bằng chứng:** boot-check skip-auth REAL PASS (:8000) · approval panel render + Duyệt/Từ chối + realtime SSE approval.decided · verify REAL browser: render+decide+resume+giải ngân THẬT. 46 vitest, TC0. {{card-sync reload re-verify — điền}}
- **Deviation:** queue Control Tower dời S4 (nguyên khối). {{card-sync}}

### T3-4 — done (tester gate S3 4/4 nhánh + authz)
- **Bằng chứng:** 4/4 đường THẬT (browser+fetch, query PG không tin UI): happy-path (loans=disbursed, used, receipt, 1 lần) · reject (loans=active, rejected, receipt=None) · decide-twice-409 (Promise.all 2 req → 200+409, resume 1 lần) · authz D-19 12/12 deterministic. `uv run pytest` → 150 passed / 6 skip. author≠checker (tester độc lập).
- **Deviation:** race resume-dispatch → sổ ngoại lệ (dưới).

## 3 Quality Gates

- [x] **Gate 1 — API**: approvals schema (constraint status enum) · integration test decide/list endpoint mới · test cũ pass · response resource trần · status 200/400/404/409 đúng · error 4-field {code,message,hint,retryable}.
- [x] **Gate 2 — Function**: unit test gated/approvals/providers assert observable · test cũ pass · edge (payload_hash int/float/None, decide-twice, missing-key) · error path (fail-closed phanh) · ruff sạch · FE Chrome self-verify real approval flow · PROD LOC (store_approvals tách D-34, không file >400) · advisory-lock chống race.
- [x] **Gate 3 — Sprint**: end_sprint count re-run độc lập (150 pass) · architect đọc trọn function (gated wrapper/decide/resume/provider — git-show verify mọi commit) · tester 100% 4/4 + browser · test 150 ≥ baseline 126 · findings ngoài scope ghi (race, 2-card-trùng) · commit format feat/fix · invariant SPEC §15 (N5 card vỏ-sinh, §4.4 phanh) giữ · UNVERIFIABLE (race) vào sổ ngoại lệ có architect duyệt.

## Test counts

- **Baseline (đầu S3):** 126 (T2 end)
- **Sau S3:** BE **150 passed** + 6 skipped (live SDK opt-in) · FE **46 passed** = vượt baseline.

## Findings ngoài scope (flag cho sprint sau)

- **Edge loop race-guard (chưa kiểm hết):** ops#2 disburse fail (loan lỗi → rollback → phiếu về
  approved-chưa-used) → grant còn → guard B re-dispatch lại → loop? Happy-path không gặp (loan hợp lệ);
  tester kiểm + thêm guard chống loop nếu cần (S4). Money-safe (không đúp).
- **2 card "Biên nhận giải ngân" trùng** (MAIN present 2 lần: Ops sub-result + MAIN tổng hợp) — không money-risk, dư UI. Dọn S4 polish.
- **Provider (c) per-conv + model dropdown UI** (D-45b) — SHB_PROVIDER server đủ standalone; UI chọn model làm S4.
- **immediate-stop sub sau gated** (người muốn "A tắt luôn") — skill/hint giảm window; polish S4.

## Ngoại lệ đã ký (§6b)

- **Race resume-dispatch (completion-nondeterminism) — ĐÃ FIX, KHÔNG còn ngoại lệ.** Guard A/B
  `_resume_dispatch_guard` (commit cd1bd24) re-dispatch TỪ task_done khi role free → MAIN không stale-read.
  Verify cô lập (loan L102, không nhiễm chéo) 3/3 clean + transcript sạch (MAIN dispatch đúng 1 lần
  created:true, guard B tự re-dispatch — tất định bằng cơ chế). "Flaky" ban đầu = contamination (3 tiến
  trình live-SDK cùng L007 + `_restore_state` global-by-loan-id + :8000 reap-orphan) — quy trình verify,
  không phải sản phẩm; backend SIGSTOP :8000 → 3/3 clean xác nhận.

- **Loop-edge guard B (defensive, treo S4)** — ops#2 disburse FAIL BỀN (loan lỗi → `_gated_txn` rollback
  → phiếu về approved-chưa-used) → `pending_execution` vẫn thấy grant → guard B re-dispatch ops#3 → loop
  (outcome='done' KHÔNG cứu vì tool trả error-dict, sub vẫn narrate done). **Money-safe** (không đúp — mỗi
  lần rollback sạch). CHỈ fire khi ops fail BỀN (loan lỗi lặp) — happy-path demo (loan hợp lệ) KHÔNG gặp.
  — **lý do chấp nhận:** bound sạch cần migration attempt-state (retry-counter/tried-marker; orch_dispatch_impl
  giấu ops#2 task_id → không one-liner) = HỐ nếu làm S3; defensive case hiếm, demo tay không chạm. — **18/7**
  — **architect duyệt** — **điều kiện xét lại:** S4 bound bằng attempt-state, hoặc demo thật gặp ops-fail-bền.

## Bài học quy trình (ghi để không lặp)

- **Verify live-SDK song song trên loan CHUNG = nhiễm chéo.** 3 tiến trình (architect/backend/tester) cùng
  chạy e2e trên L007 + cleanup global-by-loan-id → ghi đè kết quả nhau → báo FAIL oan 3 lần (mỗi người 1
  lần suýt kết "bug tiền"). Money-safe thật xuyên suốt. → Từ giờ: mỗi verifier dùng loan RIÊNG hoặc tuần tự.
- **"3/3 green" 1 người báo ≠ tất định** — cần verify cô lập độc lập (author≠checker) + đọc transcript, không
  tin pytest count qua môi trường chia sẻ. Verify độc lập của architect bắt được "3/3" không tất định (thực
  ra nhiễm chéo) trước khi gỡ ngoại lệ nhầm.
