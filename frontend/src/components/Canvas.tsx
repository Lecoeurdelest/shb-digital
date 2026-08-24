// Canvas.tsx — panel phải của Phiên xử lý (D-75): sản phẩm công việc là mặc định; tiến độ nghiệp vụ
// là tab phụ. Không mở raw task/telemetry từ bề mặt RM/khách hàng.
import { useState } from 'react';
import type { Card, OrchTask } from '../types';
import { CardRenderer } from './cards/CardRenderer';
import { sourceLabel } from './cards/sourceLabels';
import type { FormSubmitFn } from './cards/FormCard';
import { TaskBadge } from './TaskBadge';
import './Canvas.css';

interface Props {
  cards: Card[];
  tasks: OrchTask[];
  onInterruptTask?: (taskId: string) => Promise<void> | void;
  onFormSubmit?: FormSubmitFn; // T9-3 — khách nộp hồ sơ (card type 'form')
  formDrafts?: Record<string, Record<string, string>>; // DF-A-04 — form values sống qua đổi tab
  onFormDraftChange?: (cardId: string, values: Record<string, string>) => void;
}

export function Canvas({ cards, tasks, onInterruptTask, onFormSubmit, formDrafts, onFormDraftChange }: Props) {
  const [tab, setTab] = useState<'work' | 'progress'>('work');
  const [cited, setCited] = useState<string | null>(null);
  const [interruptingTaskId, setInterruptingTaskId] = useState<string | null>(null);
  const onCite = (_taskId: string | null, source: string) => setCited(sourceLabel(source));
  const hasPendingIntakeForm = cards.some((card) => card.type === 'form' && card.status !== 'submitted');

  const interruptTask = async (taskId: string) => {
    if (!onInterruptTask || interruptingTaskId) return;
    setInterruptingTaskId(taskId);
    try {
      await onInterruptTask(taskId);
    } finally {
      setInterruptingTaskId(null);
    }
  };

  return (
    <section className="canvas">
      <div className="canvas__tabs" role="tablist" aria-label="Nội dung phiên xử lý">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'work'}
          className={`canvas__tab${tab === 'work' ? ' canvas__tab--active' : ''}`}
          onClick={() => setTab('work')}
        >
          ▦ Sản phẩm công việc{cards.length > 0 ? ` (${cards.length})` : ''}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'progress'}
          className={`canvas__tab${tab === 'progress' ? ' canvas__tab--active' : ''}`}
          onClick={() => setTab('progress')}
        >
          ◷ Tiến độ xử lý{tasks.length > 0 ? ` (${tasks.length})` : ''}
        </button>
      </div>

      {tab === 'work' ? (
        <div className="canvas__work" data-scroll role="tabpanel">
          {cited && (
            <div className="canvas__cite-banner" role="status">
              ⛬ Nguồn nghiệp vụ: <b>{cited}</b>. Chi tiết được lưu trong nhật ký kiểm soát.
              <button type="button" className="canvas__cite-close" onClick={() => setCited(null)} aria-label="Đóng">✕</button>
            </div>
          )}
          {cards.length === 0 ? (
            <div className="canvas__empty">
              ▦ Các chỉ số, điều kiện và tờ trình sẽ xuất hiện tại đây sau khi xử lý.
            </div>
          ) : (
            <div className="canvas__cards">
              {cards.map((card) => (
                <CardRenderer key={card.id} card={card} onCite={onCite} canDecide={false} onFormSubmit={onFormSubmit}
                  formDrafts={formDrafts} onFormDraftChange={onFormDraftChange} />
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="canvas__progress" data-scroll role="tabpanel" aria-label="Tiến độ xử lý">
          <div className="canvas__tasks">
            <div className="canvas__tasks-label">CÁC BƯỚC XỬ LÝ</div>
            {tasks.length === 0 ? (
              <div className="canvas__tasks-empty">
                Chưa có bước xử lý nào.
                {hasPendingIntakeForm && (
                  <span className="canvas__tasks-empty-hint">
                    Điền và gửi hồ sơ ở Sản phẩm công việc để bắt đầu thẩm định.
                  </span>
                )}
              </div>
            ) : (
              <div className="canvas__tasks-list">
                {tasks.map((t) => (
                  <div key={t.id} className="canvas__task-row" data-testid={`task-row-${t.id}`}>
                    <TaskBadge task={t} />
                    <span className="canvas__task-title">{t.title}</span>
                    {(t.status === 'queued' || t.status === 'running') && onInterruptTask && (
                      <button
                        type="button"
                        className="canvas__task-stop"
                        data-testid={`task-stop-${t.id}`}
                        disabled={interruptingTaskId !== null}
                        onClick={() => void interruptTask(t.id)}
                      >
                        {interruptingTaskId === t.id ? 'Đang dừng…' : 'Dừng bước'}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
