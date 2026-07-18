// SubAgentView.test.tsx — F2a: brief + trace (audit+live) + result + nút Huỷ theo status.
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SubAgentView } from './SubAgentView';
import { conversationApi } from '../api';
import type { OrchTask, TraceItem, AuditRow } from '../types';

function task(status: OrchTask['status'], over: Partial<OrchTask> = {}): OrchTask {
  return { id: 't1', conv_id: 'c1', role: 'credit', title: 'Thẩm định DSCR C001', status, input: { customer_id: 'C001' }, ...over };
}

const auditRows: AuditRow[] = [
  { id: 'au1', task_id: 't1', conv_id: 'c1', ts: '', actor: 'credit', tool: 'cust_get', input: { customer_id: 'C001' }, output: {} },
];

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(conversationApi, 'auditByTask').mockResolvedValue(auditRows);
});

describe('SubAgentView', () => {
  it('header role + brief + trace từ audit', async () => {
    render(<SubAgentView task={task('running')} liveTrace={[]} convId="c1" onBack={vi.fn()} />);
    expect(screen.getByText(/SUB Tín dụng/)).toBeInTheDocument();
    expect(screen.getByText('Thẩm định DSCR C001')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('cust_get')).toBeInTheDocument()); // audit row
  });

  it('running → nút Huỷ hiện; done → ẩn', () => {
    const { rerender } = render(<SubAgentView task={task('running')} liveTrace={[]} convId="c1" onBack={vi.fn()} />);
    expect(screen.getByTestId('sub-cancel')).toBeInTheDocument();
    rerender(<SubAgentView task={task('done', { result: { dscr: 3.709 } })} liveTrace={[]} convId="c1" onBack={vi.fn()} />);
    expect(screen.queryByTestId('sub-cancel')).not.toBeInTheDocument();
  });

  it('bấm Huỷ → interruptTask(convId, task.id)', async () => {
    const spy = vi.spyOn(conversationApi, 'interruptTask').mockResolvedValue({ cancelled: true });
    render(<SubAgentView task={task('running')} liveTrace={[]} convId="c1" onBack={vi.fn()} />);
    fireEvent.click(screen.getByTestId('sub-cancel'));
    expect(spy).toHaveBeenCalledWith('c1', 't1');
  });

  it('live trace + audit merge (dedup toolcall theo id)', async () => {
    const live: TraceItem[] = [
      { kind: 'tool', id: 'au1', task_id: 't1', tool: 'cust_get' }, // trùng audit → dedup
      { kind: 'thinking', id: 'th1', task_id: 't1', text: 'cân nhắc DSCR' },
    ];
    render(<SubAgentView task={task('running')} liveTrace={live} convId="c1" onBack={vi.fn()} />);
    await waitFor(() => expect(screen.getByText('cust_get')).toBeInTheDocument());
    expect(screen.getByText('cân nhắc DSCR')).toBeInTheDocument();
    expect(screen.getAllByText('cust_get').length).toBe(1); // không nhân đôi
  });

  it('result render khi có', () => {
    render(<SubAgentView task={task('done', { result: { reason: 'DSCR đạt ngưỡng' } })} liveTrace={[]} convId="c1" onBack={vi.fn()} />);
    expect(screen.getByText(/DSCR đạt ngưỡng/)).toBeInTheDocument();
  });

  it('nút quay lại → onBack', () => {
    const onBack = vi.fn();
    render(<SubAgentView task={task('running')} liveTrace={[]} convId="c1" onBack={onBack} />);
    fireEvent.click(screen.getByLabelText('Quay lại'));
    expect(onBack).toHaveBeenCalled();
  });
});
