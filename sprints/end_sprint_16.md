# Sprint 16 — End (Tracing/cost rõ ràng + Tổng quan có biểu đồ)

**Nguồn:** user chê "tracing cost logging BE chưa rõ ràng, admin show không cụ thể" + 2 ref
PlatformDTC (explore inventory). User chốt: z-score LÀM · chart vào TỔNG QUAN · FE contract-first.
**Commit:** e1f5f8a (plan+contract) · c2f8221 (T16-3 FE mock-first) · 45968cb (T16-1 instrument) ·
81b69cc (T16-2 cost API) · 6356f78 (T16-4 trace per-ca) · đóng = commit này.

## Kết quả (4 task)
- **T16-1**: `tasks` +6 cột (4 token category + duration_ms + model) đọc từ ResultMessage.usage
  đang-bị-vứt — map theo SHAPE LIVE thật (tránh silent-null); MAIN → messages.meta.metrics;
  **per-turn log base_url RESOLVED = trả nợ bằng-chứng T15-2** (switch provider → log đổi, bằng
  chứng máy).
- **T16-2**: `/api/stats/cost` (total + breakdown 4 + by_model + by_role + **anomalies z-score
  STDDEV_SAMP hand-verified 2.041** + delta double-window) · `/api/stats/cost-trend` (pivot) ·
  stats cũ window 24h|7d|30d ROLLING (D-69) + sparks number[24] (D-70).
- **T16-3**: Tổng quan MỞ RỘNG (giữ 7 KPI): KpiSparkline · TokenBreakdownBar 4-category ·
  DailyCostBar stacked role · ModelDonut "(ước tính)" · CostAnomalyTable z≥2/3 row-click→audit
  (cross-tab wire thật) · segmented window · độc-lập-degrade.
- **T16-4**: trace per-ca — TaskMetricsChips + per-task TokenBreakdownBar (tái dùng) +
  ConvMetricsPanel aggregate (tasks+main) + ToolRankBar + MAIN metrics dòng mờ; null-tolerant
  backward toàn bộ ca cũ.

## Verify
FE mock-first 2 wave (contract nguyên văn — BE khớp từng field, 0 lệch khi ráp). **PROD số
THẬT**: tab Tổng quan render dữ liệu sống (3 phiếu duyệt, lane 1/6/0, 29 ca, donut glm 56%/
gpt-5.4 34%/haiku 11%) + trace chips xác nhận cả UI lẫn API — tester PASS mục 4 vòng prod.
Máy-đo này lập tức thành hạ tầng cho bench S17 (tokens/cost/duration mỗi case).

## Quality Gates
- [x] **Gate 1**: 2 endpoint mới đọc-thuần + 4-field + window validate; D-69/D-70 đổi-hành-vi có
  sổ; không primitive (recharts là dep FE duy nhất).
- [x] **Gate 2**: BE +13 test (map key thật/z-score hand-computed/spark/empty) · FE +47 test
  (transforms pure tách test được ×2 cụm) · tsc/ruff sạch · author≠checker · 2 theme.
- [x] **Gate 3**: số TỰ CHẠY LẠI 637 test (410+227) · CI xanh · đọc trọn diff từng cụm · cost provider
  ngoài label "ước tính" (trung thực) · check-fix App.test có root ghi ngày.

## Bài học
- **Contract-first 2 chiều nhanh hơn chờ nhau**: FE build trước bằng mock theo contract chốt sẵn,
  BE khớp sau — ráp 0 lệch, tổng thời gian S16 ~1 buổi xen giữa 2 sprint khác.
- **Instrument trả nợ kép**: vừa là tính năng user đòi, vừa đóng gap bằng-chứng T15-2, vừa thành
  thước đo bench S17 — 1 lần xây 3 lần dùng.
