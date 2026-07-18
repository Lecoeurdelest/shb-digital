// ControlTower.test.tsx — 4 khối admin: queue (duyệt) · audit · agents. Mock API.
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ControlTower } from './ControlTower';
import { conversationApi } from '../api';
import type { ApprovalRow, AuditRow, Conversation } from '../types';

const appr: ApprovalRow[] = [
  { id: 'a1', conv_id: 'c1conv', task_id: null, action: 'disburse', payload: { items: [{ label: 'L001' }] }, status: 'pending' },
];
const audit: AuditRow[] = [
  { id: 'au1', task_id: 't1', conv_id: 'c1', ts: '2026-01-01T10:00:00', actor: 'credit', tool: 'credit_assess', input: { owner_id: 'C001' }, output: {} },
];
const convs: Conversation[] = [
  { id: 'c1', title: 'x', status: 'running', created_at: '' },
  { id: 'c2', title: 'y', status: 'done', created_at: '' },
];

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue(appr);
  vi.spyOn(conversationApi, 'auditFiltered').mockResolvedValue(audit);
  vi.spyOn(conversationApi, 'listConversations').mockResolvedValue(convs);
});

describe('ControlTower', () => {
  it('tab Hàng chờ: list phiếu pending + nút Duyệt/Từ chối', async () => {
    render(<ControlTower onBack={vi.fn()} />);
    await waitFor(() => expect(screen.getByText(/disburse/)).toBeInTheDocument());
    expect(screen.getByTestId('queue-row-a1')).toBeInTheDocument();
    expect(screen.getByText(/Hàng chờ phê duyệt \(1\)/)).toBeInTheDocument();
  });

  it('duyệt từ queue → decideApproval + rời hàng chờ', async () => {
    const spy = vi.spyOn(conversationApi, 'decideApproval').mockResolvedValue({});
    render(<ControlTower onBack={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('queue-row-a1')).toBeInTheDocument());
    fireEvent.click(screen.getAllByText(/✓ Duyệt/)[0]);
    expect(spy).toHaveBeenCalledWith('a1', 'approved', '');
    await waitFor(() => expect(screen.queryByTestId('queue-row-a1')).not.toBeInTheDocument());
  });

  it('tab Nhật ký: audit rows + filter', async () => {
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Nhật ký tool'));
    await waitFor(() => expect(screen.getByText('credit_assess')).toBeInTheDocument());
    expect(screen.getByLabelText('Lọc conv_id')).toBeInTheDocument();
  });

  it('tab Trạng thái: đếm ca theo status', async () => {
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Trạng thái đội'));
    await waitFor(() => expect(screen.getByText(/Trạng thái đội — 2 ca/)).toBeInTheDocument());
    // cost meter note (per-turn, không per-tool)
    expect(screen.getByText(/Cost meter/)).toBeInTheDocument();
  });

  it('nút ← Workspace → onBack', () => {
    const onBack = vi.fn();
    render(<ControlTower onBack={onBack} />);
    fireEvent.click(screen.getByText(/Workspace/));
    expect(onBack).toHaveBeenCalled();
  });

  it('tab So sánh: chạy compare → 2 cột single + multi + metrics', async () => {
    vi.spyOn(conversationApi, 'runCompare').mockResolvedValue({
      single: { text: 'trả lời đơn', duration_s: 4, tool_calls: 0 },
      multi: { text: 'đội thẩm định có nguồn', duration_s: 38, tool_calls: 4, cards: 2, conv_id: 'cX' },
    });
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText(/So sánh/));
    fireEvent.click(screen.getByTestId('compare-run'));
    await waitFor(() => expect(screen.getByText('trả lời đơn')).toBeInTheDocument());
    expect(screen.getByText('đội thẩm định có nguồn')).toBeInTheDocument();
    expect(screen.getByText(/4 tool/)).toBeInTheDocument(); // metric multi
  });

  it('compare partial (multi null) → cột single + note partial', async () => {
    vi.spyOn(conversationApi, 'runCompare').mockResolvedValue({
      single: { text: 'chỉ single', duration_s: 4 },
      multi: null,
    });
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText(/So sánh/));
    fireEvent.click(screen.getByTestId('compare-run'));
    await waitFor(() => expect(screen.getByText('chỉ single')).toBeInTheDocument());
    expect(screen.getByText(/partial/)).toBeInTheDocument();
  });
});
