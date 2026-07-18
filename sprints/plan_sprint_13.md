# Sprint 13 — DRAFT: Admin thống kê + hồ sơ-lý-do-AI (user chốt 19/7, full-auto sau S11)

> Scope lead chốt với user (msg 19/7) — ref hình-dạng `../PlatformDTC/_PLATFORMDTC/shopquantum-admin`
> (KHÔNG copy code — khác stack). Nguyên tắc: GỘP vào Control Tower hiện có + 1 dòng UI
> "bản demo: admin gộp vai giám sát nghiệp vụ + kỹ thuật". KHÔNG tách role admin-2.
> Full-auto build→test→error→update (§7) — user không discuss thêm.

## Task dự kiến

### T13-1 — BE: `GET /api/stats?window=today|7d` (require_admin, gating)
- Trả: phiếu (đã duyệt/chờ/từ chối) theo window + delta so kỳ trước · tổng hồ sơ assessments
  theo lane (green/yellow/red) · đếm ca/task nếu rẻ. THUẦN group-by trên bảng sẵn
  (approvals/assessments/conversations) — KHÔNG bảng mới, KHÔNG cost-USD, KHÔNG health-metric.
- Integration test: shape + window filter + 401/403 + rỗng → zeros (không 500). 4-field errors.

### T13-2 — FE: tab "Tổng quan" trong ControlTower (sau T13-1)
- KpiCard + SparkLine THAM KHẢO shopquantum `frontend/components/dashboard/` (hình dạng),
  VIẾT LẠI cho Vite/React stack này. Theme-aware (T11-6 tokens). + dòng chú "bản demo: admin
  gộp vai giám sát nghiệp vụ + kỹ thuật".

### T13-3 — FE+BE nhẹ: nâng tab audit → "Hồ sơ + lý do AI"
- Click hồ sơ → panel assessment đầy đủ: 3 trụ criteria (pass/yellow/red từng tiêu chí —
  data criteria_json sẵn) + lane + decision + **lý do AI** (reason ma trận D-59 dẫn assessment
  #id — data sẵn, chỉ trình bày). Audit tool_calls giữ làm lớp sâu (drill-down).
- BE nếu cần: `GET /api/assessments?owner=&limit=` đọc-thuần (require_admin).

### T13-4 — Tester: e2e dashboard + hồ-sơ-chi-tiết trên prod + regression.

## RÀO (§2): chỉ endpoint ĐỌC + trình bày data-đã-có. Không primitive mới.
## Gate: §6a đủ (integration test + 4-field + FE browser-verify 2 màn + theme 2 mode) + suite ≥ baseline S11.
