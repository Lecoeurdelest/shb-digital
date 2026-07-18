// Canvas.tsx — panel phải: tab Đội làm việc (constellation spatial-2D 4 sub + bảng việc) | Công việc (cards).
// Constellation (D-53): Main giữa + 4 sub tỏa góc + đường nối chấm SVG + status dot — CSS/SVG THUẦN,
// KHÔNG three.js (D-24 3D vẫn hoãn). Card từ SSE/full-state, render defensive. Look-and-feel: design/ (D-13).
import { useState } from 'react';
import type { Card, OrchTask } from '../types';
import { CardRenderer } from './cards/CardRenderer';
import type { DecideFn } from './cards/ApprovalPanel';
import { TaskBadge } from './TaskBadge';
import { roleLabel } from '../roles';
import './Canvas.css';

// 4 phòng ban sub (D-24 live map 2D → spatial constellation D-53, CSS/SVG thuần, KHÔNG three.js).
// Mỗi sub có toạ độ % quanh Main (giữa) — Main tỏa đường nối chấm ra 4 góc chéo.
const ROLE_ICON: Record<string, string> = { credit: '🧮', legal: '⚖', products: '📦', ops: '⚙' };
// vị trí node trên khung constellation (% — x,y). 4 góc chéo cân đối quanh Main (50,50).
const SUB_LAYOUT = [
  { role: 'credit', x: 24, y: 26 },   // trên-trái
  { role: 'legal', x: 76, y: 26 },    // trên-phải
  { role: 'products', x: 76, y: 74 },  // dưới-phải
  { role: 'ops', x: 24, y: 74 },       // dưới-trái
] as const;

interface Props {
  cards: Card[];
  tasks: OrchTask[];
  onDecide?: DecideFn;
  canDecide?: boolean; // D-56 — chỉ admin (ngân hàng) quyết phiếu; customer thấy "chờ ngân hàng"
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

export function Canvas({ cards, tasks, onDecide, canDecide, onSelectSub }: Props) {
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
          {/* constellation — Main giữa + 4 sub tỏa góc + đường nối chấm (SVG). D-53, CSS/SVG thuần. */}
          <div className="constel" aria-label="Bản đồ đội — sơ đồ không gian">
            {/* lớp đường nối: Main(50,50) → mỗi sub. dasharray = chấm; màu theo tone active. */}
            <svg className="constel__links" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              {SUB_LAYOUT.map(({ role, x, y }) => {
                const st = subStatus(tasks, role);
                const active = st === 'running' || st === 'queued';
                return (
                  <line
                    key={role}
                    x1="50" y1="50" x2={x} y2={y}
                    className={`constel__link${active ? ' constel__link--active' : ''}`}
                  />
                );
              })}
            </svg>

            {/* Main — tâm điều phối */}
            <div className="constel__main" style={{ left: '50%', top: '50%' }}>
              <span className="constel__main-icon">◆</span>
              <span className="constel__main-name">Main</span>
              <span className="constel__main-desc">điều phối · hòa giải</span>
            </div>

            {/* 4 sub node tỏa góc */}
            {SUB_LAYOUT.map(({ role, x, y }) => {
              const st = subStatus(tasks, role);
              const tone = DOT_TONE[st] ?? 'idle';
              const task = latestTaskOfRole(tasks, role); // click node có task → mở SubAgentView
              const clickable = !!task && !!onSelectSub;
              return (
                <div
                  key={role}
                  className={`constel__node constel__node--${tone}${clickable ? ' constel__node--clickable' : ''}`}
                  style={{ left: `${x}%`, top: `${y}%` }}
                  data-testid={`node-${role}`}
                  onClick={clickable ? () => onSelectSub!(task!.id) : undefined}
                  role={clickable ? 'button' : undefined}
                  tabIndex={clickable ? 0 : undefined}
                  onKeyDown={clickable ? (e) => e.key === 'Enter' && onSelectSub!(task!.id) : undefined}
                >
                  <span className="constel__icon">{ROLE_ICON[role]}</span>
                  <span className="constel__name">{roleLabel(role)}</span>
                  <span className="constel__meta">
                    <span className={`status-dot status-dot--${tone}${st === 'running' ? ' deg-pulse' : ''}`} />
                    <span className="constel__status">{STATUS_TEXT[st] ?? st}</span>
                  </span>
                </div>
              );
            })}
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
                <CardRenderer key={card.id} card={card} onCite={onCite} onDecide={onDecide} canDecide={canDecide} />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
