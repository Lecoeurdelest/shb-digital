// Canvas.tsx — panel phải S2: tab Lobby (live map 2D 4 sub + bảng việc) | Công việc (card render).
// Card từ SSE card / full-state cards[]. Live map = 2D grid placeholder + status dot (D-24, KHÔNG 3D).
// Nội dung card do agent bơm — render defensive (CardRenderer). Look-and-feel tham khảo design/ (D-13).
import { useState } from 'react';
import type { Card, OrchTask } from '../types';
import { CardRenderer } from './cards/CardRenderer';
import type { DecideFn } from './cards/ApprovalPanel';
import { TaskBadge } from './TaskBadge';
import { roleLabel } from '../roles';
import './Canvas.css';

// 4 phòng ban sub (D-24 live map 2D). Main không nằm trong grid sub (là điều phối).
const SUB_ROLES = ['credit', 'legal', 'products', 'ops'] as const;
const ROLE_ICON: Record<string, string> = { credit: '🧮', legal: '⚖', products: '📦', ops: '⚙' };

interface Props {
  cards: Card[];
  tasks: OrchTask[];
  onDecide?: DecideFn;
  onSelectSub?: (taskId: string) => void; // click sub (live map/bảng việc) → mở SubAgentView (F2a)
}

// trạng thái sub từ task mới nhất của role đó (running/done/failed) → dot màu.
function subStatus(tasks: OrchTask[], role: string): OrchTask['status'] | 'idle' {
  const t = tasks.filter((x) => x.role === role).at(-1);
  return t?.status ?? 'idle';
}

const DOT_TONE: Record<string, string> = {
  idle: 'idle', queued: 'run', running: 'run', done: 'pass', failed: 'fail',
};
const STATUS_TEXT: Record<string, string> = {
  idle: '— chờ', queued: '● hàng đợi', running: '● đang làm', done: '✓ xong', failed: '✗ lỗi',
};

// task mới nhất của 1 role (để click node live map → mở sub đó).
function latestTaskOfRole(tasks: OrchTask[], role: string): OrchTask | undefined {
  return tasks.filter((t) => t.role === role).at(-1);
}

export function Canvas({ cards, tasks, onDecide, onSelectSub }: Props) {
  const [tab, setTab] = useState<'lobby' | 'work'>('lobby');
  // citation chip bấm — S2: hiện banner tên tool (tooltip đã có). Trace view mở tool-call = S4.
  const [cited, setCited] = useState<string | null>(null);
  const onCite = (_taskId: string | null, source: string) => setCited(source);

  return (
    <section className="canvas">
      <div className="canvas__tabs">
        <button
          type="button"
          className={`canvas__tab${tab === 'lobby' ? ' canvas__tab--active' : ''}`}
          onClick={() => setTab('lobby')}
        >
          🏛 Đội làm việc
        </button>
        <button
          type="button"
          className={`canvas__tab${tab === 'work' ? ' canvas__tab--active' : ''}`}
          onClick={() => setTab('work')}
        >
          ▦ Công việc{cards.length > 0 ? ` (${cards.length})` : ''}
        </button>
      </div>

      {tab === 'lobby' ? (
        <div className="canvas__lobby">
          {/* live map 2D — 4 sub phòng ban + status dot (D-24) */}
          <div className="livemap" aria-label="Bản đồ đội">
            <div className="livemap__main">◆ Main · điều phối</div>
            <div className="livemap__grid">
              {SUB_ROLES.map((role) => {
                const st = subStatus(tasks, role);
                const tone = DOT_TONE[st] ?? 'idle';
                const task = latestTaskOfRole(tasks, role); // click node có task → mở SubAgentView
                const clickable = !!task && !!onSelectSub;
                return (
                  <div
                    key={role}
                    className={`livemap__node livemap__node--${tone}${clickable ? ' livemap__node--clickable' : ''}`}
                    data-testid={`node-${role}`}
                    onClick={clickable ? () => onSelectSub!(task!.id) : undefined}
                    role={clickable ? 'button' : undefined}
                    tabIndex={clickable ? 0 : undefined}
                    onKeyDown={clickable ? (e) => e.key === 'Enter' && onSelectSub!(task!.id) : undefined}
                  >
                    <span className="livemap__icon">{ROLE_ICON[role]}</span>
                    <span className="livemap__name">{roleLabel(role)}</span>
                    <span className={`status-dot status-dot--${tone}${st === 'running' ? ' deg-pulse' : ''}`} />
                    <span className="livemap__status">{STATUS_TEXT[st] ?? st}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* bảng việc */}
          <div className="canvas__tasks">
            <div className="canvas__tasks-label">BẢNG VIỆC</div>
            {tasks.length === 0 ? (
              <div className="canvas__tasks-empty">Chưa có việc nào được giao.</div>
            ) : (
              <div className="canvas__tasks-list">
                {tasks.map((t) => (
                  <div
                    key={t.id}
                    className={`canvas__task-row${onSelectSub ? ' canvas__task-row--clickable' : ''}`}
                    onClick={onSelectSub ? () => onSelectSub(t.id) : undefined}
                    role={onSelectSub ? 'button' : undefined}
                    tabIndex={onSelectSub ? 0 : undefined}
                    onKeyDown={onSelectSub ? (e) => e.key === 'Enter' && onSelectSub(t.id) : undefined}
                    data-testid={`task-row-${t.id}`}
                  >
                    <TaskBadge task={t} />
                    <span className="canvas__task-title">{t.title}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="canvas__work" data-scroll>
          {cited && (
            <div className="canvas__cite-banner" role="status">
              ⛬ Nguồn: <b>{cited}</b> — trace tool-call đầy đủ ở Sprint 4.
              <button type="button" className="canvas__cite-close" onClick={() => setCited(null)} aria-label="Đóng">✕</button>
            </div>
          )}
          {cards.length === 0 ? (
            <div className="canvas__empty">
              ▦ Sản phẩm công việc (chỉ số · điều kiện · tờ trình…) sẽ hiện ở đây khi đội trình bày.
            </div>
          ) : (
            <div className="canvas__cards">
              {cards.map((card) => (
                <CardRenderer key={card.id} card={card} onCite={onCite} onDecide={onDecide} />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
