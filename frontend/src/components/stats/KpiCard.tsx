// KpiCard.tsx — thẻ KPI tab Tổng quan (S13 T13-2). Hình dạng THAM KHẢO shopquantum-admin (label
// uppercase + value mono lớn + delta ↑↓), VIẾT LẠI theo stack này (CSS class + var token → theme-aware).
// S16 T16-3: spark OPTIONAL → sparkline mini (KpiSparkline). KPI cũ chưa có spark từ API → không
// render (backward, KpiCard hiện y như trước).
import { KpiSparkline } from './KpiSparkline';
import './KpiCard.css';

interface Props {
  label: string;
  value: string | number;
  delta?: number | null; // chênh so kỳ trước (số tuyệt đối — stats trả delta count, không %)
  sub?: string; // dòng phụ (vd "trong đó AUTO: 7")
  tone?: 'default' | 'warn' | 'green' | 'yellow' | 'red'; // nổi màu (Đang chờ >0 → warn; lane 3 màu)
  icon?: string;
  spark?: number[]; // S16: chuỗi 24-bucket → sparkline mini (thiếu → không vẽ)
}

function DeltaBadge({ delta }: { delta: number }) {
  if (delta === 0) return <span className="kpi__delta kpi__delta--flat">→ 0</span>;
  const up = delta > 0;
  return (
    <span className={`kpi__delta kpi__delta--${up ? 'up' : 'down'}`}>
      {up ? '↑' : '↓'} {Math.abs(delta)}
    </span>
  );
}

export function KpiCard({ label, value, delta, sub, tone = 'default', icon, spark }: Props) {
  return (
    <div className={`kpi kpi--${tone}`} data-testid={`kpi-${label}`}>
      <div className="kpi__label">
        {icon && <span className="kpi__icon" aria-hidden="true">{icon}</span>}
        {label}
      </div>
      <div className="kpi__value-row">
        <span className="kpi__value">{value}</span>
        {delta != null && <DeltaBadge delta={delta} />}
      </div>
      {sub && <div className="kpi__sub">{sub}</div>}
      <KpiSparkline spark={spark} />
    </div>
  );
}
