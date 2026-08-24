// CaseWorkbench.tsx — bàn làm việc hồ sơ nghiệp vụ theo CONTRACT §11 (D-77).
// Case có identity từ nguồn; surface này chỉ đọc và định hướng bước tiếp theo, không duyệt/giải ngân.
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { conversationApi } from '../../api';
import { ApiRequestError } from '../../api/client';
import type { CaseListFilters, CaseStatus, CaseSummary } from '../../types';
import './CaseWorkbench.css';
import { useExactCaseFocus } from './useExactCaseFocus';

const STATUS_META: Record<CaseStatus, { label: string; tone: string }> = {
  received: { label: 'Đã tiếp nhận', tone: 'casewb__status--idle' },
  missing_information: { label: 'Thiếu thông tin', tone: 'casewb__status--warn' },
  ready_for_preassessment: { label: 'Sẵn sàng sơ thẩm', tone: 'casewb__status--run' },
  preassessment_in_progress: { label: 'Đang sơ thẩm', tone: 'casewb__status--run' },
  needs_specialist: { label: 'Cần chuyên gia', tone: 'casewb__status--fail' },
  ready_for_handover: { label: 'Sẵn sàng bàn giao', tone: 'casewb__status--pass' },
  cancelled: { label: 'Đã hủy', tone: 'casewb__status--idle' },
};

const STATUS_OPTIONS = Object.entries(STATUS_META) as [CaseStatus, { label: string; tone: string }][];

const SOURCE_LABELS: Record<string, string> = {
  los: 'LOS',
  saha: 'SAHA',
  internal_operations: 'Vận hành nội bộ · chỉ đọc',
};

const PRODUCT_LABELS: Record<string, string> = {
  SME_SECURED: 'SME có tài sản bảo đảm',
  SME_WORKING_CAPITAL: 'Vốn lưu động SME',
  RETAIL_MORTGAGE: 'Vay mua nhà',
};

const FIELD_LABELS: Record<string, string> = {
  assigned_rm_subject: 'Cán bộ phụ trách',
  collateral_documents: 'Hồ sơ tài sản bảo đảm',
  collateral_valuation: 'Kết quả định giá tài sản',
  document_refs: 'Danh mục chứng từ',
  external_party_id: 'Mã khách hàng tại nguồn',
  financial_statements: 'Báo cáo tài chính',
  financial_statements_2025: 'Báo cáo tài chính năm 2025',
  loan_amount_vnd: 'Số tiền đề nghị',
  product_code: 'Sản phẩm tín dụng',
};

const LANE_META = {
  green: { label: 'Cơ sở sơ bộ: Có thể tiếp tục các bước kiểm tra', tone: 'casewb__basis--pass' },
  yellow: { label: 'Cơ sở sơ bộ: Cần bổ sung hoặc rà soát', tone: 'casewb__basis--warn' },
  red: { label: 'Cơ sở sơ bộ: Cần chuyên gia xem xét', tone: 'casewb__basis--fail' },
} as const;

const SOURCE_ISSUE_CODES = new Set([
  'case_source_not_connected',
  'case_source_unavailable',
  'source_disabled',
  'source_not_configured',
  'source_not_connected',
  'source_unavailable',
]);

type LoadIssue = { kind: 'source' | 'generic'; message: string };

interface Props {
  focusedCaseId?: string;
  onOpenCaseConversation?: (conversationId: string) => void;
}

export function CaseWorkbench({ focusedCaseId, onOpenCaseConversation }: Props = {}) {
  const [rows, setRows] = useState<CaseSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draftStatus, setDraftStatus] = useState<CaseStatus | ''>('');
  const [draftSource, setDraftSource] = useState('');
  const [activeStatus, setActiveStatus] = useState<CaseStatus | ''>('');
  const [activeSource, setActiveSource] = useState('');
  const [loading, setLoading] = useState(true);
  const [issue, setIssue] = useState<LoadIssue | null>(null);
  const requestGeneration = useRef(0);
  const { focusIssue, mergeFocused } = useExactCaseFocus(focusedCaseId, setRows, setSelectedId);

  const loadCases = useCallback(() => {
    const generation = ++requestGeneration.current;
    const filters: CaseListFilters = { limit: 50 };
    if (activeStatus) filters.status = activeStatus;
    if (activeSource) filters.source = activeSource;
    setLoading(true);
    setIssue(null);

    conversationApi
      .listCases(filters)
      .then((result) => {
        if (generation !== requestGeneration.current) return;
        const list = mergeFocused(Array.isArray(result) ? result : []);
        setRows(list);
        setSelectedId((current) => {
          if (focusedCaseId && list.some((item) => item.id === focusedCaseId)) return focusedCaseId;
          return list.some((item) => item.id === current) ? current : list[0]?.id ?? null;
        });
      })
      .catch((error: unknown) => {
        if (generation !== requestGeneration.current) return;
        const fallback = mergeFocused([]);
        setRows(fallback);
        setSelectedId(fallback[0]?.id ?? null);
        setIssue(classifyLoadIssue(error));
      })
      .finally(() => {
        if (generation === requestGeneration.current) setLoading(false);
      });
  }, [activeSource, activeStatus, focusedCaseId, mergeFocused]);

  useEffect(() => {
    loadCases();
    return () => { requestGeneration.current += 1; };
  }, [loadCases]);

  const applyFilters = (event: FormEvent) => {
    event.preventDefault();
    const source = draftSource.trim().toLowerCase();
    if (source === activeSource && draftStatus === activeStatus) {
      loadCases();
      return;
    }
    setActiveSource(source);
    setActiveStatus(draftStatus);
  };

  const clearFilters = () => {
    setDraftSource('');
    setDraftStatus('');
    setActiveSource('');
    setActiveStatus('');
  };

  const selected = rows.find((item) => item.id === selectedId) ?? rows[0] ?? null;
  const hasFilters = Boolean(activeSource || activeStatus);

  return (
    <div className="ct__section casewb">
      <div className="casewb__heading">
        <div>
          <div className="ct__section-title">Hồ sơ chờ sơ thẩm ({rows.length})</div>
          <div className="casewb__subtitle">Dữ liệu từ hệ thống nghiệp vụ · kết quả hiển thị chỉ là cơ sở sơ bộ</div>
        </div>
        <form className="casewb__filters" onSubmit={applyFilters} aria-label="Bộ lọc hồ sơ">
          <select
            className="casewb__filter"
            value={draftStatus}
            onChange={(event) => setDraftStatus(event.target.value as CaseStatus | '')}
            aria-label="Lọc theo trạng thái hồ sơ"
          >
            <option value="">Tất cả trạng thái</option>
            {STATUS_OPTIONS.map(([status, meta]) => <option key={status} value={status}>{meta.label}</option>)}
          </select>
          <input
            className="casewb__filter casewb__filter--source"
            value={draftSource}
            onChange={(event) => setDraftSource(event.target.value)}
            placeholder="Nguồn: LOS, SAHA…"
            aria-label="Lọc theo nguồn hồ sơ"
          />
          <button className="ct__refresh" type="submit" disabled={loading}>Áp dụng</button>
          {hasFilters && <button className="ct__refresh" type="button" onClick={clearFilters}>Xóa lọc</button>}
        </form>
      </div>

      {loading && rows.length === 0 && <div className="ct__empty" role="status">Đang tải hồ sơ từ nguồn nghiệp vụ…</div>}
      {focusIssue && <div className="ct__notice" data-testid="focused-case-error">{focusIssue}</div>}
      {!loading && issue && <LoadIssueState issue={issue} source={activeSource} onRetry={loadCases} />}
      {!loading && !issue && rows.length === 0 && (
        <EmptyCases activeSource={activeSource} activeStatus={activeStatus} onClear={clearFilters} />
      )}
      {rows.length > 0 && (
        <div className={`casewb__split${loading ? ' casewb__split--loading' : ''}`} aria-busy={loading} data-testid="case-first-viewport">
          <div className="casewb__list" aria-label="Danh sách hồ sơ">
            {rows.map((item) => (
              <CaseRow
                key={item.id}
                item={item}
                selected={selected?.id === item.id}
                focused={focusedCaseId === item.id}
                onSelect={setSelectedId}
              />
            ))}
          </div>
          {selected && <CaseDetail item={selected} onOpenCaseConversation={onOpenCaseConversation} />}
        </div>
      )}
    </div>
  );
}

function CaseRow({ item, selected, focused, onSelect }: {
  item: CaseSummary;
  selected: boolean;
  focused: boolean;
  onSelect: (id: string) => void;
}) {
  const rowRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (focused) rowRef.current?.scrollIntoView?.({ block: 'center' });
  }, [focused]);
  const status = STATUS_META[item.case_status] ?? { label: 'Trạng thái chưa xác định', tone: 'casewb__status--idle' };
  const missingCount = safeMissingFields(item).length;
  return (
    <button
      ref={rowRef}
      type="button"
      className={`casewb__row${selected ? ' casewb__row--active' : ''}${focused ? ' casewb__row--focused' : ''}`}
      onClick={() => onSelect(item.id)}
      aria-pressed={selected}
      aria-current={focused ? 'true' : undefined}
      data-testid={`case-row-${item.id}`}
    >
      <span className="casewb__row-top">
        <span className="casewb__source">{sourceLabel(item.source_system)}</span>
        <span className={`casewb__status ${status.tone}`}>{status.label}</span>
      </span>
      <span className="casewb__case-id">{safeText(item.external_case_id, 'Chưa có mã hồ sơ nguồn')}</span>
      <span className="casewb__row-meta">{productLabel(item.product_code)} · {formatVnd(item.loan_amount_vnd)}</span>
      <span className="casewb__row-meta">Dữ liệu {formatTimestamp(item.data_as_of ?? item.synced_at)}</span>
      {missingCount > 0 && <span className="casewb__missing-count">Thiếu {missingCount} trường thông tin</span>}
    </button>
  );
}

function CaseDetail({ item, onOpenCaseConversation }: {
  item: CaseSummary;
  onOpenCaseConversation?: (conversationId: string) => void;
}) {
  const status = STATUS_META[item.case_status] ?? { label: 'Trạng thái chưa xác định', tone: 'casewb__status--idle' };
  const missing = safeMissingFields(item);
  const lane = item.assessment?.lane ?? null;
  const laneMeta = lane ? LANE_META[lane] : null;
  const linkedConversationId = safeText(item.conversation_id, '');

  return (
    <article className="casewb__detail" data-testid="case-detail">
      <header className="casewb__detail-head">
        <div>
          <div className="casewb__eyebrow">{sourceLabel(item.source_system)} · Mã hồ sơ nguồn</div>
          <h2 className="casewb__detail-id">{safeText(item.external_case_id, 'Chưa có mã hồ sơ nguồn')}</h2>
        </div>
        <span className={`casewb__status casewb__status--lg ${status.tone}`}>{status.label}</span>
      </header>

      <div className={`casewb__basis ${laneMeta?.tone ?? 'casewb__basis--idle'}`}>
        <span>{laneMeta?.label ?? 'Chưa có cơ sở sơ bộ'}</span>
        {item.assessment?.created_at && <time dateTime={item.assessment.created_at}>{formatTimestamp(item.assessment.created_at)}</time>}
      </div>
      <p className="casewb__disclaimer">Cơ sở sơ bộ hỗ trợ kiểm tra hồ sơ, không phải quyết định tín dụng hoặc phê duyệt.</p>

      <dl className="casewb__facts">
        <Fact label="Sản phẩm" value={productLabel(item.product_code)} />
        <Fact label="Số tiền đề nghị" value={formatVnd(item.loan_amount_vnd)} />
        <Fact label="Dữ liệu hiệu lực" value={formatTimestamp(item.data_as_of)} />
        <Fact label="Đồng bộ vào Tower" value={formatTimestamp(item.synced_at)} />
        <Fact label="Tham chiếu khách hàng" value={safeText(item.party_reference, 'Chưa có')} />
        <Fact label="Mã hồ sơ nội bộ" value={safeText(item.internal_application_id, 'Chưa liên kết')} />
      </dl>

      <section className="casewb__blockers" aria-labelledby={`case-missing-${item.id}`}>
        <div className="casewb__section-line">
          <h3 id={`case-missing-${item.id}`}>Thông tin cần hoàn thiện</h3>
          <span>{safeCount(item.document_count)} chứng từ đã ghi nhận</span>
        </div>
        {missing.length > 0 ? (
          <ul>{missing.map((field) => <li key={field}>{fieldLabel(field)}</li>)}</ul>
        ) : (
          <p>Không ghi nhận trường thông tin bắt buộc đang thiếu.</p>
        )}
      </section>

      <section className="casewb__next" aria-label="Việc tiếp theo">
        <span>Việc tiếp theo</span>
        <p>{safeText(item.next_action, 'Chờ nguồn nghiệp vụ xác định bước tiếp theo.')}</p>
      </section>

      {linkedConversationId && onOpenCaseConversation && (
        <div className="casewb__linked">
          <span>Hồ sơ đã có phiên làm việc được liên kết.</span>
          <button
            type="button"
            className="btn btn--primary casewb__open"
            onClick={() => onOpenCaseConversation(linkedConversationId)}
          >
            Mở phiên xử lý
          </button>
        </div>
      )}
    </article>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}

function LoadIssueState({ issue, source, onRetry }: { issue: LoadIssue; source: string; onRetry: () => void }) {
  if (issue.kind === 'source') {
    return (
      <div className="casewb__state casewb__state--source" role="status">
        <strong>Nguồn hồ sơ chưa được kết nối hoặc đang tắt</strong>
        <p>{source ? `${sourceLabel(source)} chưa cung cấp dữ liệu cho Control Tower.` : 'Chưa có kết nối khả dụng tới nguồn hồ sơ nghiệp vụ.'}</p>
        <p>Kiểm tra cấu hình nguồn và API Gateway; không tạo hồ sơ thủ công tại màn này.</p>
        <button type="button" className="ct__refresh" onClick={onRetry}>Thử lại</button>
      </div>
    );
  }
  return (
    <div className="casewb__state casewb__state--error" role="alert">
      <strong>Không tải được hồ sơ</strong>
      <p>{issue.message}</p>
      <button type="button" className="ct__refresh" onClick={onRetry}>Thử lại</button>
    </div>
  );
}

function EmptyCases({ activeSource, activeStatus, onClear }: { activeSource: string; activeStatus: CaseStatus | ''; onClear: () => void }) {
  if (activeSource && !activeStatus) {
    return (
      <div className="casewb__state" role="status">
        <strong>{sourceLabel(activeSource)} chưa có hồ sơ</strong>
        <p>Chưa có hồ sơ nào được đồng bộ từ nguồn này.</p>
        <button type="button" className="ct__refresh" onClick={onClear}>Xem tất cả nguồn</button>
      </div>
    );
  }
  if (activeSource || activeStatus) {
    return (
      <div className="casewb__state" role="status">
        <strong>Không có hồ sơ phù hợp bộ lọc</strong>
        <p>Hãy điều chỉnh trạng thái hoặc nguồn hồ sơ để tìm lại.</p>
        <button type="button" className="ct__refresh" onClick={onClear}>Xóa bộ lọc</button>
      </div>
    );
  }
  return (
    <div className="casewb__state" role="status">
      <strong>Chưa có hồ sơ nghiệp vụ</strong>
      <p>Chưa có hồ sơ nào được đồng bộ từ các nguồn nghiệp vụ.</p>
    </div>
  );
}

function classifyLoadIssue(error: unknown): LoadIssue {
  if (error instanceof ApiRequestError) {
    const code = error.body?.code ?? '';
    if (SOURCE_ISSUE_CODES.has(code)) return { kind: 'source', message: 'Nguồn hồ sơ chưa sẵn sàng.' };
    return { kind: 'generic', message: error.body?.message ?? 'Vui lòng thử tải lại sau.' };
  }
  return { kind: 'generic', message: 'Vui lòng thử tải lại sau.' };
}

function sourceLabel(source: string): string {
  const normalized = safeText(source, '').toLowerCase();
  return SOURCE_LABELS[normalized] ?? humanizeCode(source, 'Nguồn chưa xác định');
}

function productLabel(product: string | null): string {
  if (!product) return 'Chưa xác định';
  return PRODUCT_LABELS[product] ?? humanizeCode(product, 'Chưa xác định');
}

function fieldLabel(field: string): string {
  const normalized = safeText(field, '').toLowerCase();
  // Missing-field key lạ có thể là identifier nội bộ của nguồn. Fail-closed ở presentation:
  // vẫn báo có blocker nhưng không đẩy tên kỹ thuật/raw reference ra màn cán bộ.
  return FIELD_LABELS[normalized] ?? 'Thông tin bổ sung từ nguồn';
}

function humanizeCode(value: string, fallback: string): string {
  const words = safeText(value, '').replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim();
  if (!words) return fallback;
  return words.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function safeText(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}

function safeMissingFields(item: CaseSummary): string[] {
  if (!Array.isArray(item.missing_fields)) return [];
  const fields = item.missing_fields
    .filter((field) => typeof field === 'string' && field.trim())
    .map((field) => field.trim());
  return [...new Set(fields)];
}

function safeCount(value: number): number {
  return Number.isFinite(value) && value >= 0 ? Math.floor(value) : 0;
}

function formatVnd(value: number | null): string {
  if (value == null || !Number.isFinite(value) || value < 0) return 'Chưa có';
  return `${value.toLocaleString('vi-VN')} ₫`;
}

function formatTimestamp(value: string | null): string {
  if (!value || Number.isNaN(Date.parse(value))) return 'Chưa có thời điểm';
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value);
  if (!match) return 'Chưa có thời điểm';
  return `${match[3]}/${match[2]}/${match[1]} ${match[4]}:${match[5]}`;
}
