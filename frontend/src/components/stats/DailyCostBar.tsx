// DailyCostBar.tsx — S16 T16-3: BarChart stacked theo by_role qua cost-trend. bucket day (7d/30d)
// hoặc hour (24h). recharts ResponsiveContainer + fixed height (0px = blank nếu thiếu). Pivot
// long→wide qua pivotTrend. Màu series deterministic theo index. buckets rỗng → empty note.
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { pivotTrend, fmtUsd } from './costTransforms';
import type { CostTrendBucket } from '../../types';
import './ChartBlock.css';

// palette series (role/model) — cố định theo index, hoà với token màu (theme-neutral, đủ tương phản 2 theme).
const SERIES_COLORS = ['#6ea8fe', '#d97757', '#5cc98b', '#c99b5c', '#a78bfa', '#e06f95'];

export function DailyCostBar({ buckets }: { buckets: CostTrendBucket[] }) {
  const { rows, names } = pivotTrend(buckets);

  return (
    <div className="chartblock" data-testid="daily-cost-bar">
      <div className="chartblock__title">Chi phí theo thời gian (stacked theo phòng ban)</div>
      {rows.length === 0 ? (
        <div className="chartblock__empty" data-testid="daily-cost-empty">Chưa có dữ liệu chi phí theo thời gian.</div>
      ) : (
        <div className="chartblock__canvas">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 4, left: -8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--bd)" />
              <XAxis dataKey="ts" tick={{ fill: 'var(--mute)', fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fill: 'var(--mute)', fontSize: 10 }} tickFormatter={(v: number) => fmtUsd(v)} width={48} />
              <Tooltip
                contentStyle={{ background: 'var(--p1)', border: '1px solid var(--bd2)', borderRadius: 8, fontSize: 11 }}
                labelStyle={{ color: 'var(--tx)' }}
                formatter={(v, name) => [fmtUsd(Number(v)), String(name)]}
              />
              {names.map((name, i) => (
                <Bar key={name} dataKey={name} stackId="cost" fill={SERIES_COLORS[i % SERIES_COLORS.length]} radius={i === names.length - 1 ? [3, 3, 0, 0] : undefined} />
              ))}
            </BarChart>
          </ResponsiveContainer>
          <div className="chartblock__legend">
            {names.map((name, i) => (
              <span key={name} className="chartblock__legend-item">
                <span className="chartblock__dot" style={{ background: SERIES_COLORS[i % SERIES_COLORS.length] }} />
                {name}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
