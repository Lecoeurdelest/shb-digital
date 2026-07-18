# Sprint 5 — End

**Theme:** Demo-prep (script + rehearsal + polish) + track nghiệp vụ phần vỏ (D-52) + D-54 quyền duyệt.
**Commit:** 66ffbc2 (kickoff) · 5434874 (phanh phân tầng) · 8dff186 (MAIN tuần tự bàn giao) · 111458e
(font self-host + constellation) · 58d929b/5513813/b984c5b (demo-script v3/v4/thoát-hiểm) · f0d5bcf
(D-54 docs) · 5d3810b (responsive máy chiếu) · {{đóng — điền}}

## Kết quả từng task

### T5-2' — done (track nghiệp vụ phần VỎ — pain point người ra đề, D-52)
- **Bằng chứng:** (b) phanh PHÂN TẦNG: <500tr tự duyệt theo rule (phiếu 'used' decided_by='auto-rule'
  + reason + receipt CÙNG tx — Option 2 step-2-pattern, không tái mời agent-callback fragility) + card
  transparency; ≥500tr chờ người byte-identical S3. Live 2 tầng + 16 gated test + rollback-không-phiếu-ma.
  (a) MAIN tuần tự: credit TRƯỚC một mình → legal SAU kèm bàn giao thật ("DSCR 1.501, CIC nhóm 1...")
  → ops cuối; câu thường giữ fan-out. Live transcript đúng trình tự. verdict hook chờ LAB legal 3-nguồn.
- **Deviation:** LAB chưa drop → verdict-xanh chưa wire (chỗ cắm sẵn).

### T5-0/T5-4 — done (demo-script + rehearsal — gate S5)
- **Bằng chứng:** script 5 cảnh v4 (5 deliverable + phân tầng + tuần tự): tên/mã KHỚP SEED (v3 fix
  lỗi architect bịa tên), câu mẫu đủ mục-đích+COL06 (root Legal luật #3/#6 — tester chẩn), tín hiệu
  luồng (khảo-sát→fan-out / nộp-hồ-sơ→tuần-tự), thoát hiểm 8 dòng, timing thật. **Gate: Vòng 1 TRỌN
  PASS + mọi cảnh Vòng 2 pass riêng nhiều lần** (Option A lead chốt — "liền mạch" hụt do lỗi điều
  phối người, không phải sản phẩm). Compare-treo FIXED trong rehearsal.
- **Deviation:** smoke-e2e-liền-mạch tự động = nice-to-have S6 (>15' ngưỡng lead).

### T5-1 — done (polish UI/UX)
- **Bằng chứng:** font Be Vietnam Pro SELF-HOST 15 woff2 (0 request CDN — offline-safe venue; gốc:
  tokens khai font nhưng chưa import → cả app fallback system-ui) · canvas constellation (Main giữa
  + sub tỏa + đường nối chảy xanh, CSS/SVG thuần timebox) · responsive máy chiếu floor 1366×768
  (rehearsal finding #4) · ErrorBoundary. 74 vitest.

### Fix trong sprint (rehearsal-driven)
- **compare treo vô hạn (demo-killer):** `_run_single` không timeout — SDK kẹt câm không raise →
  gather khoá (multi xong vẫn treo). FIX wait_for 60s → partial 2 cột. Tester chẩn line-đúng,
  architect verify code, 6 test + tester re-verify.
- **D-54 quyền duyệt (người chốt):** require_admin → require_user (decide/list/audit) — user app =
  nhân viên cấp cao ai cũng duyệt được; Tower = giám sát/thống kê. Verify flag-OFF thật (user 200,
  no-cookie 401). 2 test authz tester sửa theo semantics mới (note D-54).
- **restart-server.sh:** kiểm ca-live + confirm + in pid/time (mã hoá 2 bài học sự cố).

## 3 Quality Gates
- [x] **Gate 1 — API**: compare timeout partial · authz D-54 nới đúng (401 giữ) · test cũ pass · 4-field.
- [x] **Gate 2 — Function**: 16 gated (2 tầng + rollback) + 6 compare + authz mới · ruff + tsc sạch ·
  FE Chrome self-verify (constellation/responsive/font) · LOC ≤400.
- [x] **Gate 3 — Sprint**: counts re-run độc lập (214 BE + 74 FE = 288 ≥ baseline 282) · architect đọc
  trọn (nhánh 4a auto / MAIN_SKILL / compare wait_for / script) · gate rehearsal Option A (lead chốt)
  · findings ghi · commit format · invariant giữ (phanh phân tầng vẫn phiếu+audit đủ).

## Test counts
Baseline 282 → **288** (214 BE + 74 FE), re-run độc lập trước commit đóng. Live: rehearsal Vòng 1
trọn + các cảnh Vòng 2.

## Findings ngoài scope (S6/sau demo)
- **UX-treo khi SSE đứt/server gián đoạn:** MAIN không báo user khi task failed vì restart (boot-cleanup
  đánh failed nhưng không message) + FE nghi không map trạng thái sau reconnect (code CÓ reconnect+refetch
  — cần thực nghiệm kiểm soát phân tầng chính xác). Mitigation demo: thoát hiểm F5 + luật không-restart.
- **Smoke e2e 5-deliverable liền mạch** (regression demo vĩnh viễn) — nice-to-have.
- **LAB legal 3-nguồn** (Bộ CA/CIC/lương → verdict xanh) — đợi LAB training xong, port + wire verdict
  hook (D-52). · **Agent-bền D-50** — sau demo.

## Ngoại lệ đã ký (§6b)
- **Race 2-nguồn-ghi-status (nhấp-nháy failed thoáng qua)** — task queued trong khe restart bị
  boot-cleanup đánh failed rồi kết quả thật overwrite done. Soát code: CHỈ 1 nguồn ghi "server
  restart" (cleanup_orphans, chạy lúc boot) — nghi cleanup quét task queued-mới-tạo trong khe
  boot. **Kết quả cuối LUÔN đúng**; rủi ro chỉ nhấp-nháy UI nếu render trúng khoảnh khắc. — lý do
  chấp nhận: hiếm (chỉ khi restart giữa ca — đã cấm bằng luật vận hành + script kiểm ca-live);
  demo không restart. — 18/7 — architect duyệt — xét lại: S6 điều tra sâu (cleanup lọc theo
  started_at/pid) hoặc demo thật gặp.

## Bài học sprint
- **Tài nguyên chung khi có người verify = ĐỘC QUYỀN người đang dùng** — architect 2 lần ra lệnh
  restart/confirm-y dựa trên hình dung sai về "ca nào đang chạy"; người duy nhất biết chắc là người
  đang dùng. Luật: hỏi TESTER, không hỏi architect; script chặn thì không vượt chặn hộ.
- **Script demo phải đối chiếu SEED** (architect bịa tên → Legal bắt mismatch đúng thiết kế) + câu
  mẫu phải ĐỦ info theo luật skill (Legal #3/#6) — "demo gãy" đa số do input người, không phải hệ.
- **Giảm crossing:** đọc board trước khi gửi; chỉ gửi FAIL/verdict/cần-hành-động.
