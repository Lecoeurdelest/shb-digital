// ApprovalPanel.test.tsx — card approval render + decide + trạng thái (T3-3 §E/D-40).
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ApprovalPanel } from './ApprovalPanel';
import { CardRenderer } from './CardRenderer';
import type { Card } from '../../types';

function approvalCard(over: Partial<Card> = {}): Card {
  return {
    id: 'card1', conv_id: 'c1', task_id: null, type: 'approval', ts: '2026-01-01',
    title: 'Phê duyệt giải ngân', action: 'Giải ngân L001', approval_id: 'appr_1', status: 'pending',
    items: [{ label: 'Số tiền', value: '5,000,000,000 VND' }],
    ...over,
  };
}

describe('ApprovalPanel', () => {
  it('pending → nút Duyệt/Từ chối + ô lý do + items render', () => {
    render(<ApprovalPanel card={approvalCard()} onDecide={vi.fn()} />);
    expect(screen.getByText('Giải ngân L001')).toBeInTheDocument();
    expect(screen.getByText('5,000,000,000 VND')).toBeInTheDocument();
    expect(screen.getByText(/CHỜ DUYỆT/)).toBeInTheDocument();
    expect(screen.getByTestId('approval-approve')).toBeInTheDocument();
    expect(screen.getByTestId('approval-reject')).toBeInTheDocument();
  });

  it('bấm Duyệt → onDecide(approvalId, "approve", reason)', () => {
    const onDecide = vi.fn();
    render(<ApprovalPanel card={approvalCard()} onDecide={onDecide} />);
    fireEvent.change(screen.getByLabelText('Lý do quyết định'), { target: { value: 'OK đủ điều kiện' } });
    fireEvent.click(screen.getByTestId('approval-approve'));
    expect(onDecide).toHaveBeenCalledWith('appr_1', 'approved', 'OK đủ điều kiện');
  });

  it('bấm Từ chối → onDecide(..., "reject", ...)', () => {
    const onDecide = vi.fn();
    render(<ApprovalPanel card={approvalCard()} onDecide={onDecide} />);
    fireEvent.click(screen.getByTestId('approval-reject'));
    expect(onDecide).toHaveBeenCalledWith('appr_1', 'rejected', '');
  });

  it('status=approved → KHÔNG nút, badge ĐÃ DUYỆT + text bằng chứng (không xoá card)', () => {
    render(<ApprovalPanel card={approvalCard({ status: 'approved', decided_by: 'admin' })} onDecide={vi.fn()} />);
    expect(screen.getByText(/ĐÃ DUYỆT/)).toBeInTheDocument();
    expect(screen.queryByTestId('approval-approve')).not.toBeInTheDocument();
    expect(screen.getByText(/hành động thực thi/)).toBeInTheDocument();
    expect(screen.getByText(/admin/)).toBeInTheDocument();
  });

  it('status=rejected → badge TỪ CHỐI + text dừng', () => {
    render(<ApprovalPanel card={approvalCard({ status: 'rejected', reason: 'DSCR thấp' })} onDecide={vi.fn()} />);
    expect(screen.getByText(/TỪ CHỐI/)).toBeInTheDocument();
    expect(screen.getByText(/Main dừng hành động/)).toBeInTheDocument();
    expect(screen.getByText(/DSCR thấp/)).toBeInTheDocument();
  });

  it('thiếu approval_id → nút disabled + cảnh báo (defensive; approval_id CHỐT, không fallback card.id)', () => {
    render(<ApprovalPanel card={approvalCard({ approval_id: undefined })} onDecide={vi.fn()} />);
    expect(screen.getByText(/Thiếu mã phiếu/)).toBeInTheDocument();
    expect(screen.getByTestId('approval-approve')).toBeDisabled();
  });

  it('CardRenderer type=approval → render ApprovalPanel (không còn placeholder S2)', () => {
    render(<CardRenderer card={approvalCard()} onDecide={vi.fn()} />);
    expect(screen.getByTestId('card-approval')).toBeInTheDocument();
    expect(screen.getByTestId('approval-approve')).toBeInTheDocument();
    expect(screen.queryByText(/Sprint 4/)).not.toBeInTheDocument();
  });
});
