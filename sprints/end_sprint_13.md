# Sprint 13 — End

**Theme (user chốt 19/7, full-auto):** Admin thống kê + hồ-sơ-lý-do-AI — gộp vào Control Tower,
ref hình-dạng shopquantum-admin (không copy code), rào chỉ-đọc.
**Commit:** 39e7deb (draft) · 9ea0335 (T13-1 API) · fb8cec2 (T13-2/3 FE) · đóng = commit này.

## Kết quả
- **T13-1** `GET /api/stats?window=today|7d` (approvals theo decided_at, auto-rule đếm riêng —
  kể ma trận; pending snapshot; assessments theo lane cast ::timestamptz; conversations; delta
  so kỳ trước; UTC day) + `GET /api/assessments` (cap 100, criteria hỏng vẫn trả row). Rào giữ:
  group-by thuần, 0 bảng mới. 10 test + curl thật.
- **T13-2** Tab "Tổng quan" (default): 7 KpiCard + delta ↑↓ + badge "trong đó AUTO" + pending
  warn + window switch + poll 30s dừng-tab-ẩn + footer "demo: admin gộp vai". Theme-aware.
  Spark bỏ đúng rào (không chế endpoint series).
- **T13-3** Tab "Hồ sơ + lý do AI": list lane-chip → panel criteria 3 trụ từng tiêu chí ✓/⚠/✗
  + "🤖 Lý do AI" (basis). Audit tool_calls giữ drill-down.
- **T13-4** tester Luồng 8 vào `business-test-scenarios.md` — **8/8 luồng PASS** (bảng tổng).
  Đối chiếu chéo mạnh: panel đọc ĐÚNG assessment thật tester tự tạo (case yellow C001 khớp
  chính xác finding honest-null cũ); KPI verify bằng SỰ KIỆN TƯƠI (disburse auto → approved=1/
  auto=1 nhảy cả UI lẫn API).

## Sự cố trong sprint (root-caused, không phải bug)
- **False alarm 8a**: stats trả 0 trong khi audit có ≥6 disburse — root = architect DELETE
  approvals lúc dọn prod sau S11 (biên lai có sẵn); tool_calls append-only không bị dọn → 2
  nguồn lệch đúng vòng đời từng bảng. Re-verify bằng sự kiện tươi → PASS. Note vận hành vào
  doc: "reset → KPI 0 và nhảy live trong demo = điểm kể chuyện".

## 3 Quality Gates
- [x] **Gate 1 — API**: 2 endpoint mới đọc-thuần, 4-field (400 bad_window, 403 non-admin),
  integration test đủ (window/delta/auto/rỗng-zeros/malformed), không primitive ngoài SPEC.
- [x] **Gate 2 — Function**: unit +20 (10 BE + 10 FE) · edge (DB rỗng, criteria hỏng, window
  lạ, cap) · ruff/format/tsc sạch · author≠checker (tester đối chiếu chéo độc lập) · FE Chrome
  2 mode + real :8000 + prod · LOC ≤400.
- [x] **Gate 3 — Sprint**: số liệu tự chạy lại: **497 test (367 BE + 130 FE) ≥ 477** + CI xanh
  mọi commit · architect đọc trọn (stats.py + Tower wiring + KpiCard cụm) · tester 8/8 prod ·
  findings ghi (false-alarm 8a + note vận hành) · commit format · invariant giữ (chỉ đọc) ·
  UNVERIFIABLE: 0 mục mới.

## Trạng thái sau sprint
Prod: Tower 6 tab (Tổng quan default) sống với data thật; L001 tester restore. Hàng đợi:
S12 retrieval (⏸ D-63 chờ LAB drop) · rehearsal 2-cửa-sổ tay trước giờ G · GOOGLE creds đã
sống · scenarios doc 8/8 = checklist giờ G.

## Bài học
- **Dashboard verify bằng SỰ KIỆN TƯƠI mạnh hơn đếm lịch sử** — false-alarm 8a lộ ra rằng
  "đối chiếu số cũ" phụ thuộc ground-truth không ai giữ; "bấm 1 phát thấy số nhảy" là bằng
  chứng sống không cãi được.
- **Dọn DB phải báo THEO SỐ**, không chỉ "đã dọn" — số 0 nằm trong message từ đầu nhưng người
  đọc không neo; cleanup từ nay ghi rõ bảng nào về bao nhiêu row.
