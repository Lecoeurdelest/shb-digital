// traceComponents.test.tsx — S16 T16-4: TaskMetricsChips + ToolRankBar + ConvMetricsPanel
// (null-tolerant/backward + render). Không assert recharts (TokenBreakdownBar là CSS flex).
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TaskMetricsChips } from './TaskMetricsChips';
import { ToolRankBar } from './ToolRankBar';
import { ConvMetricsPanel } from './ConvMetricsPanel';
import type { Message, OrchTask, TraceItem } from '../../types';

function task(over: Partial<OrchTask>): OrchTask {
  return { id: 't1', conv_id: 'c', role: 'credit', title: 'x', status: 'done', ...over };
}

describe('TaskMetricsChips', () => {
  it('task CÓ metrics → chip model/duration/cost/token', () => {
    render(<TaskMetricsChips task={task({ model: 'glm-4.6', duration_ms: 8240, cost: { cost_usd: 0.42 }, input_tokens: 18400, output_tokens: 3200 })} />);
    expect(screen.getByTestId('tmc-model')).toHaveTextContent('glm-4.6');
    expect(screen.getByTestId('tmc-duration')).toHaveTextContent('8.2s');
    expect(screen.getByTestId('tmc-cost')).toHaveTextContent('$0.42');
    expect(screen.getByTestId('tmc-tokens')).toHaveTextContent('token');
  });
  it('task CŨ (null metrics) → không render (backward)', () => {
    const { container } = render(<TaskMetricsChips task={task({})} />);
    expect(container.firstChild).toBeNull();
  });
});

describe('ToolRankBar', () => {
  const trace: TraceItem[] = [
    { kind: 'tool', id: '1', task_id: 't', tool: 'credit_assess' },
    { kind: 'tool', id: '2', task_id: 't', tool: 'credit_assess' },
    { kind: 'tool', id: '3', task_id: 't', tool: 'cust_get' },
  ];
  it('rank + count (credit_assess đầu)', () => {
    render(<ToolRankBar trace={trace} />);
    expect(screen.getByTestId('tool-rank-credit_assess')).toHaveTextContent('2');
    expect(screen.getByTestId('tool-rank-cust_get')).toHaveTextContent('1');
  });
  it('trace rỗng → empty note', () => {
    render(<ToolRankBar trace={[]} />);
    expect(screen.getByTestId('tool-rank-empty')).toBeInTheDocument();
  });
});

describe('ConvMetricsPanel', () => {
  it('có metrics → panel + cost/token tổng + token bar + tool rank', () => {
    const tasks: OrchTask[] = [task({ input_tokens: 18400, output_tokens: 3200, cache_read_tokens: 42000, cost: { cost_usd: 0.42 } })];
    const messages: Message[] = [{ id: 'm', conv_id: 'c', ts: '', sender: 'assistant', content: '', meta: { metrics: { input_tokens: 6800, cost_usd: 0.14 } } }];
    const trace: TraceItem[] = [{ kind: 'tool', id: '1', task_id: 't', tool: 'credit_assess' }];
    render(<ConvMetricsPanel tasks={tasks} messages={messages} trace={trace} />);
    expect(screen.getByTestId('conv-metrics-panel')).toBeInTheDocument();
    expect(screen.getByTestId('conv-total-cost')).toHaveTextContent('$0.56'); // 0.42 + 0.14
    expect(screen.getByTestId('token-breakdown')).toBeInTheDocument(); // TokenBreakdownBar tái dùng
    expect(screen.getByTestId('tool-rank-bar')).toBeInTheDocument();
  });
  it('ca CŨ (toàn null) → không render (backward)', () => {
    const { container } = render(<ConvMetricsPanel tasks={[task({})]} messages={[]} trace={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
