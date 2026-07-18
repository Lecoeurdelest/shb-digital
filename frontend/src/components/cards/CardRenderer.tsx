// CardRenderer.tsx — 1 SWITCH theo card.type → 7 component (canvas-present §3). Default branch
// render THÔ (type lạ không crash — N3 vỏ-mù). Mọi body đọc field qua cardUtil (defensive):
// field thiếu → bỏ qua; value MIXED (number|string); pass NULLABLE → null=không badge.
// Look-and-feel tham khảo design/workspace/cards.jsx (D-13).
import type { Card } from '../../types';
import { cardItems, cardField, itemField, renderValue, collectSources } from './cardUtil';
import { CitationChip } from './CitationChip';
import { ApprovalPanel, type DecideFn } from './ApprovalPanel';
import './CardRenderer.css';

type CiteFn = (taskId: string | null, source: string) => void;

// card chiếm cả 2 cột (rộng) cho case_file/document/approval; còn lại 1 cột.
const WIDE = new Set(['case_file', 'document', 'approval']);

export function CardRenderer({ card, onCite, onDecide }: { card: Card; onCite?: CiteFn; onDecide?: DecideFn }) {
  const wide = WIDE.has(card.type);
  return (
    <div className={`card${wide ? ' card--wide' : ''}`} id={`card-${card.id}`} data-testid={`card-${card.type}`}>
      <div className="card__head">
        <span className="card__title">{card.title ?? cardTypeLabel(card.type)}</span>
        <span className="card__type">{card.type}</span>
      </div>
      <div className="card__body">
        <CardBody card={card} onCite={onCite} onDecide={onDecide} />
      </div>
    </div>
  );
}

function CardBody({ card, onCite, onDecide }: { card: Card; onCite?: CiteFn; onDecide?: DecideFn }) {
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
      return <ApprovalPanel card={card} onDecide={onDecide} />;
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
function MetricBody({ card, onCite }: { card: Card; onCite?: CiteFn }) {
  const items = cardItems(card);
  if (items.length === 0) return <EmptyBody />;
  return (
    <table className="card-metric">
      <tbody>
        {items.map((it, i) => {
          const pass = itemField<boolean | null>(it, 'pass');
          const source = itemField<string>(it, 'source');
          const threshold = itemField(it, 'threshold');
          return (
            <tr key={i}>
              <td className="card-metric__name">{renderValue(itemField(it, 'name'))}</td>
              <td className="card-metric__value">{renderValue(itemField(it, 'value'))}</td>
              <td className="card-metric__thr">{threshold != null ? renderValue(threshold) : ''}</td>
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

// ── timeline: item {step, owner, eta} + total_days ──
function TimelineBody({ card }: { card: Card }) {
  const items = cardItems(card);
  if (items.length === 0) return <EmptyBody />;
  const total = cardField(card, 'total_days');
  return (
    <div className="card-timeline">
      {items.map((it, i) => (
        <div key={i} className="card-timeline__row">
          <span className="card-timeline__num">{i + 1}</span>
          <div className="card-timeline__body">
            <div className="card-timeline__step">{renderValue(itemField(it, 'step') ?? itemField(it, 'name'))}</div>
            <div className="card-timeline__meta">
              {itemField(it, 'owner') != null && <span>{renderValue(itemField(it, 'owner'))}</span>}
              {itemField(it, 'eta') != null && <span>· {renderValue(itemField(it, 'eta'))}</span>}
            </div>
          </div>
        </div>
      ))}
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
