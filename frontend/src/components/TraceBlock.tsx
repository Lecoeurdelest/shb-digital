// TraceBlock.tsx — khối trace collapsible trong chat (F1 · D-43 user track). Gom thinking +
// toolcall theo lượt → dòng trace (🧠 thinking / 🔧 tool + summary), MẶC ĐỊNH THU GỌN, click mở.
// Đơn giản (user: "tạm, tracing dễ"). Defensive N3: thinking dài line-clamp, không item → không hiện.
import { useState } from 'react';
import type { TraceItem } from '../types';
import { roleLabel } from '../roles';
import './TraceBlock.css';

// task_id → tên actor. main (task_id null) = điều phối; task_id khác → role của task đó (nếu biết).
function actorLabel(taskId: string | null, taskRole?: string): string {
  if (taskId == null) return 'Main';
  return taskRole ? roleLabel(taskRole) : 'Sub';
}

interface Props {
  items: TraceItem[];
  // map task_id → role (từ tasks) để hiện tên actor đúng; optional.
  taskRole?: (taskId: string) => string | undefined;
}

export function TraceBlock({ items, taskRole }: Props) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null; // không trace → không hiện khối rỗng (defensive)

  const nTool = items.filter((i) => i.kind === 'tool').length;
  const nThink = items.filter((i) => i.kind === 'thinking').length;

  return (
    <div className="trace" data-testid="trace-block">
      <button
        type="button"
        className="trace__toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className={`trace__caret${open ? ' trace__caret--open' : ''}`}>▸</span>
        <span className="trace__label">
          Diễn tiến đội — {items.length} bước
          {nTool > 0 && <span className="trace__count"> · 🔧 {nTool}</span>}
          {nThink > 0 && <span className="trace__count"> · 🧠 {nThink}</span>}
        </span>
      </button>

      {open && (
        <div className="trace__body">
          {items.map((it, i) => {
            const actor = actorLabel(it.task_id, it.task_id ? taskRole?.(it.task_id) : undefined);
            // key = id + index: toolcall id unique (dedup); thinking id có thể trùng ts → index bảo unique.
            const key = `${it.id}-${i}`;
            if (it.kind === 'thinking') {
              return (
                <div key={key} className="trace__row trace__row--think">
                  <span className="trace__icon" aria-hidden="true">🧠</span>
                  <span className="trace__actor">{actor}</span>
                  <span className="trace__text trace__text--clamp">{it.text}</span>
                </div>
              );
            }
            return (
              <div key={key} className="trace__row trace__row--tool">
                <span className="trace__icon" aria-hidden="true">🔧</span>
                <span className="trace__actor">{actor}</span>
                <code className="trace__tool">{it.tool}</code>
                {it.summary && <span className="trace__text trace__text--clamp">{it.summary}</span>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
