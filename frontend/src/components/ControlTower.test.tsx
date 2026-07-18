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
  // T13: tab Tổng quan là default → mock stats/assessments (tránh poll thật lỗi trong test)
  vi.spyOn(conversationApi, 'getStats').mockResolvedValue({
    window: 'today', approvals: { approved: 12, rejected: 3, pending: 5, auto: 7 },
    assessments: { green: 9, yellow: 6, red: 2 }, conversations: { total: 20, active: 3 },
    delta: { approvals_total: 4, assessments_total: 2 },
  });
  vi.spyOn(conversationApi, 'listAssessments').mockResolvedValue([]);
});

describe('ControlTower', () => {
  it('tab Hàng chờ: list phiếu pending + nút Duyệt/Từ chối', async () => {
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Hàng chờ duyệt')); // default giờ là Tổng quan (T13-2)
    await waitFor(() => expect(screen.getByText(/disburse/)).toBeInTheDocument());
    expect(screen.getByTestId('queue-row-a1')).toBeInTheDocument();
    expect(screen.getByText(/Hàng chờ phê duyệt \(1\)/)).toBeInTheDocument();
  });

  it('duyệt từ queue → decideApproval + rời hàng chờ', async () => {
    const spy = vi.spyOn(conversationApi, 'decideApproval').mockResolvedValue({});
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Hàng chờ duyệt'));
    await waitFor(() => expect(screen.getByTestId('queue-row-a1')).toBeInTheDocument());
    fireEvent.click(screen.getAllByText(/✓ Duyệt/)[0]);
    expect(spy).toHaveBeenCalledWith('a1', 'approved', '');
    await waitFor(() => expect(screen.queryByTestId('queue-row-a1')).not.toBeInTheDocument());
  });

  // DF-B-07: từ chối 2 bước — bấm "✗ Từ chối" → expand ô lý do; lý do bắt buộc; xác nhận gửi reason.
  it('DF-B-07: Từ chối → expand ô lý do (bắt buộc); điền → xác nhận gửi reason', async () => {
    const spy = vi.spyOn(conversationApi, 'decideApproval').mockResolvedValue({});
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Hàng chờ duyệt'));
    await waitFor(() => expect(screen.getByTestId('queue-row-a1')).toBeInTheDocument());
    // bấm "✗ Từ chối" → CHƯA gửi, mở ô lý do
    fireEvent.click(screen.getByTestId('reject-open-a1'));
    expect(screen.getByTestId('reject-panel-a1')).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled(); // chưa gửi
    // xác nhận disabled khi lý do rỗng
    expect(screen.getByTestId('reject-confirm-a1')).toBeDisabled();
    // điền lý do → xác nhận gửi decideApproval(id,'rejected',reason)
    fireEvent.change(screen.getByLabelText('Lý do từ chối'), { target: { value: 'Hồ sơ chưa đủ pháp lý' } });
    fireEvent.click(screen.getByTestId('reject-confirm-a1'));
    expect(spy).toHaveBeenCalledWith('a1', 'rejected', 'Hồ sơ chưa đủ pháp lý');
  });

  it('DF-B-07: Huỷ → đóng ô lý do, không gửi', async () => {
    const spy = vi.spyOn(conversationApi, 'decideApproval').mockResolvedValue({});
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Hàng chờ duyệt'));
    await waitFor(() => expect(screen.getByTestId('queue-row-a1')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('reject-open-a1'));
    fireEvent.click(screen.getByText('Huỷ'));
    expect(screen.queryByTestId('reject-panel-a1')).not.toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
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

  // DF-B-01: queue render display (tên khách/tiền/loan/lane) thay UUID+JSON thô.
  it('DF-B-01: row có display → tên khách + tiền VNĐ + loan + lane-chip', async () => {
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([
      { id: 'a1', conv_id: 'c1conv', task_id: null, action: 'disburse', payload: { x: 1 }, status: 'pending',
        display: { customer_name: 'Hộ KD Tân Phú', owner_id: 'C019', loan_id: 'L108', amount_vnd: 594_000_000, lane: 'yellow' } },
    ]);
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Hàng chờ duyệt'));
    await waitFor(() => expect(screen.getByText('Hộ KD Tân Phú')).toBeInTheDocument()); // tên khách, không UUID
    expect(screen.getByText('594.000.000 ₫')).toBeInTheDocument(); // tiền format VN
    expect(screen.getByText('L108')).toBeInTheDocument();
    expect(screen.getByText('YELLOW')).toBeInTheDocument(); // lane chip
  });

  it('DF-B-01 backward: display VẮNG (BE chưa deploy) → fallback shortId + JSON như cũ, không vỡ', async () => {
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([
      { id: 'a2', conv_id: 'abcdefghijklmnopqrst', task_id: null, action: 'disburse', payload: { loan: 'L001' }, status: 'pending' },
    ]);
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Hàng chờ duyệt'));
    await waitFor(() => expect(screen.getByTestId('queue-row-a2')).toBeInTheDocument());
    // fallback shortId conv (không có display) + JSON payload hiện
    expect(screen.getByText(/abcdefghij…/)).toBeInTheDocument();
    expect(screen.getByText(/L001/)).toBeInTheDocument();
  });
});
