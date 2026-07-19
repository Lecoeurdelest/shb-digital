// ConvMetricsPanel.tsx — S16 T16-4: khối metrics TỔNG cả ca (Workspace — nơi có conv-wide data:
// tasks[] + messages[] + trace[]). Cộng tasks + main-turn (aggregateConvMetrics) → TokenBreakdownBar
// TÁI DÙNG + cost/token tổng + ToolRankBar. has_any=false (ca cũ toàn null) → KHÔNG render (backward).
import { aggregateConvMetrics } from './traceMetrics';
import { fmtUsd, fmtTokens } from './costTransforms';
import { TokenBreakdownBar } from './TokenBreakdownBar';
import { ToolRankBar } from './ToolRankBar';
import type { Message, OrchTask, TraceItem } from '../../types';
import './ConvMetricsPanel.css';

export function ConvMetricsPanel({ tasks, messages, trace }: { tasks: OrchTask[]; messages: Message[]; trace: TraceItem[] }) {
  const agg = aggregateConvMetrics(tasks, messages);
  if (!agg.has_any) return null; // ca cũ chưa có metrics → không chiếm chỗ (backward)

  return (
    <div className="cmp" data-testid="conv-metrics-panel">
      <div className="cmp__head">
        <span className="cmp__title">Chi phí &amp; token cả ca</span>
        <span className="cmp__totals">
          <span className="cmp__cost" data-testid="conv-total-cost">💰 {fmtUsd(agg.total_cost_usd)} <em>ước tính</em></span>
          <span className="cmp__tokens">🔢 {fmtTokens(agg.total_tokens)} token</span>
        </span>
      </div>
      <TokenBreakdownBar breakdown={agg.breakdown} />
      <ToolRankBar trace={trace} />
    </div>
  );
}
