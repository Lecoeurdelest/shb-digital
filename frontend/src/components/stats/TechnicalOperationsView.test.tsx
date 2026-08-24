import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { conversationApi } from '../../api';
import { ApiRequestError } from '../../api/client';
import type { CostResponse, CostTrendResponse } from '../../types';
import { TechnicalOperationsView } from './TechnicalOperationsView';

const cost: CostResponse = {
  window: '24h',
  total_cost_usd: 4.82,
  cost_estimated: true,
  breakdown: { input_tokens: 100, output_tokens: 50, cache_read_tokens: 200, cache_create_tokens: 10 },
  by_model: [{ model: 'glm-4.6', cost_usd: 3, turns: 10, total_tokens: 1000 }],
  by_role: [{ role: 'credit', cost_usd: 2, turns: 6 }],
  anomalies: [{ conv_id: 'cX', title: 'Phiên xử lý bất thường', cost_usd: 0.9, mean: 0.2, stddev: 0.18, z_score: 4 }],
  delta: { total_cost_pct: 12.4 },
};
const trend: CostTrendResponse = { buckets: [{ ts: '00:00', series: { credit: 0.4 } }] };

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => vi.restoreAllMocks());

describe('TechnicalOperationsView', () => {
  it('mount tab mới mới fetch cost/trend và render telemetry', async () => {
    const getCost = vi.spyOn(conversationApi, 'getCost').mockResolvedValue(cost);
    const getCostTrend = vi.spyOn(conversationApi, 'getCostTrend').mockResolvedValue(trend);
    render(<TechnicalOperationsView />);

    await waitFor(() => expect(screen.getByTestId('cost-total')).toHaveTextContent('$4.82'));
    expect(getCost).toHaveBeenCalledWith('24h');
    expect(getCostTrend).toHaveBeenCalledWith('24h', 'hour', 'role');
    expect(screen.getByTestId('token-breakdown')).toBeInTheDocument();
    expect(screen.getByTestId('model-donut')).toBeInTheDocument();
    expect(screen.getByTestId('latency-note')).toHaveTextContent('API hiện chưa cung cấp');
    expect(screen.getByTestId('latency-note')).toHaveTextContent('từng phiên xử lý');
  });

  it('đổi window dùng bucket day và anomaly mở nhật ký kiểm soát', async () => {
    vi.spyOn(conversationApi, 'getCost').mockResolvedValue(cost);
    const getCostTrend = vi.spyOn(conversationApi, 'getCostTrend').mockResolvedValue(trend);
    const onOpenAudit = vi.fn();
    render(<TechnicalOperationsView onOpenAudit={onOpenAudit} />);
    await screen.findByTestId('anom-row-cX');

    fireEvent.click(screen.getByTestId('technical-window-7d'));
    await waitFor(() => expect(getCostTrend).toHaveBeenCalledWith('7d', 'day', 'role'));
    fireEvent.click(screen.getByTestId('anom-row-cX'));
    expect(onOpenAudit).toHaveBeenCalledWith('cX');
  });

  it('cost lỗi degrade trong tab kỹ thuật', async () => {
    vi.spyOn(conversationApi, 'getCost').mockRejectedValue(
      new ApiRequestError(404, { code: 'not_found', message: 'Chưa bật telemetry', hint: '', retryable: false }, 'nf'),
    );
    vi.spyOn(conversationApi, 'getCostTrend').mockRejectedValue(new Error('nf'));
    render(<TechnicalOperationsView />);
    expect(await screen.findByTestId('cost-error')).toHaveTextContent('Chưa bật telemetry');
  });

  it('bỏ qua cost/trend 24h cũ nếu response 7d về trước', async () => {
    const oldCost = deferred<CostResponse>();
    const currentCost = deferred<CostResponse>();
    const oldTrend = deferred<CostTrendResponse>();
    const currentTrend = deferred<CostTrendResponse>();
    vi.spyOn(conversationApi, 'getCost')
      .mockReturnValueOnce(oldCost.promise)
      .mockReturnValueOnce(currentCost.promise);
    vi.spyOn(conversationApi, 'getCostTrend')
      .mockReturnValueOnce(oldTrend.promise)
      .mockReturnValueOnce(currentTrend.promise);
    render(<TechnicalOperationsView />);

    fireEvent.click(screen.getByTestId('technical-window-7d'));
    const selectedCost = { ...cost, window: '7d', total_cost_usd: 9.99 };
    const selectedTrend = { buckets: [{ ts: '2026-08-24', series: { new_team: 0.8 } }] };
    await act(async () => {
      currentCost.resolve(selectedCost);
      currentTrend.resolve(selectedTrend);
      await Promise.all([currentCost.promise, currentTrend.promise]);
    });
    expect(screen.getByTestId('cost-total')).toHaveTextContent('$9.99');
    expect(screen.getByText('new_team')).toBeInTheDocument();

    await act(async () => {
      oldCost.resolve(cost);
      oldTrend.resolve({ buckets: [{ ts: '00:00', series: { old_team: 0.4 } }] });
      await Promise.all([oldCost.promise, oldTrend.promise]);
    });
    expect(screen.getByTestId('cost-total')).toHaveTextContent('$9.99');
    expect(screen.getByText('new_team')).toBeInTheDocument();
    expect(screen.queryByText('old_team')).not.toBeInTheDocument();
  });
});
