# Sprint 16 — Tracing/cost rõ ràng + Tổng quan có biểu đồ (user chốt 19/7)

**Nguồn**: user chê "tracing cost logging BE chưa rõ ràng, admin show không cụ thể" + 2 ref
PlatformDTC (explore inventory xong). Rào lead: MỞ RỘNG Tower hiện có, không dựng lại, không bê
màn. **User chốt**: ① anomaly z-score LÀM ("nhanh thì làm" — 1 query SQL) · ② chart vào tab
**TỔNG QUAN** hiện có (không tab mới) · ③ timing: BE-part sau S12 (BE đang gánh port), FE-part
chạy NGAY contract-first (FE đang rảnh).

## Contract API (architect chốt — FE mock theo đây, BE build T16-2 sau S12)
```
GET /api/stats/cost?window=24h|7d|30d
→ { window, total_cost_usd, cost_estimated: true,       # provider ngoài: cost SDK không tin — label "ước tính"
    breakdown: {input_tokens, output_tokens, cache_read_tokens, cache_create_tokens},
    by_model: [{model, cost_usd, turns, total_tokens}],
    by_role:  [{role, cost_usd, turns}],
    anomalies: [{conv_id, title, cost_usd, mean, stddev, z_score}],   # z = (cost-mean)/stddev, lấy z≥2
    delta: {total_cost_pct} }
GET /api/stats/cost-trend?window=&bucket=hour|day&group_by=model|role
→ { buckets: [{ts, series: {"<name>": cost}}] }         # SQL long-format, pivot Python
Mở rộng /api/stats hiện có: mỗi KPI thêm "spark": [24 số]  # 24-bucket chuẩn hoá mọi window
```

## Task
| # | Task | Ai | Khi |
|---|---|---|---|
| T16-1 | Instrument: `tasks` +6 cột (in/out/cache_read/cache_create tokens, duration_ms, model — đọc ResultMessage.usage đang bị vứt); MAIN turn ghi cost/token vào message result; per-turn log có cấu trúc (provider/model/base_url — trả nợ bằng-chứng T15-2) | BE | sau S12 |
| T16-2 | 2 endpoint theo contract + spark 24-bucket + delta double-window 1-query + anomaly z-score SQL (mean+2σ, STDDEV_SAMP) + window 24h thêm vào stats cũ | BE | sau S12 |
| T16-3 | Tổng quan MỞ RỘNG (recharts): KpiCard +sparkline · TokenBreakdownBar 4-category (màu cố định) · DailyCostBar stacked theo role · donut by-model (label "ước tính") · bảng anomaly z≥2/3 filter, row-click → audit ca · segmented window (có 24h) | FE | NGAY (mock theo contract) |
| T16-4 | Trace per-ca: SubAgentView + cost/tokens/duration per task + tool-call ranked bar | FE | sau T16-3 |

## Rào giữ
Không bê 19 màn shopquantum (không billing/merchant/health/redis) · recharts là dep FE mới duy
nhất · cost provider ngoài label "ước tính", token là số thật · Tổng quan cũ (7 KPI nghiệp vụ)
GIỮ — chart bổ sung phía dưới, không thay.

## Kickoff — 2026-07-19
Baseline: BE 376 (sau T12-1) · FE 180. Gate: theo §6a chuẩn + tester verify khi BE-part xong
(FE mock-first sẽ có vòng verify-lại với API thật).
