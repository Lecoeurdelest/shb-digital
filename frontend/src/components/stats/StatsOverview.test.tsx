// StatsOverview.test.tsx — tab Tổng quan (T13-2): KPI render, window switch (query lại), delta, AUTO sub.
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { StatsOverview } from './StatsOverview';
import { conversationApi } from '../../api';
import { ApiRequestError } from '../../api/client';
import type { CostResponse, CostTrendResponse, StatsResponse } from '../../types';

const cost: CostResponse = {
  window: '24h', total_cost_usd: 4.82, cost_estimated: true,
  breakdown: { input_tokens: 100, output_tokens: 100, cache_read_tokens: 200, cache_create_tokens: 0 },
  by_model: [{ model: 'glm-4.6', cost_usd: 3, turns: 10, total_tokens: 1000 }],
  by_role: [{ role: 'credit', cost_usd: 2, turns: 6 }],
  anomalies: [{ conv_id: 'cX', title: 'Ca bất thường', cost_usd: 0.9, mean: 0.2, stddev: 0.18, z_score: 4.0 }],
  delta: { total_cost_pct: 12.4 },
};
const trend: CostTrendResponse = { buckets: [{ ts: '00:00', series: { credit: 0.4 } }] };
// mock cost cluster mặc định OK (nhiều test chỉ quan tâm KPI — tránh phụ thuộc mock backend thật)
function mockCostOk() {
  vi.spyOn(conversationApi, 'getCost').mockResolvedValue(cost);
  vi.spyOn(conversationApi, 'getCostTrend').mockResolvedValue(trend);
}

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

  it('Đang chờ >0 → tone warn (nổi màu)', async () => {
    vi.spyOn(conversationApi, 'getStats').mockResolvedValue(today);
    render(<StatsOverview />);
    await waitFor(() => expect(screen.getByTestId('kpi-Đang chờ')).toHaveClass('kpi--warn'));
  });

  it('footer chú thích demo admin gộp vai', async () => {
    vi.spyOn(conversationApi, 'getStats').mockResolvedValue(today);
    render(<StatsOverview />);
    await waitFor(() => expect(screen.getByText(/admin gộp vai/)).toBeInTheDocument());
  });

  // ── S16 T16-3: cụm cost ──
  it('T16-3: cost cluster render — total + token breakdown + anomaly', async () => {
    vi.spyOn(conversationApi, 'getStats').mockResolvedValue(today);
    mockCostOk();
    render(<StatsOverview />);
    await waitFor(() => expect(screen.getByTestId('cost-total')).toBeInTheDocument());
    expect(screen.getByText(/tổng \$4\.82/)).toBeInTheDocument();
    expect(screen.getAllByText(/ước tính/).length).toBeGreaterThan(0); // cost_estimated (2 chỗ: header + donut)
    expect(screen.getByTestId('token-breakdown')).toBeInTheDocument();
    expect(screen.getByTestId('cost-anomaly-table')).toBeInTheDocument();
    expect(screen.getByTestId('anom-row-cX')).toBeInTheDocument();
  });

  it('T16-3: độc lập degrade — getCost 404 → 7 KPI VẪN render + cost hiện note', async () => {
    vi.spyOn(conversationApi, 'getStats').mockResolvedValue(today);
    vi.spyOn(conversationApi, 'getCost').mockRejectedValue(new ApiRequestError(404, { code: 'not_found', message: 'chưa có', hint: '', retryable: false }, 'nf'));
    vi.spyOn(conversationApi, 'getCostTrend').mockRejectedValue(new Error('nf'));
    render(<StatsOverview />);
    // KPI vẫn render (không bị cost-fail chặn)
    await waitFor(() => expect(within(screen.getByTestId('kpi-Phiếu đã duyệt')).getByText('12')).toBeInTheDocument());
    // cost block hiện note lỗi im đẹp
    await waitFor(() => expect(screen.getByTestId('cost-error')).toBeInTheDocument());
  });

  it('T16-3: anomaly row-click → onOpenAudit(conv_id)', async () => {
    vi.spyOn(conversationApi, 'getStats').mockResolvedValue(today);
    mockCostOk();
    const onOpenAudit = vi.fn();
    render(<StatsOverview onOpenAudit={onOpenAudit} />);
    await waitFor(() => expect(screen.getByTestId('anom-row-cX')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('anom-row-cX'));
    expect(onOpenAudit).toHaveBeenCalledWith('cX');
  });

  it('T16-3: segmented window có 24h/7d/30d', async () => {
    vi.spyOn(conversationApi, 'getStats').mockResolvedValue(today);
    mockCostOk();
    render(<StatsOverview />);
    await waitFor(() => expect(screen.getByTestId('window-24h')).toBeInTheDocument());
    expect(screen.getByTestId('window-7d')).toBeInTheDocument();
    expect(screen.getByTestId('window-30d')).toBeInTheDocument();
  });
});
