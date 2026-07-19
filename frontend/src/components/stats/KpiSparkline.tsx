// KpiSparkline.tsx — S16 T16-3: sparkline mini (LineChart) cho KpiCard. spark rỗng/1 điểm → không
// render (KpiCard backward: KPI cũ chưa có spark từ API → không hiện). Không trục/tooltip (mini).
import { LineChart, Line, ResponsiveContainer } from 'recharts';

export function KpiSparkline({ spark, color = 'var(--acc)' }: { spark?: number[]; color?: string }) {
  if (!Array.isArray(spark) || spark.length < 2) return null; // cần ≥2 điểm mới vẽ được đường
  const data = spark.map((v, i) => ({ i, v }));
  return (
    <div className="kpi__spark" data-testid="kpi-spark">
      <ResponsiveContainer width="100%" height={28}>
        <LineChart data={data} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
          <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
