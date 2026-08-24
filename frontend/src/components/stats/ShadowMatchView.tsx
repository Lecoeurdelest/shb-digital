// ShadowMatchView — bề mặt admin đọc ledger S18. Ca lệch được trình bày như tín hiệu
// hiệu chỉnh và drill-down qua đúng deep-link S19; không tạo đường focus/approval thứ hai.
import { useEffect, useState } from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { conversationApi } from '../../api';
import type { ShadowLane, ShadowMatchStats, ShadowMismatch } from '../../types';
import { KpiCard } from './KpiCard';
import './ChartBlock.css';
import './ShadowMatchView.css';

const PAGE_LIMIT = 50;

function formatPercent(rate: number): string {
  const safeRate = Number.isFinite(rate) ? rate : 0;
  return `${(safeRate * 100).toLocaleString('vi-VN', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`;
}

function formatDay(date: string): string {
  const [year, month, day] = date.split('-');
  return year && month && day ? `${day}/${month}/${year}` : date;
}

function formatDecisionTime(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });
}

function laneLabel(lane: ShadowLane): string {
  return lane ? lane.toUpperCase() : 'CHƯA PHÂN LANE';
}

const RECOMMENDATION_LABEL: Record<ShadowMismatch['system_recommendation'], string> = {
  'auto-eligible': 'Có thể tự động',
  'human-review': 'Cần người xem xét',
  'reject-recommended': 'Khuyến nghị không duyệt',
};

export function ShadowMatchView() {
  const [stats, setStats] = useState<ShadowMatchStats | null>(null);
  const [mismatches, setMismatches] = useState<ShadowMismatch[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    Promise.all([
      conversationApi.getShadowMatch(),
      conversationApi.listShadowMismatches({ limit: PAGE_LIMIT }),
    ])
      .then(([aggregate, page]) => {
        if (!alive) return;
        setStats(aggregate);
        setMismatches(page.items);
        setNextCursor(page.next_cursor);
        setPageError(null);
      })
      .catch(() => {
        if (alive) setError('Không tải được sổ đối chiếu shadow.');
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => { alive = false; };
  }, [reload]);

  const loadMore = () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    setPageError(null);
    conversationApi.listShadowMismatches({ limit: PAGE_LIMIT, cursor: nextCursor })
      .then((page) => {
        setMismatches((current) => {
          const known = new Set(current.map((item) => item.approval_id));
          return [...current, ...page.items.filter((item) => !known.has(item.approval_id))];
        });
        setNextCursor(page.next_cursor);
      })
      .catch(() => setPageError('Không tải được trang tín hiệu tiếp theo.'))
      .finally(() => setLoadingMore(false));
  };

  if (loading) {
    return <div className="ct__empty" role="status">Đang tải sổ đối chiếu shadow…</div>;
  }

  if (error || !stats) {
    return (
      <div className="ct__section shadow">
        <div className="ct__error" role="alert">{error ?? 'Dữ liệu đối chiếu chưa sẵn sàng.'}</div>
        <button type="button" className="ct__refresh" onClick={() => setReload((value) => value + 1)}>
          Thử tải lại
        </button>
      </div>
    );
  }

  const dailyRates = stats.by_day.map((bucket) => bucket.rate * 100);
  const trend = stats.by_day.map((bucket) => ({
    date: formatDay(bucket.date),
    rate: bucket.rate * 100,
    matched: bucket.matched,
    comparable: bucket.comparable,
  }));

  return (
    <div className="ct__section shadow" data-testid="shadow-match-view">
      <div className="ct__section-head shadow__head">
        <div>
          <div className="ct__section-title">Đối chiếu shadow</div>
          <p className="shadow__intro">
            Ca lệch là tín hiệu hiệu chỉnh để rà soát mô hình và chính sách, không phải kết luận lỗi của người quyết định.
          </p>
        </div>
      </div>

      <div className="shadow__kpis">
        <KpiCard
          label="Độ khớp tổng"
          value={formatPercent(stats.rate)}
          sub={`${stats.matched}/${stats.comparable} ca có thể đối chiếu · ${stats.total} mẫu`}
          icon="◎"
          spark={dailyRates}
        />
        {stats.by_lane.map((bucket) => (
          <KpiCard
            key={bucket.lane ?? 'none'}
            label={`Lane ${laneLabel(bucket.lane)}`}
            value={formatPercent(bucket.rate)}
            sub={`${bucket.matched}/${bucket.comparable} ca khớp · ${bucket.total} mẫu`}
            tone={bucket.lane ?? 'default'}
          />
        ))}
      </div>

      <div className="chartblock shadow__trend" data-testid="shadow-day-trend">
        <div className="chartblock__title">Độ khớp theo ngày (UTC)</div>
        {trend.length === 0 ? (
          <div className="chartblock__empty">Chưa có dữ liệu theo ngày.</div>
        ) : (
          <>
            <div className="chartblock__canvas" role="img" aria-label="Biểu đồ đường độ khớp shadow theo ngày UTC">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={trend} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--bd)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--mute)', fontSize: 10 }} />
                  <YAxis domain={[0, 100]} tick={{ fill: 'var(--mute)', fontSize: 10 }} tickFormatter={(value: number) => `${value}%`} />
                  <Tooltip
                    contentStyle={{ background: 'var(--p1)', border: '1px solid var(--bd2)', borderRadius: 8, fontSize: 11 }}
                    formatter={(value) => [`${Number(value).toLocaleString('vi-VN', { maximumFractionDigits: 1 })}%`, 'Độ khớp']}
                  />
                  <Line type="monotone" dataKey="rate" stroke="var(--acc)" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="shadow__day-facts" aria-label="Số liệu độ khớp theo ngày">
              {trend.map((point) => (
                <span key={point.date}>{point.date}: {formatPercent(point.rate / 100)} ({point.matched}/{point.comparable})</span>
              ))}
            </div>
          </>
        )}
      </div>

      <section className="shadow__mismatches" aria-labelledby="shadow-mismatch-title">
        <div className="shadow__table-head">
          <div>
            <h2 id="shadow-mismatch-title">Tín hiệu hiệu chỉnh ({mismatches.length})</h2>
            <p>Chọn một ca để mở đúng phiếu và xem đầy đủ căn cứ quyết định.</p>
          </div>
        </div>

        {mismatches.length === 0 ? (
          <div className="ct__empty" data-testid="shadow-mismatch-empty">Chưa có ca lệch trong sổ đối chiếu.</div>
        ) : (
          <div className="shadow__rows">
            <div className="shadow__row shadow__row--labels" aria-hidden="true">
              <span>Phiếu / phiên</span><span>Lane</span><span>Hệ thống</span><span>Người quyết định</span><span>Lý do</span><span>Thời điểm</span>
            </div>
            {mismatches.map((item) => (
              <a
                key={item.approval_id}
                className="shadow__row shadow__row--link"
                href={`/?tab=approvals&approval=${item.approval_id}`}
                data-testid={`shadow-mismatch-${item.approval_id}`}
                aria-label={`Mở phiếu ${item.approval_id}`}
              >
                <span className="shadow__identity"><b>{item.approval_id.slice(0, 8)}</b><small>Phiên {item.conv_id.slice(0, 8)}</small></span>
                <span className={`shadow__lane shadow__lane--${item.system_lane ?? 'none'}`}>{laneLabel(item.system_lane)}</span>
                <span>{RECOMMENDATION_LABEL[item.system_recommendation]}</span>
                <span>{item.human_decision === 'approved' ? 'Đã duyệt' : 'Không duyệt'}</span>
                <span>{item.human_reason?.trim() || 'Không ghi lý do'}</span>
                <time dateTime={item.decided_at}>{formatDecisionTime(item.decided_at)}</time>
              </a>
            ))}
          </div>
        )}

        {pageError && <div className="ct__error" role="alert">{pageError}</div>}
        {nextCursor && (
          <button type="button" className="ct__refresh shadow__more" onClick={loadMore} disabled={loadingMore}>
            {loadingMore ? 'Đang tải…' : 'Tải thêm tín hiệu'}
          </button>
        )}
      </section>
    </div>
  );
}
