// traceMetrics.test.ts — S16 T16-4: pure transforms (aggregate null→0, rank, hasMetrics, fmt).
import { describe, it, expect } from 'vitest';
import { aggregateConvMetrics, rankToolCalls, hasTaskMetrics, taskBreakdown, taskCostUsd, turnMetrics, fmtDuration } from './traceMetrics';
import type { Message, OrchTask, TraceItem } from '../../types';

function task(over: Partial<OrchTask>): OrchTask {
  return { id: 't', conv_id: 'c', role: 'credit', title: 'x', status: 'done', ...over };
}

describe('hasTaskMetrics', () => {
  it('có token/duration/model/cost → true', () => {
    expect(hasTaskMetrics(task({ input_tokens: 100 }))).toBe(true);
    expect(hasTaskMetrics(task({ duration_ms: 500 }))).toBe(true);
    expect(hasTaskMetrics(task({ model: 'glm-4.6' }))).toBe(true);
    expect(hasTaskMetrics(task({ cost: { cost_usd: 0.1 } }))).toBe(true);
  });
  it('task cũ (mọi field null) → false (backward — không render)', () => {
    expect(hasTaskMetrics(task({ input_tokens: null, duration_ms: null, model: null, cost: null }))).toBe(false);
    expect(hasTaskMetrics(task({}))).toBe(false);
  });
});

describe('taskBreakdown + taskCostUsd', () => {
  it('4 token field → CostBreakdown; null→0', () => {
    expect(taskBreakdown(task({ input_tokens: 10, output_tokens: 20, cache_read_tokens: null }))).toEqual({
      input_tokens: 10, output_tokens: 20, cache_read_tokens: 0, cache_create_tokens: 0,
    });
  });
  it('cost_usd từ jsonb; thiếu → null', () => {
    expect(taskCostUsd(task({ cost: { cost_usd: 0.42 } }))).toBe(0.42);
    expect(taskCostUsd(task({ cost: { tool_calls: 1 } }))).toBeNull();
    expect(taskCostUsd(task({ cost: null }))).toBeNull();
  });
});

describe('turnMetrics', () => {
  const msg = (meta: Record<string, unknown> | null): Message => ({ id: 'm', conv_id: 'c', ts: '', sender: 'assistant', content: '', meta });
  it('meta.metrics → object', () => {
    expect(turnMetrics(msg({ metrics: { input_tokens: 50, cost_usd: 0.1 } }))).toEqual({ input_tokens: 50, cost_usd: 0.1 });
  });
  it('không meta/metrics → null', () => {
    expect(turnMetrics(msg(null))).toBeNull();
    expect(turnMetrics(msg({ other: 1 }))).toBeNull();
  });
});

describe('aggregateConvMetrics', () => {
  it('cộng tasks + main-turn; null→0 (không NaN)', () => {
    const tasks: OrchTask[] = [
      task({ input_tokens: 100, output_tokens: 50, cache_read_tokens: 200, cost: { cost_usd: 0.3 } }),
      task({ input_tokens: null, output_tokens: 30, cost: null }), // task cũ token null → góp 0
    ];
    const messages: Message[] = [
      { id: 'm1', conv_id: 'c', ts: '', sender: 'assistant', content: '', meta: { metrics: { input_tokens: 10, cost_usd: 0.05 } } },
      { id: 'm2', conv_id: 'c', ts: '', sender: 'user', content: '', meta: null }, // user không metrics
    ];
    const agg = aggregateConvMetrics(tasks, messages);
    expect(agg.breakdown.input_tokens).toBe(110); // 100 + 0 + 10
    expect(agg.breakdown.output_tokens).toBe(80); // 50 + 30
    expect(agg.breakdown.cache_read_tokens).toBe(200);
    expect(agg.total_cost_usd).toBeCloseTo(0.35); // 0.3 + 0.05
    expect(agg.total_tokens).toBe(390);
    expect(agg.has_any).toBe(true);
    expect(Number.isNaN(agg.breakdown.input_tokens)).toBe(false);
  });
  it('ca toàn null → has_any false, tổng 0 (TokenBreakdownBar hit empty)', () => {
    const agg = aggregateConvMetrics([task({}), task({})], []);
    expect(agg.has_any).toBe(false);
    expect(agg.total_tokens).toBe(0);
  });
  it('input rỗng → an toàn', () => {
    // @ts-expect-error defensive
    expect(aggregateConvMetrics(null, null).total_tokens).toBe(0);
  });
});

describe('rankToolCalls', () => {
  const trace: TraceItem[] = [
    { kind: 'tool', id: '1', task_id: 't', tool: 'credit_assess' },
    { kind: 'tool', id: '2', task_id: 't', tool: 'cust_get' },
    { kind: 'tool', id: '3', task_id: 't', tool: 'credit_assess' },
    { kind: 'thinking', id: '4', task_id: 't', text: 'nghĩ' }, // thinking bỏ
  ];
  it('đếm + sort giảm dần + pct', () => {
    const r = rankToolCalls(trace);
    expect(r[0]).toEqual({ tool: 'credit_assess', count: 2, pct: (2 / 3) * 100 });
    expect(r[1].tool).toBe('cust_get');
    expect(r).toHaveLength(2); // thinking không tính
  });
  it('rỗng → []', () => {
    expect(rankToolCalls([])).toEqual([]);
    // @ts-expect-error defensive
    expect(rankToolCalls(null)).toEqual([]);
  });
});

describe('fmtDuration', () => {
  it('ms/s/m', () => {
    expect(fmtDuration(820)).toBe('820ms');
    expect(fmtDuration(4200)).toBe('4.2s');
    expect(fmtDuration(62000)).toBe('1m2s');
    expect(fmtDuration(null)).toBe('—');
  });
});
