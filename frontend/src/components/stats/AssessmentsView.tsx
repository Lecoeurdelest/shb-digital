// AssessmentsView.tsx — tab "Hồ sơ + lý do AI" (S13 T13-3). Danh sách assessments (lane chip màu +
// owner + số tiền + thời gian) → click → panel chi tiết: từng tiêu chí 3 trụ (criteria[] level chip +
// detail) + lane + "Lý do AI" (basis). Theme-aware (var token). Defensive: criteria rỗng/lane lạ → an toàn.
import { useEffect, useState } from 'react';
import { conversationApi } from '../../api';
import { ApiRequestError } from '../../api/client';
import type { Assessment, AssessmentCriterion } from '../../types';
import './AssessmentsView.css';

const LANE_META: Record<string, { label: string; cls: string }> = {
  green: { label: 'GREEN — Đạt', cls: 'lane--green' },
  yellow: { label: 'YELLOW — Cân nhắc', cls: 'lane--yellow' },
  red: { label: 'RED — Từ chối', cls: 'lane--red' },
};
function laneMeta(lane: string) {
  return LANE_META[lane] ?? { label: lane.toUpperCase(), cls: 'lane--idle' };
}

const LEVEL_META: Record<string, { mark: string; cls: string }> = {
  pass: { mark: '✓', cls: 'asmt__crit--pass' },
  green: { mark: '✓', cls: 'asmt__crit--pass' },
  yellow: { mark: '⚠', cls: 'asmt__crit--yellow' },
  red: { mark: '✗', cls: 'asmt__crit--red' },
};
function levelMeta(level: string) {
  return LEVEL_META[level] ?? { mark: '•', cls: 'asmt__crit--idle' };
}

// DF-B-02 (gộp): criteria key BE tiếng Anh (identity/criminal/cic…) → nhãn Việt cho cán bộ đọc.
// Tra CASE-INSENSITIVE; key lạ/tên riêng viết hoa (DSCR/LTV) → pass-through nguyên (pattern A-06).
const CRITERION_LABEL: Record<string, string> = {
  identity: 'Định danh',
  criminal: 'Án tích',
  cic: 'CIC', // tên riêng — giữ
  income: 'Thu nhập',
  employment: 'Việc làm',
  collateral: 'Tài sản đảm bảo',
  docs: 'Hồ sơ giấy tờ',
  documents: 'Hồ sơ giấy tờ',
  purpose: 'Mục đích vay',
  credit: 'Lịch sử tín dụng',
  legal: 'Pháp lý',
};
function criterionLabel(key: string): string {
  return CRITERION_LABEL[key.toLowerCase()] ?? key; // lạ → giữ nguyên
}

function fmtVnd(n?: number): string {
  if (n == null) return '—';
  if (n >= 1e9) return `${(n / 1e9).toFixed(n % 1e9 === 0 ? 0 : 1)} tỷ`;
  if (n >= 1e6) return `${Math.round(n / 1e6)} triệu`;
  return n.toLocaleString('vi-VN');
}
function fmtTs(ts?: string): string {
  return ts ? ts.slice(0, 16).replace('T', ' ') : '';
}

export function AssessmentsView() {
  const [rows, setRows] = useState<Assessment[]>([]);
  const [selected, setSelected] = useState<Assessment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    conversationApi
      .listAssessments()
      .then((r) => {
        const list = Array.isArray(r) ? r : [];
        setRows(list);
        setError(null);
        setSelected((cur) => cur ?? list[0] ?? null); // chọn sẵn hồ sơ đầu
      })
      .catch((e: unknown) => setError(e instanceof ApiRequestError ? e.body?.message ?? 'Lỗi tải hồ sơ' : 'Lỗi tải hồ sơ'));
  }, []);

  return (
    <div className="ct__section asmt">
      <div className="ct__section-head">
        <span className="ct__section-title">Hồ sơ thẩm định + lý do AI ({rows.length})</span>
      </div>
      {error && <div className="ct__error">{error}</div>}
      {rows.length === 0 && !error ? (
        <div className="ct__empty">Chưa có hồ sơ thẩm định nào.</div>
      ) : (
        <div className="asmt__split">
          {/* danh sách */}
          <div className="asmt__list">
            {rows.map((a) => {
              const m = laneMeta(a.lane);
              return (
                <button
                  key={String(a.id)}
                  type="button"
                  className={`asmt__row${selected?.id === a.id ? ' asmt__row--active' : ''}`}
                  onClick={() => setSelected(a)}
                  data-testid={`asmt-row-${a.id}`}
                >
                  <span className={`asmt__lane ${m.cls}`}>{a.lane.toUpperCase()}</span>
                  <span className="asmt__row-body">
                    <span className="asmt__row-owner">{a.owner_id} · {a.loan_type ?? 'vay'}</span>
                    <span className="asmt__row-meta">{fmtVnd(a.loan_amount_vnd)} · {fmtTs(a.created_at)}</span>
                  </span>
                </button>
              );
            })}
          </div>

          {/* panel chi tiết */}
          {selected && <AssessmentDetail assessment={selected} />}
        </div>
      )}
    </div>
  );
}

function AssessmentDetail({ assessment: a }: { assessment: Assessment }) {
  const m = laneMeta(a.lane);
  const criteria: AssessmentCriterion[] = Array.isArray(a.criteria) ? a.criteria : [];
  return (
    <div className="asmt__detail" data-testid="asmt-detail">
      <div className="asmt__detail-head">
        <span className={`asmt__lane asmt__lane--lg ${m.cls}`}>{m.label}</span>
        <span className="asmt__detail-title">{a.owner_id} · {a.loan_type ?? 'vay'} · {fmtVnd(a.loan_amount_vnd)}</span>
      </div>

      <div className="asmt__crit-label">Tiêu chí thẩm định (3 trụ)</div>
      {criteria.length === 0 ? (
        <div className="asmt__crit-empty">Không có chi tiết tiêu chí cho hồ sơ này.</div>
      ) : (
        <div className="asmt__crit-list">
          {criteria.map((c, i) => {
            const lm = levelMeta(c.level);
            return (
              <div key={`${c.key}-${i}`} className={`asmt__crit ${lm.cls}`}>
                <span className="asmt__crit-mark" aria-hidden="true">{lm.mark}</span>
                <span className="asmt__crit-body">
                  <span className="asmt__crit-key">{criterionLabel(c.key)}</span>
                  {c.detail && <span className="asmt__crit-detail">{c.detail}</span>}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {a.basis && (
        <div className="asmt__basis">
          {/* DF-B-02: basis = policy snapshot lúc chấm (giống nhau giữa hồ sơ là by-design) — KHÔNG phải
              lý do riêng. Lý do per-hồ-sơ thật = 3 tiêu chí phía trên. Nhãn/chú thích phản ánh đúng. */}
          <div className="asmt__basis-label">📋 Chính sách áp dụng (snapshot lúc chấm)</div>
          <div className="asmt__basis-text">{a.basis}</div>
          <div className="asmt__basis-note">Lý do riêng của hồ sơ nằm ở tiêu chí 3 trụ phía trên.</div>
        </div>
      )}
    </div>
  );
}
