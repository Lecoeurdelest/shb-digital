import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { conversationApi } from '../api';
import { ApiRequestError } from '../api/client';
import type { ApprovalRow } from '../types';
import { ApprovalQueue } from './ApprovalQueue';

const FOCUSED_ID = '0198a4e1-7b6c-7abc-9012-1234567890ab';
const OTHER_ID = '11111111-2222-3333-4444-555555555555';

const focusedPending: ApprovalRow = {
  id: FOCUSED_ID,
  conv_id: 'conversation-focused',
  task_id: null,
  action: 'disburse',
  payload: { loan_id: 'L108' },
  status: 'pending',
  display: {
    customer_name: 'Hộ KD Tân Phú',
    owner_id: 'C019',
    loan_id: 'L108',
    amount_vnd: 594_000_000,
    lane: 'yellow',
  },
};

const otherPending: ApprovalRow = {
  id: OTHER_ID,
  conv_id: 'conversation-other',
  task_id: null,
  action: 'disburse',
  payload: { loan_id: 'L200' },
  status: 'pending',
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('ApprovalQueue deep-link merge', () => {
  it('merges a focused pending resource with the pending list without duplication', async () => {
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([focusedPending]);
    vi.spyOn(conversationApi, 'getApproval').mockResolvedValue(focusedPending);

    render(<ApprovalQueue focusedApprovalId={FOCUSED_ID} />);

    const row = await screen.findByTestId(`queue-row-${FOCUSED_ID}`);
    expect(screen.getAllByTestId(`queue-row-${FOCUSED_ID}`)).toHaveLength(1);
    expect(row).toHaveClass('ct__appr-wrap--focused');
    expect(screen.getByText('Hàng chờ phê duyệt (1)')).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: /Duyệt/ })).toBeInTheDocument();
  });

  it.each([
    ['approved', 'Đã duyệt'],
    ['rejected', 'Đã từ chối'],
    ['used', 'Đã thực thi'],
    ['exec_failed', 'Thực thi lỗi'],
  ] as const)('keeps focused final status %s visible without decision buttons', async (status, label) => {
    const finalRow: ApprovalRow = { ...focusedPending, status, reason: status === 'rejected' ? 'Thiếu hồ sơ' : null };
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([otherPending]);
    vi.spyOn(conversationApi, 'getApproval').mockResolvedValue(finalRow);

    render(<ApprovalQueue focusedApprovalId={FOCUSED_ID} />);

    const row = await screen.findByTestId(`queue-row-${FOCUSED_ID}`);
    expect(row).toHaveAttribute('data-approval-status', status);
    expect(within(row).getByText(label)).toBeInTheDocument();
    expect(within(row).queryByRole('button', { name: /Duyệt|Từ chối/ })).not.toBeInTheDocument();
    expect(screen.getByTestId(`queue-row-${OTHER_ID}`)).toBeInTheDocument();
    expect(screen.getByText('Hàng chờ phê duyệt (1)')).toBeInTheDocument();
  });

  it('keeps the same focused row as final and preserves display after deciding', async () => {
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([focusedPending]);
    vi.spyOn(conversationApi, 'getApproval').mockResolvedValue(focusedPending);
    vi.spyOn(conversationApi, 'decideApproval').mockResolvedValue({
      ...focusedPending,
      status: 'approved',
      decided_by: 'admin',
      display: undefined,
    });

    render(<ApprovalQueue focusedApprovalId={FOCUSED_ID} />);
    const row = await screen.findByTestId(`queue-row-${FOCUSED_ID}`);
    fireEvent.click(within(row).getByRole('button', { name: /Duyệt/ }));

    await waitFor(() => expect(row).toHaveAttribute('data-approval-status', 'approved'));
    expect(within(row).getByText('Đã duyệt')).toBeInTheDocument();
    expect(within(row).getByText('Hộ KD Tân Phú')).toBeInTheDocument();
    expect(within(row).getByText('594.000.000 ₫')).toBeInTheDocument();
    expect(within(row).queryByRole('button', { name: /Duyệt|Từ chối/ })).not.toBeInTheDocument();
    expect(screen.getByText('Hàng chờ phê duyệt (0)')).toBeInTheDocument();
  });

  it('does not hide a same-id pending list row while the exact request is loading', async () => {
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([focusedPending]);
    vi.spyOn(conversationApi, 'getApproval').mockReturnValue(new Promise<ApprovalRow>(() => {}));

    render(<ApprovalQueue focusedApprovalId={FOCUSED_ID} />);

    const row = await screen.findByTestId(`queue-row-${FOCUSED_ID}`);
    expect(row).toHaveClass('ct__appr-wrap--focused');
    expect(screen.getByText('Hàng chờ phê duyệt (1)')).toBeInTheDocument();
  });

  it('keeps the ordinary queue usable when the exact resource is not found', async () => {
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([focusedPending, otherPending]);
    vi.spyOn(conversationApi, 'getApproval').mockRejectedValue(
      new ApiRequestError(
        404,
        { code: 'not_found', message: 'Không có phiếu.', hint: 'Kiểm lại liên kết.', retryable: false },
        'not_found',
      ),
    );

    render(<ApprovalQueue focusedApprovalId={FOCUSED_ID} />);

    expect(await screen.findByTestId(`queue-row-${FOCUSED_ID}`)).toHaveClass('ct__appr-wrap--focused');
    expect(screen.getByTestId(`queue-row-${OTHER_ID}`)).toBeInTheDocument();
    expect(await screen.findByTestId('focused-approval-error')).toBeInTheDocument();
    expect(screen.getByText('Hàng chờ phê duyệt (2)')).toBeInTheDocument();
  });

  it('renders the exact final ticket even when the pending-list request fails', async () => {
    vi.spyOn(conversationApi, 'listApprovals').mockRejectedValue(new Error('network'));
    vi.spyOn(conversationApi, 'getApproval').mockResolvedValue({ ...focusedPending, status: 'used' });

    render(<ApprovalQueue focusedApprovalId={FOCUSED_ID} />);

    const row = await screen.findByTestId(`queue-row-${FOCUSED_ID}`);
    expect(within(row).getByText('Đã thực thi')).toBeInTheDocument();
    expect(screen.getByText('Lỗi tải hàng chờ')).toBeInTheDocument();
    expect(screen.getByText('Hàng chờ phê duyệt (0)')).toBeInTheDocument();
  });
});
