// Canvas.test.tsx — S16 T16-4 polish: ConvMetricsPanel DỜI sang tab "Công việc" (cột phải), KHỎI
// cột chat. Verify: panel ở tab Công việc (không tab Đội làm việc); backward null → ẩn.
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Canvas } from './Canvas';
import type { Message, OrchTask, TraceItem } from '../types';

const taskWithMetrics: OrchTask = {
  id: 't1', conv_id: 'c', role: 'credit', title: 'Thẩm định', status: 'done',
  input_tokens: 18_400, output_tokens: 3_200, cache_read_tokens: 42_000, cache_create_tokens: 1_800,
  duration_ms: 8_240, model: 'glm-4.6', cost: { cost_usd: 0.42 },
};
const taskNoMetrics: OrchTask = { id: 't0', conv_id: 'c', role: 'credit', title: 'Ca cũ', status: 'done' };
const trace: TraceItem[] = [{ kind: 'tool', id: '1', task_id: 't1', tool: 'credit_assess' }];
const messages: Message[] = [];

function openWorkTab() {
  fireEvent.click(screen.getByText(/Công việc/));
}

describe('Canvas — ConvMetricsPanel dời sang tab Công việc (T16-4 polish)', () => {
  it('tab Công việc + task CÓ metrics → ConvMetricsPanel hiện (cột phải)', () => {
    render(<Canvas cards={[]} tasks={[taskWithMetrics]} messages={messages} trace={trace} />);
    openWorkTab();
    expect(screen.getByTestId('conv-metrics-panel')).toBeInTheDocument();
    expect(screen.getByTestId('conv-total-cost')).toHaveTextContent('$0.42');
    expect(screen.getByTestId('tool-rank-bar')).toBeInTheDocument();
  });

  it('tab Đội làm việc (mặc định) → ConvMetricsPanel KHÔNG render (chỉ ở tab Công việc)', () => {
    render(<Canvas cards={[]} tasks={[taskWithMetrics]} messages={messages} trace={trace} />);
    // mặc định tab lobby → panel không có
    expect(screen.queryByTestId('conv-metrics-panel')).not.toBeInTheDocument();
  });

  it('backward: task CŨ (null metrics) → panel ẩn dù ở tab Công việc', () => {
    render(<Canvas cards={[]} tasks={[taskNoMetrics]} messages={[]} trace={[]} />);
    openWorkTab();
    expect(screen.queryByTestId('conv-metrics-panel')).not.toBeInTheDocument();
  });

  it('panel nằm SAU cards trong luồng cuộn (không che card)', () => {
    const cards = [{ id: 'card1', conv_id: 'c', task_id: 't1', type: 'metric', ts: '', title: 'Chỉ số', items: [] }];
    render(<Canvas cards={cards} tasks={[taskWithMetrics]} messages={messages} trace={trace} />);
    openWorkTab();
    const work = screen.getByTestId('conv-metrics-panel').closest('.canvas__work');
    const cardsEl = work?.querySelector('.canvas__cards');
    const panel = screen.getByTestId('conv-metrics-panel');
    // DOM order: cards trước panel (panel sau → không che card)
    expect(cardsEl && (cardsEl.compareDocumentPosition(panel) & Node.DOCUMENT_POSITION_FOLLOWING)).toBeTruthy();
  });
});
