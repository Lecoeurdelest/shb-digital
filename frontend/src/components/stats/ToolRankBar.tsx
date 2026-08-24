// ToolRankBar.tsx — S16 T16-4: tool-call ranked bar trong ca (đếm theo tool từ trace conv, sort
// giảm dần). CSS flex (không recharts — bar ngang không trục, nhẹ+test-được). trace rỗng → empty.
import { rankToolCalls } from './traceMetrics';
import type { TraceItem } from '../../types';
import './ToolRankBar.css';

export function ToolRankBar({ trace, max = 8 }: { trace: TraceItem[]; max?: number }) {
  const ranked = rankToolCalls(trace);
  const top = ranked.slice(0, max);
  const peak = top[0]?.count ?? 0;

  return (
    <div className="trb" data-testid="tool-rank-bar">
      <div className="trb__title">Bước xử lý được dùng nhiều nhất</div>
      {top.length === 0 ? (
        <div className="trb__empty" data-testid="tool-rank-empty">Chưa có bước xử lý nào.</div>
      ) : (
        <div className="trb__rows">
          {top.map((t) => (
            <div key={t.tool} className="trb__row" data-testid={`tool-rank-${t.tool}`}>
              <span className="trb__tool">{businessStepLabel(t.tool)}</span>
              <div className="trb__track">
                <div className="trb__fill" style={{ width: `${peak > 0 ? (t.count / peak) * 100 : 0}%` }} />
              </div>
              <span className="trb__count">{t.count}</span>
            </div>
          ))}
          {ranked.length > max && <div className="trb__more">… và {ranked.length - max} bước khác</div>}
        </div>
      )}
    </div>
  );
}

function businessStepLabel(tool: string): string {
  const labels: Record<string, string> = {
    credit_assess: 'Đánh giá tín dụng',
    cust_get: 'Tra cứu khách hàng',
    disburse: 'Chuẩn bị giải ngân',
    present: 'Lập bản trình bày',
    calc: 'Tính toán chỉ tiêu',
  };
  return labels[tool] ?? 'Bước xử lý';
}
