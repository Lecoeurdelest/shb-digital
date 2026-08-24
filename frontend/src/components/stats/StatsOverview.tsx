// StatsOverview.tsx — tổng quan dành cho quản lý nghiệp vụ. Chỉ đọc /stats để lần mở mặc định
// không kéo telemetry kỹ thuật; cost/token/model được mount riêng khi vào TechnicalOperationsView.
import { useCallback, useEffect, useRef, useState } from 'react';
import { conversationApi } from '../../api';
import { ApiRequestError } from '../../api/client';
import type { StatsResponse, StatsWindow } from '../../types';
import { KpiCard } from './KpiCard';
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

function pct(part: number, total: number): string {
  if (total <= 0) return '0%';
  return `${Math.round((part / total) * 100)}%`;
}

function num(value: number | undefined): number {
  return value ?? 0;
}

export function StatsOverview() {
  const [window, setWindow] = useState<StatsWindow>('24h');
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestGeneration = useRef(0);

  const load = useCallback((w: StatsWindow) => {
    const generation = ++requestGeneration.current;
    conversationApi.getStats(w)
      .then((s) => {
        if (generation !== requestGeneration.current) return;
        setStats(s);
        setError(null);
      })
      .catch((e: unknown) => {
        if (generation === requestGeneration.current) setError(errMsg(e, 'Lỗi tải thống kê'));
      });
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
    return () => {
      alive = false;
      requestGeneration.current += 1;
      globalThis.clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [window, load]);

  const a = stats?.approvals;
  const asmt = stats?.assessments;
  const conv = stats?.conversations;
  const d = stats?.delta;
  const sp = stats?.sparks;
  const approved = num(a?.approved);
  const rejected = num(a?.rejected);
  const pending = num(a?.pending);
  const auto = num(a?.auto);
  const green = num(asmt?.green);
  const yellow = num(asmt?.yellow);
  const red = num(asmt?.red);
  const totalDecisions = approved + rejected;
  const totalApprovalWork = totalDecisions + pending;
  const totalAssessments = green + yellow + red;
  const active = num(conv?.active);
  const totalConversations = num(conv?.total);

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
        <KpiCard label="Phiên xử lý" value={conv?.total ?? '—'} icon="💬"
          sub={conv ? `đang chạy: ${conv.active}` : undefined} spark={sp?.conversations} />
      </div>

      <div className="stats__insights" data-testid="stats-insights">
        <section className="stats__panel stats__panel--decision">
          <div className="stats__panel-head">
            <span className="stats__panel-title">Luồng quyết định</span>
            <span className="stats__panel-value">{totalApprovalWork}</span>
          </div>
          <div className="stats__bar" aria-label="Phân bổ phiếu">
            <span className="stats__bar-seg stats__bar-seg--pass" style={{ width: pct(approved, totalApprovalWork) }} />
            <span className="stats__bar-seg stats__bar-seg--fail" style={{ width: pct(rejected, totalApprovalWork) }} />
            <span className="stats__bar-seg stats__bar-seg--warn" style={{ width: pct(pending, totalApprovalWork) }} />
          </div>
          <div className="stats__rows">
            <MetricRow label="Đã duyệt" value={approved} meta={pct(approved, totalApprovalWork)} tone="pass" />
            <MetricRow label="Từ chối" value={rejected} meta={pct(rejected, totalApprovalWork)} tone="fail" />
            <MetricRow label="Đang chờ" value={pending} meta={pending > 0 ? 'cần xử lý' : 'sạch hàng chờ'} tone={pending > 0 ? 'warn' : 'default'} />
            <MetricRow label="Tự động" value={auto} meta={`${pct(auto, approved)} phiếu duyệt`} />
          </div>
        </section>

        <section className="stats__panel stats__panel--lane">
          <div className="stats__panel-head">
            <span className="stats__panel-title">Chất lượng hồ sơ</span>
            <span className="stats__panel-value">{totalAssessments}</span>
          </div>
          <div className="stats__bar" aria-label="Phân bổ lane hồ sơ">
            <span className="stats__bar-seg stats__bar-seg--pass" style={{ width: pct(green, totalAssessments) }} />
            <span className="stats__bar-seg stats__bar-seg--warn" style={{ width: pct(yellow, totalAssessments) }} />
            <span className="stats__bar-seg stats__bar-seg--fail" style={{ width: pct(red, totalAssessments) }} />
          </div>
          <div className="stats__rows">
            <MetricRow label="Đạt sơ bộ" value={green} meta={pct(green, totalAssessments)} tone="pass" />
            <MetricRow label="Cần bổ sung" value={yellow} meta={pct(yellow, totalAssessments)} tone="warn" />
            <MetricRow label="Rủi ro cao" value={red} meta={pct(red, totalAssessments)} tone="fail" />
            <MetricRow label="Cần rà soát" value={yellow + red} meta={`${pct(yellow + red, totalAssessments)} hồ sơ`} />
          </div>
        </section>

        <section className="stats__panel stats__panel--workload">
          <div className="stats__panel-head">
            <span className="stats__panel-title">Tải xử lý</span>
            <span className="stats__panel-value">{active}/{totalConversations}</span>
          </div>
          <div className="stats__workload-grid">
            <div>
              <span className="stats__workload-num">{active}</span>
              <span className="stats__workload-label">đang chạy</span>
            </div>
            <div>
              <span className="stats__workload-num">{pending + active}</span>
              <span className="stats__workload-label">đang cần theo dõi</span>
            </div>
            <div>
              <span className="stats__workload-num">{totalDecisions}</span>
              <span className="stats__workload-label">đã có quyết định</span>
            </div>
          </div>
          <div className="stats__footer">
            Pending là trạng thái hiện tại; các số còn lại theo khoảng thời gian đang chọn.
          </div>
        </section>
      </div>

    </div>
  );
}

function MetricRow({
  label,
  value,
  meta,
  tone = 'default',
}: {
  label: string;
  value: number;
  meta: string;
  tone?: 'default' | 'pass' | 'warn' | 'fail';
}) {
  return (
    <div className="stats__metric-row">
      <span className={`stats__metric-dot stats__metric-dot--${tone}`} />
      <span className="stats__metric-label">{label}</span>
      <span className="stats__metric-value">{value}</span>
      <span className="stats__metric-meta">{meta}</span>
    </div>
  );
}
