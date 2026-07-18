// StatsOverview.tsx — tab "Tổng quan" ControlTower (S13 T13-2, tab đầu default). KpiCard grid từ
// GET /api/stats. Window today|7d switch (query lại). Poll 30s khi tab mở (dừng tab ẩn — pattern
// useApprovalBadge). Theme-aware (KpiCard dùng var token). Spark bỏ (stats không series).
import { useCallback, useEffect, useState } from 'react';
import { conversationApi } from '../../api';
import { ApiRequestError } from '../../api/client';
import type { StatsResponse } from '../../types';
import { KpiCard } from './KpiCard';
import './StatsOverview.css';

type Window = 'today' | '7d';
const POLL_MS = 30000;

export function StatsOverview() {
  const [window, setWindow] = useState<Window>('today');
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((w: Window) => {
    conversationApi
      .getStats(w)
      .then((s) => { setStats(s); setError(null); })
      .catch((e: unknown) => setError(e instanceof ApiRequestError ? e.body?.message ?? 'Lỗi tải thống kê' : 'Lỗi tải thống kê'));
  }, []);

  // load khi đổi window + poll 30s (dừng tab ẩn — đỡ spam server)
  useEffect(() => {
    let alive = true;
    let timer = 0;
    const tick = () => {
      if (document.visibilityState === 'hidden') { schedule(); return; }
      if (alive) load(window);
      schedule();
    };
    const schedule = () => { if (alive) timer = globalThis.setTimeout(tick, POLL_MS); };
    load(window); // ngay
    timer = globalThis.setTimeout(tick, POLL_MS);
    const onVisible = () => { if (document.visibilityState === 'visible' && alive) { globalThis.clearTimeout(timer); load(window); schedule(); } };
    document.addEventListener('visibilitychange', onVisible);
    return () => { alive = false; globalThis.clearTimeout(timer); document.removeEventListener('visibilitychange', onVisible); };
  }, [window, load]);

  const a = stats?.approvals;
  const asmt = stats?.assessments;
  const conv = stats?.conversations;
  const d = stats?.delta;

  return (
    <div className="ct__section stats">
      <div className="ct__section-head">
        <span className="ct__section-title">Tổng quan nghiệp vụ</span>
        <div className="stats__window" role="tablist" aria-label="Khoảng thời gian">
          {(['today', '7d'] as Window[]).map((w) => (
            <button
              key={w}
              type="button"
              className={`stats__window-btn${window === w ? ' stats__window-btn--active' : ''}`}
              onClick={() => setWindow(w)}
              aria-selected={window === w}
              data-testid={`window-${w}`}
            >
              {w === 'today' ? 'Hôm nay' : '7 ngày'}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="ct__error">{error}</div>}

      <div className="stats__grid">
        <KpiCard label="Phiếu đã duyệt" value={a?.approved ?? '—'} delta={d?.approvals_total} icon="✅"
          sub={a ? `trong đó AUTO: ${a.auto}` : undefined} />
        <KpiCard label="Từ chối" value={a?.rejected ?? '—'} icon="✗" />
        <KpiCard label="Đang chờ" value={a?.pending ?? '—'} icon="⏳"
          tone={a && a.pending > 0 ? 'warn' : 'default'} />
        <KpiCard label="Hồ sơ Green" value={asmt?.green ?? '—'} delta={d?.assessments_total} tone="green" icon="●"
          sub="thẩm định đạt" />
        <KpiCard label="Hồ sơ Yellow" value={asmt?.yellow ?? '—'} tone="yellow" icon="●" />
        <KpiCard label="Hồ sơ Red" value={asmt?.red ?? '—'} tone="red" icon="●" />
        <KpiCard label="Ca tư vấn" value={conv?.total ?? '—'} icon="💬"
          sub={conv ? `đang chạy: ${conv.active}` : undefined} />
      </div>

      <div className="stats__footer">Bản demo: admin gộp vai giám sát nghiệp vụ + kỹ thuật.</div>
    </div>
  );
}
