// CardRenderer.tsx — 1 SWITCH theo card.type → 7 component (canvas-present §3). Default branch
// render THÔ (type lạ không crash — N3 vỏ-mù). Mọi body đọc field qua cardUtil (defensive):
// field thiếu → bỏ qua; value MIXED (number|string); pass NULLABLE → null=không badge.
// Look-and-feel tham khảo design/workspace/cards.jsx (D-13).
import type { Card } from '../../types';
import { cardItems, cardField, itemField, renderValue, collectSources } from './cardUtil';
import { CitationChip } from './CitationChip';
import { ApprovalPanel, type DecideFn } from './ApprovalPanel';
import { FormCard, type FormSubmitFn } from './FormCard';
import './CardRenderer.css';

type CiteFn = (taskId: string | null, source: string) => void;

interface CardProps {
  card: Card;
  onCite?: CiteFn;
  onDecide?: DecideFn;
  canDecide?: boolean;
  onFormSubmit?: FormSubmitFn; // T9-3 — khách nộp hồ sơ (card type 'form')
  formDrafts?: Record<string, Record<string, string>>; // DF-A-04 — form values sống qua đổi tab (theo card.id)
  onFormDraftChange?: (cardId: string, values: Record<string, string>) => void;
}

// card chiếm cả 2 cột (rộng) cho case_file/document/approval/form; còn lại 1 cột.
const WIDE = new Set(['case_file', 'document', 'approval', 'form']);

export function CardRenderer({ card, onCite, onDecide, canDecide, onFormSubmit, formDrafts, onFormDraftChange }: CardProps) {
  const wide = WIDE.has(card.type);
  return (
    <div className={`card${wide ? ' card--wide' : ''}`} id={`card-${card.id}`} data-testid={`card-${card.type}`}>
      <div className="card__head">
        <span className="card__title">{card.title ?? cardTypeLabel(card.type)}</span>
        <span className="card__type">{card.type}</span>
      </div>
      <div className="card__body">
        <CardBody card={card} onCite={onCite} onDecide={onDecide} canDecide={canDecide} onFormSubmit={onFormSubmit}
          formDrafts={formDrafts} onFormDraftChange={onFormDraftChange} />
      </div>
    </div>
  );
}

function CardBody({ card, onCite, onDecide, canDecide, onFormSubmit, formDrafts, onFormDraftChange }: CardProps) {
  switch (card.type) {
    case 'metric':
      return <MetricBody card={card} onCite={onCite} />;
    case 'checklist':
      return <ChecklistBody card={card} />;
    case 'options':
      return <OptionsBody card={card} onCite={onCite} />;
    case 'timeline':
      return <TimelineBody card={card} />;
    case 'case_file':
      return <CaseFileBody card={card} />;
    case 'document':
      return <DocumentBody card={card} onCite={onCite} />;
    case 'approval':
      return <ApprovalPanel card={card} onDecide={onDecide} canDecide={canDecide} />;
    case 'form':
      return <FormCard card={card} onSubmit={onFormSubmit}
        draftValues={formDrafts?.[card.id] ?? {}} onDraftChange={onFormDraftChange} />;
    default:
      return <RawBody card={card} />;
  }
}

const TYPE_LABEL: Record<string, string> = {
  metric: 'Bảng chỉ số',
  checklist: 'Điều kiện',
  options: 'So sánh gói',
  timeline: 'Lộ trình',
  case_file: 'Hồ sơ',
  document: 'Tờ trình',
  approval: 'Phê duyệt',
};
function cardTypeLabel(type: string): string {
  return TYPE_LABEL[type] ?? type;
}

// ── metric: bảng chỉ số. value MIXED, pass NULLABLE (null→không badge), source→chip ──
// DF-A-06: dịch thuật ngữ tiếng Anh hay gặp ở tầng HIỂN THỊ (fallback map — KHÔNG đổi data; tên lạ
// giữ nguyên pass-through). Chỉ áp cụm tiếng Anh trong ngoặc / tên trụ phổ biến.
const METRIC_LABEL_MAP: Record<string, string> = {
  Identity: 'Định danh', Criminal: 'Án tích', Income: 'Thu nhập', Collateral: 'Tài sản đảm bảo',
  Credit: 'Tín dụng', Legal: 'Pháp lý', Residence: 'Cư trú', Employment: 'Việc làm',
};
function mapMetricLabel(raw: string): string {
  // "Nhân thân (Identity)" → thay cụm trong ngoặc bằng tiếng Việt; "Identity" đơn → dịch cả.
  let out = raw;
  for (const [en, vi] of Object.entries(METRIC_LABEL_MAP)) {
    out = out.replace(new RegExp(`\\(${en}\\)`, 'g'), `(${vi})`).replace(new RegExp(`^${en}$`), vi);
  }
  return out;
}

function MetricBody({ card, onCite }: { card: Card; onCite?: CiteFn }) {
  const items = cardItems(card);
  if (items.length === 0) return <EmptyBody />;
  // có item nào có threshold không → hiện cột Ngưỡng + header phân tách (DF-A-06: value vs threshold dính nhau).
  const hasThreshold = items.some((it) => itemField(it, 'threshold') != null);
  return (
    <table className="card-metric">
      <thead>
        <tr className="card-metric__head">
          <th>Chỉ tiêu</th>
          <th>Thực tế</th>
          {hasThreshold && <th>Ngưỡng</th>}
          <th>Kết quả</th>
          <th>Nguồn</th>
        </tr>
      </thead>
      <tbody>
        {items.map((it, i) => {
          const pass = itemField<boolean | null>(it, 'pass');
          const source = itemField<string>(it, 'source');
          const threshold = itemField(it, 'threshold');
          const nameRaw = renderValue(itemField(it, 'name'));
          return (
            <tr key={i}>
              <td className="card-metric__name">{mapMetricLabel(nameRaw)}</td>
              <td className="card-metric__value">{renderValue(itemField(it, 'value'))}</td>
              {hasThreshold && <td className="card-metric__thr">{threshold != null ? renderValue(threshold) : ''}</td>}
              <td className="card-metric__pass">
                {pass === true && <span className="badge badge--pass">✓ Đạt</span>}
                {pass === false && <span className="badge badge--fail">✗ Không đạt</span>}
                {/* pass == null → không render badge (số tham chiếu N/A) */}
              </td>
              <td className="card-metric__src">
                {source && <CitationChip source={source} taskId={card.task_id} onCite={onCite} />}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── checklist: item {item, status: ok|missing|risk, note?} ──
function ChecklistBody({ card }: { card: Card }) {
  const items = cardItems(card);
  if (items.length === 0) return <EmptyBody />;
  const MARK: Record<string, string> = { ok: '✓', missing: '✗', risk: '⚠' };
  const TONE: Record<string, string> = { ok: 'ok', missing: 'fail', risk: 'warn' };
  return (
    <ul className="card-checklist">
      {items.map((it, i) => {
        const status = String(itemField(it, 'status') ?? 'ok');
        const tone = TONE[status] ?? 'ok';
        const note = itemField(it, 'note');
        return (
          <li key={i} className={`card-checklist__row card-checklist__row--${tone}`}>
            <span className="card-checklist__mark">{MARK[status] ?? '•'}</span>
            <span className="card-checklist__text">
              {renderValue(itemField(it, 'item') ?? itemField(it, 'name'))}
              {note != null && <span className="card-checklist__note">{renderValue(note)}</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

// ── options: item {name, rate, tenor, fee, fit} + recommended ──
function OptionsBody({ card, onCite }: { card: Card; onCite?: CiteFn }) {
  const items = cardItems(card);
  if (items.length === 0) return <EmptyBody />;
  const rec = cardField<string>(card, 'recommended');
  return (
    <div className="card-options">
      {items.map((it, i) => {
        const name = renderValue(itemField(it, 'name'));
        const isRec = rec != null && name === renderValue(rec);
        const source = itemField<string>(it, 'source');
        return (
          <div key={i} className={`card-options__row${isRec ? ' card-options__row--rec' : ''}`}>
            <span className="card-options__mark">{isRec ? '★' : '○'}</span>
            <span className="card-options__name">{name}</span>
            {itemField(it, 'rate') != null && <span className="card-options__rate">{renderValue(itemField(it, 'rate'))}</span>}
            {itemField(it, 'tenor') != null && <span className="card-options__meta">{renderValue(itemField(it, 'tenor'))}</span>}
            {itemField(it, 'fee') != null && <span className="card-options__meta">{renderValue(itemField(it, 'fee'))}</span>}
            {source && <CitationChip source={source} taskId={card.task_id} onCite={onCite} />}
          </div>
        );
      })}
    </div>
  );
}

// ── timeline: item shape TỰ DO (N3 vỏ-mù) — DF-A-05-FE render TOLERANT theo evidence prod.
// Shape thật sub emit: {name, detail, status, assignee}. Dòng chính = step??name; dòng mô tả =
// detail??description??value; meta chips = owner/assignee/eta/status + field string LẠ nối vào mô tả.
// Item rỗng hẳn → "(chưa có mô tả)". KHÔNG migrate data — card cũ (2afff539) tự đọc được sau fix.
const TIMELINE_PRIMARY_KEYS = ['step', 'name'];
const TIMELINE_DESC_KEYS = ['detail', 'description', 'value'];
const TIMELINE_META_KEYS = ['owner', 'assignee', 'eta', 'status'];
const TIMELINE_KNOWN = new Set([...TIMELINE_PRIMARY_KEYS, ...TIMELINE_DESC_KEYS, ...TIMELINE_META_KEYS]);

function asRec(it: unknown): Record<string, unknown> {
  return it && typeof it === 'object' ? (it as Record<string, unknown>) : {};
}
function firstStr(rec: Record<string, unknown>, keys: string[]): string | null {
  for (const k of keys) {
    const v = rec[k];
    if (v != null && String(v).trim()) return String(v).trim();
  }
  return null;
}

// dòng chính (step) — nếu vắng, dùng dòng mô tả làm chính (đừng để trống); vẫn vắng → "(chưa có mô tả)".
function timelineTitle(rec: Record<string, unknown>): string {
  return firstStr(rec, TIMELINE_PRIMARY_KEYS) ?? firstStr(rec, TIMELINE_DESC_KEYS) ?? '(chưa có mô tả)';
}
// dòng mô tả — detail/description/value + field string LẠ (ngoài known) nối vào, KHÔNG vứt nội dung.
function timelineDesc(rec: Record<string, unknown>): string {
  const parts: string[] = [];
  // chỉ lấy desc key nếu KHÁC cái đã dùng làm title (tránh lặp)
  const title = firstStr(rec, TIMELINE_PRIMARY_KEYS);
  const desc = firstStr(rec, TIMELINE_DESC_KEYS);
  if (title && desc && desc !== title) parts.push(desc);
  for (const [k, v] of Object.entries(rec)) {
    if (TIMELINE_KNOWN.has(k)) continue;
    if (typeof v === 'string' || typeof v === 'number') { const s = String(v).trim(); if (s) parts.push(s); }
  }
  return parts.join(' · ');
}

function TimelineBody({ card }: { card: Card }) {
  const items = cardItems(card);
  if (items.length === 0) return <EmptyBody />;
  const total = cardField(card, 'total_days');
  return (
    <div className="card-timeline">
      {items.map((it, i) => {
        const rec = asRec(it);
        const desc = timelineDesc(rec);
        const metaChips = TIMELINE_META_KEYS
          .map((k) => (rec[k] != null && String(rec[k]).trim() ? String(rec[k]).trim() : null))
          .filter((v): v is string => v !== null);
        return (
          <div key={i} className="card-timeline__row">
            <span className="card-timeline__num">{i + 1}</span>
            <div className="card-timeline__body">
              <div className="card-timeline__step">{timelineTitle(rec)}</div>
              {desc && <div className="card-timeline__desc">{desc}</div>}
              {metaChips.length > 0 && (
                <div className="card-timeline__meta">
                  {metaChips.map((m, j) => <span key={j} className="card-timeline__chip">{m}</span>)}
                </div>
              )}
            </div>
          </div>
        );
      })}
      {total != null && <div className="card-timeline__total">Tổng: {renderValue(total)} ngày</div>}
    </div>
  );
}

// ── case_file: item {label, value} + flags ──
function CaseFileBody({ card }: { card: Card }) {
  const items = cardItems(card);
  const flags = cardField<unknown[]>(card, 'flags');
  return (
    <div className="card-casefile">
      {items.length > 0 && (
        <div className="card-casefile__grid">
          {items.map((it, i) => (
            <div key={i} className="card-casefile__cell">
              <div className="card-casefile__label">{renderValue(itemField(it, 'label') ?? itemField(it, 'name'))}</div>
              <div className="card-casefile__value">{renderValue(itemField(it, 'value'))}</div>
            </div>
          ))}
        </div>
      )}
      {Array.isArray(flags) && flags.length > 0 && (
        <div className="card-casefile__flags">
          {flags.map((f, i) => (
            <span key={i} className="badge badge--warn">⚑ {renderValue(f)}</span>
          ))}
        </div>
      )}
      {items.length === 0 && (!Array.isArray(flags) || flags.length === 0) && <EmptyBody />}
    </div>
  );
}

// ── document: item {section, content} + sources ──
function DocumentBody({ card, onCite }: { card: Card; onCite?: CiteFn }) {
  const items = cardItems(card);
  const sources = collectSources(card);
  return (
    <div className="card-document">
      <div className="card-document__paper">
        {items.length === 0 && <EmptyBody />}
        {items.map((it, i) => (
          <div key={i} className="card-document__section">
            <div className="card-document__sec-title">{renderValue(itemField(it, 'section') ?? itemField(it, 'label'))}</div>
            <div className="card-document__sec-body">{renderValue(itemField(it, 'content') ?? itemField(it, 'value'))}</div>
          </div>
        ))}
      </div>
      {sources.length > 0 && (
        <div className="card-document__sources">
          <span className="card-document__src-label">Nguồn:</span>
          {sources.map((s) => (
            <CitationChip key={s} source={s} taskId={card.task_id} onCite={onCite} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── default: type lạ → render THÔ (title + JSON items). KHÔNG crash (N3). ──
function RawBody({ card }: { card: Card }) {
  return (
    <pre className="card-raw">{JSON.stringify(card.items ?? card, null, 2)}</pre>
  );
}

function EmptyBody() {
  return <div className="card-empty">— chưa có nội dung —</div>;
}
