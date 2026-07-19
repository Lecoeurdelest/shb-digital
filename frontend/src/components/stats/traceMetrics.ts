// traceMetrics.ts — S16 T16-4: pure functions cho trace/metrics per-ca (tách khỏi component để TEST
// data-in→out — jsdom không đo recharts SVG). Cộng-tổng ca = tasks + main-turn metrics, coerce
// null→0 (turn cũ null → góp 0, KHÔNG NaN). rank tool-call từ trace. Field-name KHỚP TokenBreakdownBar.
import type { CostBreakdown, Message, OrchTask, TraceItem, TurnMetrics } from '../../types';

const TOKEN_KEYS = ['input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_create_tokens'] as const;

function num(x: unknown): number {
  const n = Number(x);
  return Number.isFinite(n) ? n : 0;
}

// task CÓ metrics không (ít nhất 1 field token/duration/cost/model non-null) → mới render chip/breakdown.
export function hasTaskMetrics(task: OrchTask): boolean {
  return TOKEN_KEYS.some((k) => task[k] != null)
    || task.duration_ms != null
    || task.model != null
    || (task.cost != null && task.cost.cost_usd != null);
}

// 4 token field của 1 task → CostBreakdown (đưa thẳng vào TokenBreakdownBar, không adapter). null→0.
export function taskBreakdown(task: OrchTask): CostBreakdown {
  return {
    input_tokens: num(task.input_tokens),
    output_tokens: num(task.output_tokens),
    cache_read_tokens: num(task.cache_read_tokens),
    cache_create_tokens: num(task.cache_create_tokens),
  };
}

// cost_usd của task từ jsonb cost (T16-1 shape {cost_usd}). null/thiếu → null (chip không hiện).
export function taskCostUsd(task: OrchTask): number | null {
  const c = task.cost?.cost_usd;
  return typeof c === 'number' && Number.isFinite(c) ? c : null;
}

// metrics MAIN từ message.meta.metrics (assistant role='main'). shape tự do → đọc an toàn.
export function turnMetrics(msg: Message): TurnMetrics | null {
  const m = msg.meta?.metrics;
  if (!m || typeof m !== 'object') return null;
  return m as TurnMetrics;
}

// CỘNG-TỔNG cả ca: 4 token của mọi task + mọi main-turn metrics. cost_usd tổng. null→0 (turn cũ góp 0).
export interface ConvAggregate {
  breakdown: CostBreakdown;
  total_cost_usd: number;
  total_tokens: number;
  has_any: boolean; // có ít nhất 1 nguồn metrics non-null → mới hiện khối tổng
}
export function aggregateConvMetrics(tasks: OrchTask[], messages: Message[]): ConvAggregate {
  const bd: CostBreakdown = { input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_create_tokens: 0 };
  let cost = 0;
  let hasAny = false;

  for (const t of tasks ?? []) {
    if (hasTaskMetrics(t)) hasAny = true;
    for (const k of TOKEN_KEYS) bd[k] += num(t[k]);
    const c = taskCostUsd(t);
    if (c != null) cost += c;
  }
  for (const msg of messages ?? []) {
    const m = turnMetrics(msg);
    if (!m) continue;
    hasAny = true;
    for (const k of TOKEN_KEYS) bd[k] += num(m[k]);
    if (m.cost_usd != null) cost += num(m.cost_usd);
  }

  const total_tokens = TOKEN_KEYS.reduce((s, k) => s + bd[k], 0);
  return { breakdown: bd, total_cost_usd: cost, total_tokens, has_any: hasAny };
}

// rank tool-call: đếm theo tool từ trace (kind='tool'), sort giảm dần. thinking bỏ. rỗng → [].
export interface ToolRank { tool: string; count: number; pct: number }
export function rankToolCalls(trace: TraceItem[]): ToolRank[] {
  if (!Array.isArray(trace)) return [];
  const counts = new Map<string, number>();
  for (const it of trace) {
    if (it.kind !== 'tool' || !it.tool) continue;
    counts.set(it.tool, (counts.get(it.tool) ?? 0) + 1);
  }
  const total = [...counts.values()].reduce((s, c) => s + c, 0);
  return [...counts.entries()]
    .map(([tool, count]) => ({ tool, count, pct: total > 0 ? (count / total) * 100 : 0 }))
    .sort((a, b) => b.count - a.count);
}

// duration ms → gọn: 820ms / 4.2s / 1m2s
export function fmtDuration(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return '—';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  return `${m}m${Math.round(s - m * 60)}s`;
}
