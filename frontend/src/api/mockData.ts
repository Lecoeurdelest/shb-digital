// api/mockData.ts — cụm generator STATELESS tách khỏi mock.ts (nợ ghi từ S14 — file gốc >400
// LOC). Các hàm ở đây KHÔNG đụng room/turnText của MockBackend — thuần data-shape cho
// getModels/getStats/getCost/getCostTrend/listAssessments/runCompare. MockBackend (mock.ts)
// delegate 1-dòng sang đây — giữ NGUYÊN behavior/shape, chỉ DI CHUYỂN code.

import type {
  Assessment,
  CompareResult,
  CostResponse,
  CostTrendResponse,
  ModelsResponse,
  StatsResponse,
  StatsWindow,
} from '../types';
import { MOCK_LATENCY_MS, delay, uid } from './mockShared';

export async function mockGetModels(): Promise<ModelsResponse> {
  return {
    providers: [
      { name: 'claude-cli', kind: 'subscription', base_url: null, models: ['haiku', 'sonnet', 'opus'], default: true, has_key: true, note: 'đường chính (mock)' },
      { name: 'zai', kind: 'api', base_url: 'https://api.z.ai', models: ['glm-4.6', 'glm-4.5'], default: false, has_key: true, note: 'GLM z.ai (mock)' },
    ],
    default: 'claude-cli',
  };
}

// ── Stats + assessments (S13 T13-2/T13-3) + cost dashboard (S16 T16-3) ──
export async function mockGetStats(window: StatsWindow = '24h'): Promise<StatsResponse> {
  await delay(MOCK_LATENCY_MS);
  // số phân bố gần thực; 7d/30d lớn hơn 24h (delta dương). +sparks 24-bucket (S16 T16-3).
  const mul = window === '30d' ? 24 : window === '7d' ? 6 : 1;
  // spark 24-bucket: nhiễu quanh mức nền (deterministic — không Math.random để test ổn định).
  const spark = (base: number) => Array.from({ length: 24 }, (_, i) => Math.round(base * (0.7 + 0.6 * ((i * 7) % 11) / 11)));
  return {
    window,
    approvals: { approved: 12 * mul, rejected: 3 * mul, pending: 5, auto: 7 * mul },
    assessments: { green: 9 * mul, yellow: 6 * mul, red: 2 * mul },
    conversations: { total: 20 * mul, active: 3 },
    delta: { approvals_total: window === '24h' ? 4 : 14, assessments_total: window === '7d' ? -3 : 2 },
    sparks: {
      approved: spark(12), green: spark(9), total: spark(20),
    },
  };
}

// S16 T16-3: cost & vận hành AI (contract). Data gần thực: model zai/wrap/claude-cli, 4 role,
// 1-2 anomaly z≥2. cost_estimated=true (provider ngoài ước tính). Số scale theo window.
export async function mockGetCost(window: StatsWindow = '24h'): Promise<CostResponse> {
  await delay(MOCK_LATENCY_MS);
  const mul = window === '30d' ? 24 : window === '7d' ? 6 : 1;
  const round2 = (n: number) => Math.round(n * 100) / 100;
  return {
    window,
    total_cost_usd: round2(4.82 * mul),
    cost_estimated: true,
    breakdown: {
      input_tokens: 1_240_000 * mul,
      output_tokens: 388_000 * mul,
      cache_read_tokens: 2_100_000 * mul,
      cache_create_tokens: 156_000 * mul,
    },
    by_model: [
      { model: 'glm-4.6', cost_usd: round2(2.31 * mul), turns: 84 * mul, total_tokens: 2_040_000 * mul },
      { model: 'claude-cli/sonnet', cost_usd: round2(1.66 * mul), turns: 52 * mul, total_tokens: 980_000 * mul },
      { model: 'wrap/gpt-4o', cost_usd: round2(0.85 * mul), turns: 31 * mul, total_tokens: 864_000 * mul },
    ],
    by_role: [
      { role: 'credit', cost_usd: round2(1.94 * mul), turns: 61 * mul },
      { role: 'legal', cost_usd: round2(1.12 * mul), turns: 44 * mul },
      { role: 'products', cost_usd: round2(0.98 * mul), turns: 38 * mul },
      { role: 'ops', cost_usd: round2(0.78 * mul), turns: 24 * mul },
    ],
    anomalies: [
      { conv_id: 'conv-seed-1', title: 'Ca DN Gỗ Việt Phát — thẩm định phức tạp', cost_usd: 0.94, mean: 0.21, stddev: 0.18, z_score: 4.06 },
      { conv_id: 'conv-seed-2', title: 'Ca Hộ KD Tân Phú — nhiều vòng hỏi lại', cost_usd: 0.58, mean: 0.21, stddev: 0.18, z_score: 2.06 },
    ],
    delta: { total_cost_pct: window === '24h' ? 12.4 : window === '7d' ? -5.2 : 8.1 },
  };
}

// S16 T16-3: cost-trend long-format. bucket=hour (24h) → 24 điểm; day (7d/30d) → 7/30 điểm.
// series theo group_by (model|role). Deterministic (không random — test ổn định).
export async function mockGetCostTrend(window: StatsWindow, bucket: 'hour' | 'day', groupBy: 'model' | 'role'): Promise<CostTrendResponse> {
  await delay(MOCK_LATENCY_MS);
  const n = bucket === 'hour' ? 24 : window === '30d' ? 30 : 7;
  const names = groupBy === 'model'
    ? ['glm-4.6', 'claude-cli/sonnet', 'wrap/gpt-4o']
    : ['credit', 'legal', 'products', 'ops'];
  const buckets: CostTrendResponse['buckets'] = Array.from({ length: n }, (_, i) => {
    const series: Record<string, number> = {};
    names.forEach((name, j) => {
      // sóng deterministic khác pha theo (i,j) — có nhấp nhô nhìn giống thật
      const wave = 0.6 + 0.4 * Math.abs(Math.sin((i + j * 2) * 0.7));
      series[name] = Math.round(wave * (0.4 + j * 0.15) * 100) / 100;
    });
    return { ts: `${bucket === 'hour' ? `${String(i).padStart(2, '0')}:00` : `D${i + 1}`}`, series };
  });
  return { buckets };
}

export async function mockListAssessments(owner?: string, limit = 50): Promise<Assessment[]> {
  await delay(MOCK_LATENCY_MS);
  const all: Assessment[] = [
    {
      id: 'as_001', owner_id: 'C001', loan_type: 'Thế chấp', loan_amount_vnd: 5_000_000_000, lane: 'green',
      basis: 'lane_policy: green — DSCR ≥ 1.2, LTV ≤ 70%, CIC nhóm 1.',
      created_at: '2026-07-19T09:12:00',
      criteria: [
        { key: 'DSCR', level: 'pass', detail: 'DSCR 1.501 ≥ ngưỡng 1.2 (credit_assess).' },
        { key: 'LTV', level: 'pass', detail: 'LTV 62% ≤ 70% (tài sản định giá 8 tỷ).' },
        { key: 'CIC', level: 'pass', detail: 'Nhóm 1 — lịch sử tín dụng tốt (credit_cic_get).' },
      ],
    },
    {
      id: 'as_002', owner_id: 'C029', loan_type: 'Tín chấp', loan_amount_vnd: 800_000_000, lane: 'yellow',
      basis: 'lane_policy: yellow — DSCR biên, cần bổ sung tài sản đảm bảo.',
      created_at: '2026-07-19T08:40:00',
      criteria: [
        { key: 'DSCR', level: 'yellow', detail: 'DSCR 1.05 — dưới ngưỡng an toàn 1.2, sát rủi ro.' },
        { key: 'LTV', level: 'pass', detail: 'LTV 45% ≤ 70%.' },
        { key: 'CIC', level: 'pass', detail: 'Nhóm 1.' },
      ],
    },
    {
      id: 'as_003', owner_id: 'DN2024001', loan_type: 'Thế chấp DN', loan_amount_vnd: 12_000_000_000, lane: 'red',
      basis: 'lane_policy: red — DSCR < 1.0, giấy tờ pháp lý thiếu (pháp chế chặn).',
      created_at: '2026-07-19T07:55:00',
      criteria: [
        { key: 'DSCR', level: 'red', detail: 'DSCR 0.62 < 1.0 — không đủ dòng tiền trả nợ.' },
        { key: 'Pháp lý', level: 'red', detail: 'Thiếu giấy chứng nhận quyền sử dụng đất (check_documents).' },
        { key: 'CIC', level: 'yellow', detail: 'Nhóm 2 — có nợ quá hạn nhẹ.' },
      ],
    },
  ];
  const filtered = owner ? all.filter((a) => a.owner_id === owner) : all;
  return filtered.slice(0, limit);
}

export async function mockRunCompare(question: string): Promise<CompareResult> {
  await delay(MOCK_LATENCY_MS * 3);
  return {
    single: { text: `[Single-agent] Trả lời trực tiếp cho: ${question}. DSCR ước ~0.24, không đủ điều kiện.`, duration_s: 4.2, tool_calls: 0, cards: 0, conv_id: null },
    multi: { text: `[Multi-agent] Đội thẩm định: DSCR 0.236 (credit_assess), CIC nhóm 1, khuyến nghị vay nhỏ hơn — có nguồn từng số.`, duration_s: 38.5, tool_calls: 4, cards: 2, conv_id: uid('c') },
  };
}
