// ModelDonut.tsx — S16 T16-3: donut by-model (PieChart innerRadius) + center label tổng $ +
// legend %. Nhãn kèm "(ước tính)" vì cost provider ngoài không tin (contract). by_model rỗng → empty.
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { modelSlices, fmtUsd } from './costTransforms';
import type { CostByModel } from '../../types';
import './ChartBlock.css';

const SLICE_COLORS = ['#6ea8fe', '#d97757', '#5cc98b', '#c99b5c', '#a78bfa', '#e06f95'];

export function ModelDonut({ byModel, estimated }: { byModel: CostByModel[]; estimated?: boolean }) {
  const { slices, total } = modelSlices(byModel);

  return (
    <div className="chartblock" data-testid="model-donut">
      <div className="chartblock__title">
        Chi phí theo model {estimated && <span className="chartblock__est" title="Cost provider ngoài SDK không tách chính xác">(ước tính)</span>}
      </div>
      {slices.length === 0 ? (
        <div className="chartblock__empty" data-testid="model-donut-empty">Chưa có dữ liệu chi phí theo model.</div>
      ) : (
        <div className="chartblock__canvas chartblock__canvas--donut">
          <div className="chartblock__donut-wrap">
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={slices} dataKey="cost_usd" nameKey="model" innerRadius={52} outerRadius={78} paddingAngle={2} stroke="none">
                  {slices.map((s, i) => (
                    <Cell key={s.model} fill={SLICE_COLORS[i % SLICE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: 'var(--p1)', border: '1px solid var(--bd2)', borderRadius: 8, fontSize: 11 }}
                  formatter={(v, name) => [fmtUsd(Number(v)), String(name)]}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="chartblock__donut-center" data-testid="donut-total">
              <span className="chartblock__donut-total">{fmtUsd(total)}</span>
              <span className="chartblock__donut-label">tổng</span>
            </div>
          </div>
          <div className="chartblock__legend chartblock__legend--col">
            {slices.map((s, i) => (
              <span key={s.model} className="chartblock__legend-item" data-testid={`donut-legend-${s.model}`}>
                <span className="chartblock__dot" style={{ background: SLICE_COLORS[i % SLICE_COLORS.length] }} />
                <span className="chartblock__legend-name">{s.model}</span>
                <span className="chartblock__legend-pct">{s.pct.toFixed(0)}%</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
