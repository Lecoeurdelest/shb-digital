// CostAnomalyTable.tsx — S16 T16-3: bảng anomaly z_score. Filter nút z≥2 / z≥3. border-left đỏ.
// row-click → onOpenAudit(conv_id) (ControlTower nhảy tab audit + seed filter mã ca — không route mới).
// anomalies rỗng (hoặc lọc hết) → empty note. z càng cao càng bất thường (đỏ đậm hơn).
import { useState } from 'react';
import { filterAnomalies, fmtUsd } from './costTransforms';
import type { CostAnomaly } from '../../types';
import './CostAnomalyTable.css';

export function CostAnomalyTable({ anomalies, onOpenAudit }: { anomalies: CostAnomaly[]; onOpenAudit?: (convId: string) => void }) {
  const [minZ, setMinZ] = useState<2 | 3>(2);
  const rows = filterAnomalies(anomalies ?? [], minZ);

  return (
    <div className="anom" data-testid="cost-anomaly-table">
      <div className="anom__head">
        <span className="anom__title">Ca chi phí bất thường (z-score)</span>
        <div className="anom__filter" role="tablist" aria-label="Ngưỡng z-score">
          {([2, 3] as const).map((z) => (
            <button
              key={z}
              type="button"
              className={`anom__filter-btn${minZ === z ? ' anom__filter-btn--active' : ''}`}
              onClick={() => setMinZ(z)}
              aria-selected={minZ === z}
              data-testid={`anom-z-${z}`}
            >
              z ≥ {z}
            </button>
          ))}
        </div>
      </div>
      {rows.length === 0 ? (
        <div className="anom__empty" data-testid="anom-empty">Không có ca bất thường (z ≥ {minZ}).</div>
      ) : (
        <div className="anom__rows">
          {rows.map((a) => (
            <button
              key={a.conv_id}
              type="button"
              className="anom__row"
              onClick={() => onOpenAudit?.(a.conv_id)}
              data-testid={`anom-row-${a.conv_id}`}
              title="Mở nhật ký tool của ca này"
            >
              <span className="anom__row-main">
                <span className="anom__row-title">{a.title || a.conv_id}</span>
                <span className="anom__row-meta">
                  chi phí {fmtUsd(a.cost_usd)} · TB {fmtUsd(a.mean)} · z={a.z_score.toFixed(1)}
                </span>
              </span>
              <span className="anom__z" data-testid={`anom-z-badge-${a.conv_id}`}>z {a.z_score.toFixed(1)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
