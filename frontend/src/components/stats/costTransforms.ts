// costTransforms.ts — S16 T16-3: pure functions cho cost dashboard (pivot long→wide, z-filter,
// token breakdown, donut). Tách khỏi component để TEST TRỰC TIẾP (jsdom không đo recharts SVG —
// test data-in→data-out). Mọi hàm defensive: input rỗng/thiếu → trả rỗng an toàn, KHÔNG throw.
import type { CostAnomaly, CostBreakdown, CostByModel, CostTrendBucket } from '../../types';

// pivot long-format buckets (series{name:cost}) → wide rows recharts BarChart cần: [{ts, name1, name2}].
// Union mọi tên series qua các bucket (bucket thiếu name → 0). names giữ thứ tự xuất hiện đầu tiên.
export function pivotTrend(buckets: CostTrendBucket[]): { rows: Record<string, number | string>[]; names: string[] } {
  if (!Array.isArray(buckets) || buckets.length === 0) return { rows: [], names: [] };
  const names: string[] = [];
  for (const b of buckets) {
    for (const name of Object.keys(b.series ?? {})) {
      if (!names.includes(name)) names.push(name);
    }
  }
  const rows = buckets.map((b) => {
    const row: Record<string, number | string> = { ts: b.ts ?? '' };
    for (const name of names) row[name] = Number(b.series?.[name] ?? 0);
    return row;
  });
  return { rows, names };
}

// lọc anomaly theo ngưỡng z (2 hoặc 3), sort z giảm dần. input rỗng/thiếu z_score → bỏ an toàn.
export function filterAnomalies(anomalies: CostAnomaly[], minZ: number): CostAnomaly[] {
  if (!Array.isArray(anomalies)) return [];
  return anomalies
    .filter((a) => typeof a?.z_score === 'number' && a.z_score >= minZ)
    .sort((x, y) => y.z_score - x.z_score);
}

// TokenBreakdownBar 4 category CỐ ĐỊNH (màu + thứ tự — component chung T16-4). Trả segment %+abs.
// tổng 0 → mọi pct 0 (không chia 0). Thiếu field → coi 0.
export const TOKEN_CATEGORIES = [
  { key: 'input_tokens', label: 'Input', color: '#6ea8fe' },
  { key: 'output_tokens', label: 'Output', color: '#d97757' },
  { key: 'cache_read_tokens', label: 'Cache đọc', color: '#5cc98b' },
  { key: 'cache_create_tokens', label: 'Cache tạo', color: '#c99b5c' },
] as const;

export interface TokenSegment { key: string; label: string; color: string; value: number; pct: number }

export function tokenSegments(b: CostBreakdown | null | undefined): { segments: TokenSegment[]; total: number } {
  const rec = (b ?? {}) as unknown as Record<string, unknown>;
  const vals = TOKEN_CATEGORIES.map((c) => Math.max(0, Number(rec[c.key] ?? 0)));
  const total = vals.reduce((s, v) => s + v, 0);
  const segments = TOKEN_CATEGORIES.map((c, i) => ({
    key: c.key, label: c.label, color: c.color,
    value: vals[i],
    pct: total > 0 ? (vals[i] / total) * 100 : 0,
  }));
  return { segments, total };
}

// donut by-model: mỗi lát cost_usd + pct. tổng 0 → pct 0. sort cost giảm dần (lát lớn trước).
export interface ModelSlice { model: string; cost_usd: number; pct: number }
export function modelSlices(byModel: CostByModel[]): { slices: ModelSlice[]; total: number } {
  if (!Array.isArray(byModel) || byModel.length === 0) return { slices: [], total: 0 };
  const total = byModel.reduce((s, m) => s + Math.max(0, Number(m?.cost_usd ?? 0)), 0);
  const slices = byModel
    .map((m) => ({ model: m.model, cost_usd: Number(m?.cost_usd ?? 0), pct: total > 0 ? (Number(m?.cost_usd ?? 0) / total) * 100 : 0 }))
    .sort((a, b) => b.cost_usd - a.cost_usd);
  return { slices, total };
}

// định dạng tiền $ gọn (dashboard cost nhỏ, giữ 2 số lẻ; ≥1000 → k).
export function fmtUsd(n: number): string {
  if (!Number.isFinite(n)) return '$0';
  if (Math.abs(n) >= 1000) return `$${(n / 1000).toFixed(1)}k`;
  return `$${n.toFixed(2)}`;
}

// token gọn: 1.24M / 388K / 156
export function fmtTokens(n: number): string {
  if (!Number.isFinite(n) || n === 0) return '0';
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${Math.round(n / 1e3)}K`;
  return String(n);
}
