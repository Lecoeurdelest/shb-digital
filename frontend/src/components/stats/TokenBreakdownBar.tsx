// TokenBreakdownBar.tsx — S16 T16-3: stacked horizontal 1 thanh, 4 category CỐ ĐỊNH màu+vị trí
// (input/output/cache_read/cache_create). Component CHUNG (T16-4 tái dùng). CSS flex (không cần
// recharts cho 1 thanh — nhẹ + chắc). tổng 0 → thanh rỗng + note. Legend dưới với abs+%.
import { tokenSegments, fmtTokens } from './costTransforms';
import type { CostBreakdown } from '../../types';
import './TokenBreakdownBar.css';

export function TokenBreakdownBar({ breakdown }: { breakdown: CostBreakdown | null | undefined }) {
  const { segments, total } = tokenSegments(breakdown);

  return (
    <div className="tbb" data-testid="token-breakdown">
      <div className="tbb__head">
        <span className="tbb__title">Token theo loại</span>
        <span className="tbb__total">{fmtTokens(total)} token</span>
      </div>
      {total === 0 ? (
        <div className="tbb__empty" data-testid="token-breakdown-empty">Chưa có dữ liệu token.</div>
      ) : (
        <>
          <div className="tbb__bar" role="img" aria-label="Phân bố token theo loại">
            {segments.filter((s) => s.value > 0).map((s) => (
              <div
                key={s.key}
                className="tbb__seg"
                style={{ width: `${s.pct}%`, background: s.color }}
                title={`${s.label}: ${fmtTokens(s.value)} (${s.pct.toFixed(1)}%)`}
                data-testid={`token-seg-${s.key}`}
              />
            ))}
          </div>
          <div className="tbb__legend">
            {segments.map((s) => (
              <div key={s.key} className="tbb__legend-item" data-testid={`token-legend-${s.key}`}>
                <span className="tbb__dot" style={{ background: s.color }} />
                <span className="tbb__legend-label">{s.label}</span>
                <span className="tbb__legend-val">{fmtTokens(s.value)} · {s.pct.toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
