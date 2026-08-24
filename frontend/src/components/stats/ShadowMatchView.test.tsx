import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { conversationApi } from '../../api';
import type { ShadowMatchStats, ShadowMismatch } from '../../types';
import { ShadowMatchView } from './ShadowMatchView';

const approvalId = '0198a4e1-7b6c-7abc-0012-1234567890ab';
const otherApprovalId = '11111111-2222-3333-4444-555555555555';

const aggregate: ShadowMatchStats = {
  total: 3,
  comparable: 3,
  matched: 2,
  rate: 2 / 3,
  by_lane: [
    { lane: 'green', total: 2, comparable: 2, matched: 1, rate: 0.5 },
    { lane: 'red', total: 1, comparable: 1, matched: 1, rate: 1 },
  ],
  by_day: [
    { date: '2026-08-23', total: 1, comparable: 1, matched: 1, rate: 1 },
    { date: '2026-08-24', total: 2, comparable: 2, matched: 1, rate: 0.5 },
  ],
};

const mismatch: ShadowMismatch = {
  approval_id: approvalId,
  conv_id: 'conv-green-001',
  system_lane: 'green',
  system_recommendation: 'auto-eligible',
  human_decision: 'rejected',
  human_reason: 'Cần kiểm tra thêm dòng tiền.',
  decided_at: '2026-08-24T08:42:00Z',
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => vi.restoreAllMocks());

describe('ShadowMatchView (S20)', () => {
  it('render 2/3 = 66,7%, lane/day và exact-ticket deep-link với copy trung lập', async () => {
    const aggregateSpy = vi.spyOn(conversationApi, 'getShadowMatch').mockResolvedValue(aggregate);
    const mismatchSpy = vi.spyOn(conversationApi, 'listShadowMismatches').mockResolvedValue({
      items: [mismatch],
      next_cursor: null,
    });

    render(<ShadowMatchView />);

    const overall = await screen.findByTestId('kpi-Độ khớp tổng');
    expect(within(overall).getByText('66,7%')).toBeInTheDocument();
    expect(within(overall).getByText(/2\/3 ca có thể đối chiếu/)).toBeInTheDocument();
    expect(within(screen.getByTestId('kpi-Lane GREEN')).getByText('50,0%')).toBeInTheDocument();
    expect(screen.getByText('24/08/2026: 50,0% (1/2)')).toBeInTheDocument();
    expect(screen.getByText(/tín hiệu hiệu chỉnh để rà soát/)).toBeInTheDocument();

    const row = screen.getByRole('link', { name: `Mở phiếu ${approvalId}` });
    expect(row).toHaveAttribute('href', `/?tab=approvals&approval=${approvalId}`);
    expect(row).toHaveTextContent('Cần kiểm tra thêm dòng tiền.');
    expect(aggregateSpy).toHaveBeenCalledTimes(1);
    expect(mismatchSpy).toHaveBeenCalledWith({ limit: 50 });
  });

  it('tải page kế bằng cursor và nối row không trùng', async () => {
    vi.spyOn(conversationApi, 'getShadowMatch').mockResolvedValue(aggregate);
    const list = vi.spyOn(conversationApi, 'listShadowMismatches')
      .mockResolvedValueOnce({ items: [mismatch], next_cursor: 'cursor-page-2' })
      .mockResolvedValueOnce({
        items: [mismatch, { ...mismatch, approval_id: otherApprovalId }],
        next_cursor: null,
      });

    render(<ShadowMatchView />);
    await screen.findByRole('link', { name: `Mở phiếu ${approvalId}` });
    fireEvent.click(screen.getByRole('button', { name: 'Tải thêm tín hiệu' }));

    await screen.findByRole('link', { name: `Mở phiếu ${otherApprovalId}` });
    expect(list).toHaveBeenNthCalledWith(2, { limit: 50, cursor: 'cursor-page-2' });
    expect(screen.getAllByRole('link', { name: `Mở phiếu ${approvalId}` })).toHaveLength(1);
    expect(screen.queryByRole('button', { name: 'Tải thêm tín hiệu' })).not.toBeInTheDocument();
  });

  it('có trạng thái loading rồi empty quan sát được', async () => {
    const statsRequest = deferred<ShadowMatchStats>();
    const pageRequest = deferred<{ items: ShadowMismatch[]; next_cursor: null }>();
    vi.spyOn(conversationApi, 'getShadowMatch').mockReturnValue(statsRequest.promise);
    vi.spyOn(conversationApi, 'listShadowMismatches').mockReturnValue(pageRequest.promise);

    render(<ShadowMatchView />);
    expect(screen.getByRole('status')).toHaveTextContent('Đang tải sổ đối chiếu shadow');

    statsRequest.resolve({ total: 0, comparable: 0, matched: 0, rate: 0, by_lane: [], by_day: [] });
    pageRequest.resolve({ items: [], next_cursor: null });
    expect(await screen.findByTestId('shadow-mismatch-empty')).toHaveTextContent('Chưa có ca lệch');
    expect(screen.getByText('Chưa có dữ liệu theo ngày.')).toBeInTheDocument();
  });

  it('lỗi tải có alert và nút retry gọi lại cả hai endpoint', async () => {
    const aggregateSpy = vi.spyOn(conversationApi, 'getShadowMatch')
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce(aggregate);
    const mismatchSpy = vi.spyOn(conversationApi, 'listShadowMismatches')
      .mockResolvedValue({ items: [mismatch], next_cursor: null });

    render(<ShadowMatchView />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Không tải được sổ đối chiếu');
    fireEvent.click(screen.getByRole('button', { name: 'Thử tải lại' }));

    await waitFor(() => expect(aggregateSpy).toHaveBeenCalledTimes(2));
    expect(mismatchSpy).toHaveBeenCalledTimes(2);
    expect(await screen.findByTestId('shadow-match-view')).toBeInTheDocument();
  });
});
