// FormCard.tsx — card type 'form' (D-57 T9-3): khách MỚI điền hồ sơ trên canvas (WIDE, panel phải).
// Fields SERVER định nghĩa (card.data.fields) — FE render ĐÚNG theo, KHÔNG hardcode. Nộp → form-submit.
// status='submitted' (SSE update / reload) → read-only "đã nộp". Defensive: fields rỗng → fallback.
import { useState } from 'react';
import type { Card, FormField } from '../../types';
import { cardField } from './cardUtil';
import './FormCard.css';

export type FormSubmitFn = (cardId: string, values: Record<string, string>) => Promise<void>;

// đọc fields defensive: đúng shape {name,label,type,required} mới nhận; loại field lạ.
function readFields(card: Card): FormField[] {
  const raw = cardField<unknown[]>(card, 'fields');
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (f): f is FormField =>
      !!f && typeof f === 'object' && typeof (f as FormField).name === 'string' && typeof (f as FormField).label === 'string',
  );
}

function formStatus(card: Card): string {
  return String(cardField<string>(card, 'status') ?? 'pending');
}

interface FormCardProps {
  card: Card;
  onSubmit?: FormSubmitFn;
  // DF-A-04: values NÂNG lên caller (Workspace) để sống qua đổi tab canvas (FormCard unmount khi
  // đổi tab → local state chết). Nếu caller quản lý (draftValues + onDraftChange) → dùng; nếu không
  // (test standalone) → local state fallback. busy/error/missing giữ local (không cần sống qua tab).
  draftValues?: Record<string, string>;
  onDraftChange?: (cardId: string, values: Record<string, string>) => void;
}

export function FormCard({ card, onSubmit, draftValues, onDraftChange }: FormCardProps) {
  const fields = readFields(card);
  const status = formStatus(card);
  const submitted = status === 'submitted';

  const [localValues, setLocalValues] = useState<Record<string, string>>({});
  const managed = draftValues !== undefined && onDraftChange !== undefined;
  const values = managed ? draftValues : localValues;
  const setValues = (next: Record<string, string>) => {
    if (managed) onDraftChange!(card.id, next);
    else setLocalValues(next);
  };
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState<Set<string>>(new Set());

  if (fields.length === 0) {
    return <div className="formcard__invalid" data-testid="form-invalid">Form hồ sơ không hợp lệ (thiếu định nghĩa trường).</div>;
  }

  const submit = () => {
    if (!onSubmit || busy || submitted) return;
    // validate client-side (server vẫn validate lại — đây chỉ UX sớm): required trống → highlight
    const req = fields.filter((f) => f.required).map((f) => f.name);
    const miss = new Set(req.filter((n) => !String(values[n] ?? '').trim()));
    if (miss.size > 0) {
      setMissing(miss);
      setError('Vui lòng điền đủ các trường bắt buộc.');
      return;
    }
    setMissing(new Set());
    setBusy(true);
    setError(null);
    onSubmit(card.id, values)
      .then(() => { /* SSE card update → status submitted → re-render read-only */ })
      .catch((e: unknown) => {
        // lỗi từ body 4-field (missing_fields/bad_income/409) → message; 409 để SSE/reload lo read-only
        const msg = e instanceof Error ? e.message : 'Nộp hồ sơ thất bại';
        setError(msg);
      })
      .finally(() => setBusy(false));
  };

  return (
    <div className="formcard" data-testid="form-card">
      {submitted ? (
        <div className="formcard__done" data-testid="form-submitted">
          ✅ Đã nộp hồ sơ — hệ thống đang xử lý thẩm định.
        </div>
      ) : (
        <>
          <div className="formcard__fields">
            {fields.map((f) => (
              <label key={f.name} className={`formcard__field${missing.has(f.name) ? ' formcard__field--missing' : ''}`}>
                <span className="formcard__label">
                  {f.label}{f.required && <span className="formcard__req"> *</span>}
                </span>
                <input
                  className="formcard__input"
                  type={f.type === 'number' ? 'number' : 'text'}
                  value={values[f.name] ?? ''}
                  disabled={busy}
                  aria-label={f.label}
                  onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
                />
              </label>
            ))}
          </div>
          {error && <div className="formcard__error" role="alert">{error}</div>}
          <button
            type="button"
            className="btn btn--primary formcard__submit"
            onClick={submit}
            disabled={busy || !onSubmit}
            data-testid="form-submit"
          >
            {busy ? 'Đang nộp…' : 'Nộp hồ sơ'}
          </button>
        </>
      )}
    </div>
  );
}
