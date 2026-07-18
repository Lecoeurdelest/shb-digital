// ModelSelect.tsx — S15 T15-2: chọn provider+model kiểu Claude (1 text-button gọn góc phải-dưới
// composer: "glm-4.6 · zai ˅"). Click → dropdown compact group theo provider (đọc /api/models).
// Dùng CẢ draft (chọn trước, tạo ca kèm) LẪN open-conv (per-turn switch → PATCH). provider has_key=false
// → item disable. Đang running → disabled (BE trả 409 nếu cố).
//
// T15-4 tolerant default: selection KHÔNG BAO GIỜ trỏ provider/model ma. resolveSelection() kẹp về
// hợp lệ: provider hiện tại không có trong list → default:true → thằng đầu list; model không thuộc
// provider → model[0]. Áp cho cả default top-level lẫn ca có provider/model cũ đã biến mất khỏi list.
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { conversationApi } from '../api';
import type { Provider } from '../types';
import './ModelSelect.css';

interface Props {
  provider: string;
  model: string;
  onChange: (provider: string, model: string) => void;
  disabled?: boolean;
  // draft: chưa có provider → tự chọn default (giữ hành vi ModelPicker cũ). open-conv: đã có sẵn.
  autoDefault?: boolean;
}

// T15-4: kẹp (provider, model) về lựa chọn HỢP LỆ trong list. Trả null nếu list rỗng.
// - provider không có trong list (hoặc rỗng) → provider default:true → provider đầu list.
// - model không thuộc provider đã kẹp → model[0] của provider đó.
function resolveSelection(
  list: Provider[],
  provider: string,
  model: string,
): { provider: string; model: string } | null {
  if (list.length === 0) return null;
  const p = list.find((x) => x.name === provider)
    ?? list.find((x) => x.default)
    ?? list[0];
  const models = p.models ?? [];
  const m = models.includes(model) ? model : (models[0] ?? '');
  return { provider: p.name, model: m };
}

export function ModelSelect({ provider, model, onChange, disabled, autoDefault }: Props) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ left: number; bottom: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const dropRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let alive = true;
    conversationApi
      .getModels()
      .then((res) => {
        if (!alive) return;
        const list = Array.isArray(res.providers) ? res.providers : [];
        setProviders(list);
        setError(null);
        // draft (autoDefault): chưa chọn provider → chọn default response (kẹp qua resolveSelection).
        // T15-4: default response không có trong list → resolveSelection fallback default:true / đầu list.
        if (autoDefault && !provider && list.length > 0) {
          const sel = resolveSelection(list, res.default, '');
          if (sel) onChange(sel.provider, sel.model);
        }
      })
      .catch(() => { if (alive) setError('mặc định máy chủ'); });
    return () => { alive = false; };
    // 1 lần lúc mount — provider/onChange KHÔNG vào deps (tránh refetch vòng lặp, như ModelPicker cũ).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // đóng dropdown: click ngoài (dual-ref vì portal) + Esc.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (btnRef.current?.contains(t) || dropRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (error) return <span className="msel__fallback" title="Không tải được model — dùng mặc định máy chủ">⚙ {error}</span>;
  if (providers.length === 0) return null;

  // T15-4: hiển thị theo selection ĐÃ KẸP (không render provider/model ma nếu list đổi).
  const sel = resolveSelection(providers, provider, model);
  if (!sel) return null;
  const label = sel.model ? `${sel.model} · ${sel.provider}` : sel.provider;

  const openMenu = () => {
    if (disabled) return;
    const b = btnRef.current?.getBoundingClientRect();
    if (b) setPos({ left: b.left, bottom: window.innerHeight - b.top + 6 }); // menu nổi LÊN trên nút
    setOpen((v) => !v);
  };

  const pick = (p: Provider, m: string) => {
    setOpen(false);
    onChange(p.name, m);
  };

  return (
    <div className="msel">
      <button
        ref={btnRef}
        type="button"
        className="msel__btn"
        onClick={openMenu}
        disabled={disabled}
        aria-label="Chọn model"
        data-testid="model-select-btn"
        title={disabled ? 'Ca đang chạy — không đổi model giữa lượt' : 'Đổi provider / model'}
      >
        <span className="msel__label">{label}</span>
        <span className="msel__caret" aria-hidden="true">˅</span>
      </button>
      {open && pos && createPortal(
        <div
          className="msel__menu"
          role="menu"
          ref={dropRef}
          style={{ left: pos.left, bottom: pos.bottom }}
          data-testid="model-select-menu"
        >
          {providers.map((p) => (
            <div key={p.name} className="msel__group">
              <div className="msel__group-head">
                {p.name}{p.default ? ' ★' : ''}{p.has_key ? '' : ' · thiếu key'}
              </div>
              {(p.models ?? []).map((m) => {
                const active = p.name === sel.provider && m === sel.model;
                return (
                  <button
                    key={`${p.name}/${m}`}
                    type="button"
                    className={`msel__item${active ? ' msel__item--active' : ''}`}
                    disabled={!p.has_key}
                    onClick={() => pick(p, m)}
                    data-testid={`model-opt-${p.name}-${m}`}
                  >
                    {m}{active ? ' ✓' : ''}
                  </button>
                );
              })}
            </div>
          ))}
        </div>,
        document.body,
      )}
    </div>
  );
}
