// TechnicalOperationsView.tsx — telemetry chỉ được tải khi tab kỹ thuật được mount. Tách khỏi
// tổng quan nghiệp vụ để quản lý không vô tình tải/xem model, token và chi phí vận hành.
import { useCallback, useEffect, useRef, useState } from 'react';
import { conversationApi } from '../../api';
import { ApiRequestError } from '../../api/client';
import type { CostResponse, CostTrendResponse, StatsWindow } from '../../types';
import { CostAnomalyTable } from './CostAnomalyTable';
import { DailyCostBar } from './DailyCostBar';
import { ModelDonut } from './ModelDonut';
import { TokenBreakdownBar } from './TokenBreakdownBar';
import './StatsOverview.css';

const POLL_MS = 30000;
const WINDOWS: { key: StatsWindow; label: string }[] = [
  { key: '24h', label: '24 giờ' },
  { key: '7d', label: '7 ngày' },
  { key: '30d', label: '30 ngày' },
];

function errMsg(error: unknown): string {
  const fallback = 'Chưa có dữ liệu vận hành kỹ thuật.';
  return error instanceof ApiRequestError ? error.body?.message ?? fallback : fallback;
}

export interface TechnicalOperationsViewProps {
  onOpenAudit?: (convId: string) => void;
}

export function TechnicalOperationsView({ onOpenAudit }: TechnicalOperationsViewProps) {
  const [window, setWindow] = useState<StatsWindow>('24h');
  const [cost, setCost] = useState<CostResponse | null>(null);
  const [trend, setTrend] = useState<CostTrendResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestGeneration = useRef(0);

  const load = useCallback((selectedWindow: StatsWindow) => {
    const generation = ++requestGeneration.current;
    const bucket = selectedWindow === '24h' ? 'hour' : 'day';
    conversationApi.getCost(selectedWindow)
      .then((next) => {
        if (generation !== requestGeneration.current) return;
        setCost(next);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (generation !== requestGeneration.current) return;
        setCost(null);
        setError(errMsg(reason));
      });
    conversationApi.getCostTrend(selectedWindow, bucket, 'role')
      .then((next) => {
        if (generation === requestGeneration.current) setTrend(next);
      })
      .catch(() => {
        if (generation === requestGeneration.current) setTrend(null);
      });
  }, []);

  useEffect(() => {
    let alive = true;
    let timer = 0;
    const schedule = () => { if (alive) timer = globalThis.setTimeout(tick, POLL_MS); };
    const tick = () => {
      if (document.visibilityState !== 'hidden' && alive) load(window);
      schedule();
    };
    const onVisible = () => {
      if (document.visibilityState === 'visible' && alive) {
        globalThis.clearTimeout(timer);
        load(window);
        schedule();
      }
    };

    load(window);
    timer = globalThis.setTimeout(tick, POLL_MS);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      alive = false;
      requestGeneration.current += 1;
      globalThis.clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [load, window]);

  return (
    <div className="ct__section stats" data-testid="technical-operations">
      <div className="ct__section-head">
        <span className="ct__section-title">Vận hành kỹ thuật</span>
        <div className="stats__window" role="tablist" aria-label="Khoảng thời gian kỹ thuật">
          {WINDOWS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`stats__window-btn${window === item.key ? ' stats__window-btn--active' : ''}`}
              onClick={() => setWindow(item.key)}
              aria-selected={window === item.key}
              data-testid={`technical-window-${item.key}`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="stats__cost-head">
        <span className="ct__section-title">Chi phí, token và model</span>
        {cost ? (
          <span className="stats__cost-total" data-testid="cost-total">
            {cost.cost_estimated ? <span className="stats__est">ước tính</span> : null}
            tổng {formatUsd(cost.total_cost_usd)}
            <DeltaPct pct={cost.delta.total_cost_pct} />
          </span>
        ) : null}
      </div>

      {error ? (
        <div className="ct__empty" data-testid="cost-error">{error}</div>
      ) : (
        <>
          <TokenBreakdownBar breakdown={cost?.breakdown} />
          <div className="stats__cost-grid">
            <DailyCostBar buckets={trend?.buckets ?? []} />
            <ModelDonut byModel={cost?.by_model ?? []} estimated={cost?.cost_estimated} />
          </div>
          <div className="ct__note" data-testid="latency-note">
            Độ trễ xử lý: API hiện chưa cung cấp chuỗi tổng hợp; xem theo từng phiên xử lý trong nhật ký kỹ thuật.
          </div>
          <CostAnomalyTable anomalies={cost?.anomalies ?? []} onOpenAudit={onOpenAudit} />
        </>
      )}
    </div>
  );
}

function formatUsd(value: number): string {
  return Number.isFinite(value) ? `$${value.toFixed(2)}` : '$0';
}

function DeltaPct({ pct }: { pct: number }) {
  if (pct === 0) return <span className="stats__delta stats__delta--flat">→ 0%</span>;
  const up = pct > 0;
  return (
    <span className={`stats__delta stats__delta--${up ? 'up' : 'down'}`}>
      {up ? '↑' : '↓'} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}
