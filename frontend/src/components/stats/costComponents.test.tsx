// costComponents.test.tsx — S16 T16-3: empty-state + basic render các chart wrapper (KHÔNG assert
// recharts SVG — jsdom không đo layout; test empty branch + testid + data-driven text).
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TokenBreakdownBar } from './TokenBreakdownBar';
import { DailyCostBar } from './DailyCostBar';
import { ModelDonut } from './ModelDonut';
import { CostAnomalyTable } from './CostAnomalyTable';
import { KpiSparkline } from './KpiSparkline';
import type { CostAnomaly } from '../../types';

describe('TokenBreakdownBar', () => {
  it('có data → thanh + legend 4 category', () => {
    render(<TokenBreakdownBar breakdown={{ input_tokens: 100, output_tokens: 50, cache_read_tokens: 200, cache_create_tokens: 10 }} />);
    expect(screen.getByTestId('token-seg-input_tokens')).toBeInTheDocument();
    expect(screen.getByTestId('token-legend-cache_read_tokens')).toBeInTheDocument();
  });
  it('total 0 → empty note', () => {
    render(<TokenBreakdownBar breakdown={{ input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_create_tokens: 0 }} />);
    expect(screen.getByTestId('token-breakdown-empty')).toBeInTheDocument();
  });
  it('null breakdown → empty (không crash)', () => {
    render(<TokenBreakdownBar breakdown={null} />);
    expect(screen.getByTestId('token-breakdown-empty')).toBeInTheDocument();
  });
});

describe('DailyCostBar', () => {
  it('buckets rỗng → empty note', () => {
    render(<DailyCostBar buckets={[]} />);
    expect(screen.getByTestId('daily-cost-empty')).toBeInTheDocument();
  });
  it('có buckets → render (không empty)', () => {
    render(<DailyCostBar buckets={[{ ts: '00:00', series: { credit: 0.4 } }]} />);
    expect(screen.queryByTestId('daily-cost-empty')).not.toBeInTheDocument();
    expect(screen.getByTestId('daily-cost-bar')).toBeInTheDocument();
  });
});

describe('ModelDonut', () => {
  it('by_model rỗng → empty note', () => {
    render(<ModelDonut byModel={[]} />);
    expect(screen.getByTestId('model-donut-empty')).toBeInTheDocument();
  });
  it('có model → total center + legend + nhãn ước tính', () => {
    render(<ModelDonut byModel={[{ model: 'glm-4.6', cost_usd: 3, turns: 10, total_tokens: 1000 }]} estimated />);
    expect(screen.getByTestId('donut-total')).toHaveTextContent('$3.00');
    expect(screen.getByText(/ước tính/)).toBeInTheDocument();
    expect(screen.getByTestId('donut-legend-glm-4.6')).toBeInTheDocument();
  });
});

describe('CostAnomalyTable', () => {
  const anoms: CostAnomaly[] = [
    { conv_id: 'hi', title: 'Cao', cost_usd: 0.9, mean: 0.2, stddev: 0.18, z_score: 4.0 },
    { conv_id: 'mid', title: 'Vừa', cost_usd: 0.5, mean: 0.2, stddev: 0.18, z_score: 2.1 },
  ];
  it('z≥2 mặc định → cả 2; nút z≥3 → chỉ z cao', () => {
    render(<CostAnomalyTable anomalies={anoms} />);
    expect(screen.getByTestId('anom-row-hi')).toBeInTheDocument();
    expect(screen.getByTestId('anom-row-mid')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('anom-z-3'));
    expect(screen.getByTestId('anom-row-hi')).toBeInTheDocument();
    expect(screen.queryByTestId('anom-row-mid')).not.toBeInTheDocument(); // z=2.1 loại
  });
  it('rỗng → empty note', () => {
    render(<CostAnomalyTable anomalies={[]} />);
    expect(screen.getByTestId('anom-empty')).toBeInTheDocument();
  });
  it('row-click → onOpenAudit(conv_id)', () => {
    const onOpenAudit = vi.fn();
    render(<CostAnomalyTable anomalies={anoms} onOpenAudit={onOpenAudit} />);
    fireEvent.click(screen.getByTestId('anom-row-hi'));
    expect(onOpenAudit).toHaveBeenCalledWith('hi');
  });
});

describe('KpiSparkline', () => {
  it('spark <2 điểm → không render (backward KPI cũ)', () => {
    const { container } = render(<KpiSparkline spark={[1]} />);
    expect(container.firstChild).toBeNull();
  });
  it('spark undefined → không render', () => {
    const { container } = render(<KpiSparkline />);
    expect(container.firstChild).toBeNull();
  });
  it('spark ≥2 → render wrapper', () => {
    render(<KpiSparkline spark={[1, 2, 3]} />);
    expect(screen.getByTestId('kpi-spark')).toBeInTheDocument();
  });
});
