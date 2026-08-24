// StatsOverview.test.tsx — tab Tổng quan (T13-2): KPI render, window switch (query lại), delta, AUTO sub.
import { act, render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { StatsOverview } from './StatsOverview';
import { conversationApi } from '../../api';
import type { StatsResponse } from '../../types';

const today: StatsResponse = {
  window: 'today', approvals: { approved: 12, rejected: 3, pending: 5, auto: 7 },
  assessments: { green: 9, yellow: 6, red: 2 }, conversations: { total: 20, active: 3 },
  delta: { approvals_total: 4, assessments_total: 2 },
};
const week: StatsResponse = {
  window: '7d', approvals: { approved: 72, rejected: 18, pending: 5, auto: 42 },
  assessments: { green: 54, yellow: 36, red: 12 }, conversations: { total: 120, active: 3 },
  delta: { approvals_total: 14, assessments_total: -3 },
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => vi.restoreAllMocks());

describe('StatsOverview (T13-2)', () => {
  it('render KPI từ stats: đã duyệt + AUTO sub + đang chờ + 3 lane hồ sơ', async () => {
    vi.spyOn(conversationApi, 'getStats').mockResolvedValue(today);
    render(<StatsOverview />);
    await waitFor(() => expect(within(screen.getByTestId('kpi-Phiếu đã duyệt')).getByText('12')).toBeInTheDocument());
    expect(screen.getByText(/AUTO: 7/)).toBeInTheDocument(); // badge AUTO trong sub
    expect(within(screen.getByTestId('kpi-Đang chờ')).getByText('5')).toBeInTheDocument();
    expect(within(screen.getByTestId('kpi-Hồ sơ Green')).getByText('9')).toBeInTheDocument();
    expect(within(screen.getByTestId('kpi-Hồ sơ Red')).getByText('2')).toBeInTheDocument();
    expect(within(screen.getByTestId('kpi-Phiên xử lý')).getByText('20')).toBeInTheDocument();
  });

  it('delta ↑ hiện cạnh số (approvals_total)', async () => {
    vi.spyOn(conversationApi, 'getStats').mockResolvedValue(today);
    render(<StatsOverview />);
    await waitFor(() => expect(within(screen.getByTestId('kpi-Phiếu đã duyệt')).getByText(/↑ 4/)).toBeInTheDocument());
  });

  it('window switch today→7d → gọi lại getStats(7d) + số đổi', async () => {
    const spy = vi.spyOn(conversationApi, 'getStats')
      .mockResolvedValueOnce(today).mockResolvedValueOnce(week);
    render(<StatsOverview />);
    await waitFor(() => expect(within(screen.getByTestId('kpi-Phiếu đã duyệt')).getByText('12')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('window-7d'));
    await waitFor(() => expect(spy).toHaveBeenCalledWith('7d'));
    await waitFor(() => expect(within(screen.getByTestId('kpi-Phiếu đã duyệt')).getByText('72')).toBeInTheDocument());
  });

  it('bỏ qua response 24h cũ nếu response 7d về trước', async () => {
    const oldRequest = deferred<StatsResponse>();
    const currentRequest = deferred<StatsResponse>();
    const spy = vi.spyOn(conversationApi, 'getStats')
      .mockReturnValueOnce(oldRequest.promise)
      .mockReturnValueOnce(currentRequest.promise);
    render(<StatsOverview />);
    expect(spy).toHaveBeenCalledWith('24h');

    fireEvent.click(screen.getByTestId('window-7d'));
    await waitFor(() => expect(spy).toHaveBeenCalledWith('7d'));
    await act(async () => { currentRequest.resolve(week); await currentRequest.promise; });
    expect(within(screen.getByTestId('kpi-Phiếu đã duyệt')).getByText('72')).toBeInTheDocument();

    await act(async () => { oldRequest.resolve(today); await oldRequest.promise; });
    expect(within(screen.getByTestId('kpi-Phiếu đã duyệt')).getByText('72')).toBeInTheDocument();
    expect(within(screen.getByTestId('kpi-Phiếu đã duyệt')).queryByText('12')).not.toBeInTheDocument();
  });

  it('Đang chờ >0 → tone warn (nổi màu)', async () => {
    vi.spyOn(conversationApi, 'getStats').mockResolvedValue(today);
    render(<StatsOverview />);
    await waitFor(() => expect(screen.getByTestId('kpi-Đang chờ')).toHaveClass('kpi--warn'));
  });

  it('mở mặc định chỉ fetch KPI, không fetch telemetry kỹ thuật', async () => {
    vi.spyOn(conversationApi, 'getStats').mockResolvedValue(today);
    const getCost = vi.spyOn(conversationApi, 'getCost');
    const getCostTrend = vi.spyOn(conversationApi, 'getCostTrend');
    render(<StatsOverview />);
    await waitFor(() => expect(within(screen.getByTestId('kpi-Phiếu đã duyệt')).getByText('12')).toBeInTheDocument());
    expect(getCost).not.toHaveBeenCalled();
    expect(getCostTrend).not.toHaveBeenCalled();
    expect(screen.queryByTestId('cost-total')).not.toBeInTheDocument();
  });

  it('segmented window có 24h/7d/30d', async () => {
    vi.spyOn(conversationApi, 'getStats').mockResolvedValue(today);
    render(<StatsOverview />);
    await waitFor(() => expect(screen.getByTestId('window-24h')).toBeInTheDocument());
    expect(screen.getByTestId('window-7d')).toBeInTheDocument();
    expect(screen.getByTestId('window-30d')).toBeInTheDocument();
  });

  it('render breakdown nghiệp vụ: luồng quyết định, chất lượng hồ sơ, tải xử lý', async () => {
    vi.spyOn(conversationApi, 'getStats').mockResolvedValue(today);
    render(<StatsOverview />);
    await waitFor(() => expect(screen.getByTestId('stats-insights')).toBeInTheDocument());
    expect(screen.getByText('Luồng quyết định')).toBeInTheDocument();
    expect(screen.getByText('Chất lượng hồ sơ')).toBeInTheDocument();
    expect(screen.getByText('Tải xử lý')).toBeInTheDocument();
    expect(screen.getByText('Cần rà soát')).toBeInTheDocument();
    expect(screen.getByText('đang cần theo dõi')).toBeInTheDocument();
  });
});
