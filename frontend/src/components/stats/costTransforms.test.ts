// costTransforms.test.ts — S16 T16-3: pure transforms (pivot/z-filter/token/donut) + empty-guards.
// jsdom KHÔNG đo recharts SVG → test data-in→data-out là core verify của charts.
import { describe, it, expect } from 'vitest';
import { pivotTrend, filterAnomalies, tokenSegments, modelSlices, fmtUsd, fmtTokens } from './costTransforms';
import type { CostAnomaly, CostBreakdown, CostByModel, CostTrendBucket } from '../../types';

describe('pivotTrend', () => {
  it('long → wide rows + union names theo thứ tự xuất hiện', () => {
    const buckets: CostTrendBucket[] = [
      { ts: '00:00', series: { credit: 0.4, legal: 0.2 } },
      { ts: '01:00', series: { credit: 0.5, ops: 0.1 } }, // ops mới, legal thiếu
    ];
    const { rows, names } = pivotTrend(buckets);
    expect(names).toEqual(['credit', 'legal', 'ops']);
    expect(rows[0]).toEqual({ ts: '00:00', credit: 0.4, legal: 0.2, ops: 0 }); // ops→0
    expect(rows[1]).toEqual({ ts: '01:00', credit: 0.5, legal: 0, ops: 0.1 }); // legal→0
  });

  it('buckets rỗng → rows/names rỗng (không crash)', () => {
    expect(pivotTrend([])).toEqual({ rows: [], names: [] });
    // @ts-expect-error test defensive với input xấu
    expect(pivotTrend(null)).toEqual({ rows: [], names: [] });
  });
});

describe('filterAnomalies', () => {
  const anoms: CostAnomaly[] = [
    { conv_id: 'a', title: 'A', cost_usd: 0.9, mean: 0.2, stddev: 0.18, z_score: 4.0 },
    { conv_id: 'b', title: 'B', cost_usd: 0.5, mean: 0.2, stddev: 0.18, z_score: 2.1 },
    { conv_id: 'c', title: 'C', cost_usd: 0.3, mean: 0.2, stddev: 0.18, z_score: 1.5 },
  ];
  it('z≥2 → 2 row, sort z giảm dần', () => {
    const r = filterAnomalies(anoms, 2);
    expect(r.map((a) => a.conv_id)).toEqual(['a', 'b']); // c (z=1.5) loại
  });
  it('z≥3 → chỉ z cao', () => {
    expect(filterAnomalies(anoms, 3).map((a) => a.conv_id)).toEqual(['a']);
  });
  it('rỗng → rỗng', () => {
    expect(filterAnomalies([], 2)).toEqual([]);
    // @ts-expect-error defensive
    expect(filterAnomalies(undefined, 2)).toEqual([]);
  });
});

describe('tokenSegments', () => {
  it('4 category cố định + pct đúng', () => {
    const b: CostBreakdown = { input_tokens: 100, output_tokens: 100, cache_read_tokens: 200, cache_create_tokens: 0 };
    const { segments, total } = tokenSegments(b);
    expect(total).toBe(400);
    expect(segments.map((s) => s.key)).toEqual(['input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_create_tokens']);
    expect(segments[2].pct).toBe(50); // cache_read 200/400
    expect(segments[3].pct).toBe(0);
  });
  it('total 0 → mọi pct 0 (không chia 0)', () => {
    const { segments, total } = tokenSegments({ input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_create_tokens: 0 });
    expect(total).toBe(0);
    expect(segments.every((s) => s.pct === 0)).toBe(true);
  });
  it('null/thiếu field → 0 an toàn', () => {
    const { total } = tokenSegments(null);
    expect(total).toBe(0);
  });
});

describe('modelSlices', () => {
  it('pct + sort cost giảm dần', () => {
    const bm: CostByModel[] = [
      { model: 'small', cost_usd: 1, turns: 5, total_tokens: 100 },
      { model: 'big', cost_usd: 3, turns: 9, total_tokens: 300 },
    ];
    const { slices, total } = modelSlices(bm);
    expect(total).toBe(4);
    expect(slices[0].model).toBe('big'); // sort giảm
    expect(slices[0].pct).toBe(75);
  });
  it('rỗng → rỗng', () => {
    expect(modelSlices([])).toEqual({ slices: [], total: 0 });
  });
});

describe('fmt', () => {
  it('fmtUsd', () => {
    expect(fmtUsd(4.826)).toBe('$4.83');
    expect(fmtUsd(1500)).toBe('$1.5k');
    expect(fmtUsd(NaN)).toBe('$0');
  });
  it('fmtTokens', () => {
    expect(fmtTokens(1_240_000)).toBe('1.24M');
    expect(fmtTokens(388_000)).toBe('388K');
    expect(fmtTokens(156)).toBe('156');
    expect(fmtTokens(0)).toBe('0');
  });
});
