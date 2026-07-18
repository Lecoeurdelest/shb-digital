// Canvas.tsx — panel phải: tab Đội làm việc (lobby 3D chi nhánh BANK + bảng việc) | Công việc (cards).
// Lobby 3D (D-24 ĐÓNG — thay constellation D-53, người chốt 18/7): three.js, scene tĩnh render-on-demand,
// agent 'run' → icon nhấp nháy trên đầu. Card từ SSE/full-state, render defensive. Look-and-feel: design/ (D-13).
import { useState } from 'react';
import type { Card, OrchTask } from '../types';
import { CardRenderer } from './cards/CardRenderer';
import type { DecideFn } from './cards/ApprovalPanel';
import type { FormSubmitFn } from './cards/FormCard';
import { TaskBadge } from './TaskBadge';
import { Lobby3D, type LobbyStatus } from './Lobby3D';
import './Canvas.css';

// 4 phòng ban sub. Main không nằm trong grid sub (là điều phối).
const SUB_ROLES = ['credit', 'legal', 'products', 'ops'] as const;

interface Props {
  cards: Card[];
  tasks: OrchTask[];
  onDecide?: DecideFn;
  canDecide?: boolean; // D-56 — chỉ admin (ngân hàng) quyết phiếu; customer thấy "chờ ngân hàng"
  onFormSubmit?: FormSubmitFn; // T9-3 — khách nộp hồ sơ (card type 'form')
  formDrafts?: Record<string, Record<string, string>>; // DF-A-04 — form values sống qua đổi tab
  onFormDraftChange?: (cardId: string, values: Record<string, string>) => void;
  onSelectSub?: (taskId: string) => void; // click sub (live map/bảng việc) → mở SubAgentView (F2a)
}

// trạng thái sub từ task mới nhất của role đó (running/done/failed) → dot màu.
function subStatus(tasks: OrchTask[], role: string): OrchTask['status'] | 'idle' {
  const t = tasks.filter((x) => x.role === role).at(-1);
  return t?.status ?? 'idle';
}

// task mới nhất của 1 role (để click nhân vật lobby → mở sub đó).
function latestTaskOfRole(tasks: OrchTask[], role: string): OrchTask | undefined {
  return tasks.filter((t) => t.role === role).at(-1);
}

export function Canvas({ cards, tasks, onDecide, canDecide, onFormSubmit, formDrafts, onFormDraftChange, onSelectSub }: Props) {
  const [tab, setTab] = useState<'lobby' | 'work'>('lobby');
  // citation chip bấm — S2: hiện banner tên tool (tooltip đã có). Trace view mở tool-call = S4.
  const [cited, setCited] = useState<string | null>(null);
  const onCite = (_taskId: string | null, source: string) => setCited(source);

  // trạng thái từng agent cho lobby 3D (map TaskStatus → trạng thái hiển thị); Main 'run' nếu có sub chạy
  const agentStatus = (role: string): LobbyStatus => {
    const st = subStatus(tasks, role);
    return st === 'running' || st === 'queued' ? 'run' : st === 'done' ? 'done' : st === 'failed' ? 'err' : 'idle';
  };
  const subStates = SUB_ROLES.map(agentStatus);
  const agents: Record<string, LobbyStatus> = {
    planner: subStates.includes('run') ? 'run' : subStates.includes('done') ? 'done' : 'idle',
    credit: agentStatus('credit'), legal: agentStatus('legal'), products: agentStatus('products'), ops: agentStatus('ops'),
  };
  const handleSelectRole = (role: string) => {
    const task = latestTaskOfRole(tasks, role);
    if (task && onSelectSub) onSelectSub(task.id);
  };

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
          {/* live map 3D — chi nhánh BANK (D-24 lobby-3D): click nhân vật → mở SubAgentView */}
          <Lobby3D agents={agents} onSelect={handleSelectRole} />

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
                <CardRenderer key={card.id} card={card} onCite={onCite} onDecide={onDecide} canDecide={canDecide} onFormSubmit={onFormSubmit}
                  formDrafts={formDrafts} onFormDraftChange={onFormDraftChange} />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
