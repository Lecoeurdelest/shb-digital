// StatsOverview.tsx — tab "Tổng quan" ControlTower. GIỮ 7 KPI nghiệp vụ (S13) + THÊM cụm "Chi phí
// & vận hành AI" (S16 T16-3, recharts): TokenBreakdownBar · DailyCostBar · ModelDonut · CostAnomalyTable.
// Segmented window 24h|7d|30d (nâng 2-nút cũ). Poll 30s dừng tab ẩn. KpiCard +spark.
// ĐỘC LẬP DEGRADE (advisor): cost cluster fetch RIÊNG error/loading — BE T16-2 chưa có (404) thì
// 7 KPI vẫn render, chỉ block cost hiện note. Fetch-fail im đẹp (throwOnError-mềm như stats cũ).
import { useCallback, useEffect, useState } from 'react';
import { conversationApi } from '../../api';
import { ApiRequestError } from '../../api/client';
import type { CostResponse, CostTrendResponse, StatsResponse, StatsWindow } from '../../types';
import { KpiCard } from './KpiCard';
import { TokenBreakdownBar } from './TokenBreakdownBar';
import { DailyCostBar } from './DailyCostBar';
import { ModelDonut } from './ModelDonut';
import { CostAnomalyTable } from './CostAnomalyTable';
import './StatsOverview.css';

const POLL_MS = 30000;
const WINDOWS: { key: StatsWindow; label: string }[] = [
  { key: '24h', label: '24 giờ' },
  { key: '7d', label: '7 ngày' },
  { key: '30d', label: '30 ngày' },
];

function errMsg(e: unknown, fallback: string): string {
  return e instanceof ApiRequestError ? e.body?.message ?? fallback : fallback;
}

export function StatsOverview({ onOpenAudit }: { onOpenAudit?: (convId: string) => void }) {
  const [window, setWindow] = useState<StatsWindow>('24h');
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  // cost cluster — state RIÊNG (độc lập với 7 KPI: BE chưa build → cost lỗi nhưng KPI vẫn hiện).
  const [cost, setCost] = useState<CostResponse | null>(null);
  const [trend, setTrend] = useState<CostTrendResponse | null>(null);
  const [costError, setCostError] = useState<string | null>(null);

  const load = useCallback((w: StatsWindow) => {
    conversationApi.getStats(w)
      .then((s) => { setStats(s); setError(null); })
      .catch((e: unknown) => setError(errMsg(e, 'Lỗi tải thống kê')));
    // cost + trend fetch RIÊNG (không để 1 fail chặn KPI). 24h → bucket hour; 7d/30d → day.
    const bucket = w === '24h' ? 'hour' : 'day';
    conversationApi.getCost(w)
      .then((c) => { setCost(c); setCostError(null); })
      .catch((e: unknown) => { setCost(null); setCostError(errMsg(e, 'Chưa có dữ liệu chi phí (đang chờ backend).')); });
    conversationApi.getCostTrend(w, bucket, 'role')
      .then((t) => setTrend(t))
      .catch(() => setTrend(null)); // trend lỗi → DailyCostBar tự hiện empty
  }, []);

  useEffect(() => {
    let alive = true;
    let timer = 0;
    const tick = () => {
      if (document.visibilityState === 'hidden') { schedule(); return; }
      if (alive) load(window);
      schedule();
    };
    const schedule = () => { if (alive) timer = globalThis.setTimeout(tick, POLL_MS); };
    load(window);
    timer = globalThis.setTimeout(tick, POLL_MS);
    const onVisible = () => { if (document.visibilityState === 'visible' && alive) { globalThis.clearTimeout(timer); load(window); schedule(); } };
    document.addEventListener('visibilitychange', onVisible);
    return () => { alive = false; globalThis.clearTimeout(timer); document.removeEventListener('visibilitychange', onVisible); };
  }, [window, load]);

  const a = stats?.approvals;
  const asmt = stats?.assessments;
  const conv = stats?.conversations;
  const d = stats?.delta;
  const sp = stats?.sparks;

  return (
    <div className="ct__section stats">
      <div className="ct__section-head">
        <span className="ct__section-title">Tổng quan nghiệp vụ</span>
        <div className="stats__window" role="tablist" aria-label="Khoảng thời gian">
          {WINDOWS.map((w) => (
            <button
              key={w.key}
              type="button"
              className={`stats__window-btn${window === w.key ? ' stats__window-btn--active' : ''}`}
              onClick={() => setWindow(w.key)}
              aria-selected={window === w.key}
              data-testid={`window-${w.key}`}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="ct__error">{error}</div>}

      <div className="stats__grid">
        <KpiCard label="Phiếu đã duyệt" value={a?.approved ?? '—'} delta={d?.approvals_total} icon="✅"
          sub={a ? `trong đó AUTO: ${a.auto}` : undefined} spark={sp?.approved} />
        <KpiCard label="Từ chối" value={a?.rejected ?? '—'} icon="✗" />
        <KpiCard label="Đang chờ" value={a?.pending ?? '—'} icon="⏳"
          tone={a && a.pending > 0 ? 'warn' : 'default'} />
        <KpiCard label="Hồ sơ Green" value={asmt?.green ?? '—'} delta={d?.assessments_total} tone="green" icon="●"
          sub="thẩm định đạt" spark={sp?.green} />
        <KpiCard label="Hồ sơ Yellow" value={asmt?.yellow ?? '—'} tone="yellow" icon="●" />
        <KpiCard label="Hồ sơ Red" value={asmt?.red ?? '—'} tone="red" icon="●" />
        <KpiCard label="Ca tư vấn" value={conv?.total ?? '—'} icon="💬"
          sub={conv ? `đang chạy: ${conv.active}` : undefined} spark={sp?.total} />
      </div>

      {/* ── Cụm CHI PHÍ & VẬN HÀNH AI (S16 T16-3) — độc lập degrade ── */}
      <div className="stats__cost-head">
        <span className="ct__section-title">Chi phí &amp; vận hành AI</span>
        {cost && (
          <span className="stats__cost-total" data-testid="cost-total">
            {cost.cost_estimated && <span className="stats__est">ước tính</span>}
            tổng {formatUsd(cost.total_cost_usd)}
            {cost.delta && <DeltaPct pct={cost.delta.total_cost_pct} />}
          </span>
        )}
      </div>
      {costError ? (
        <div className="ct__empty" data-testid="cost-error">{costError}</div>
      ) : (
        <>
          <TokenBreakdownBar breakdown={cost?.breakdown} />
          <div className="stats__cost-grid">
            <DailyCostBar buckets={trend?.buckets ?? []} />
            <ModelDonut byModel={cost?.by_model ?? []} estimated={cost?.cost_estimated} />
          </div>
          <CostAnomalyTable anomalies={cost?.anomalies ?? []} onOpenAudit={onOpenAudit} />
        </>
      )}

      <div className="stats__footer">Bản demo: admin gộp vai giám sát nghiệp vụ + kỹ thuật. Cost provider ngoài là ước tính; token là số thật.</div>
    </div>
  );
}

function formatUsd(n: number): string {
  return Number.isFinite(n) ? `$${n.toFixed(2)}` : '$0';
}

function DeltaPct({ pct }: { pct: number }) {
  if (pct === 0) return <span className="stats__delta stats__delta--flat">→ 0%</span>;
  const up = pct > 0;
  return <span className={`stats__delta stats__delta--${up ? 'up' : 'down'}`}>{up ? '↑' : '↓'} {Math.abs(pct).toFixed(1)}%</span>;
}
