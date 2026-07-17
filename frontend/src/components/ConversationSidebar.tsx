// components/ConversationSidebar.tsx — list ca + tạo ca mới (D-14 look-and-feel: chat.jsx ConversationSidebar).
import type { Conversation } from '../types';
import './ConversationSidebar.css';

const STATUS_LABEL: Record<Conversation['status'], { label: string; dot: string }> = {
  idle: { label: 'Mới', dot: 'status-dot' },
  running: { label: 'Đang chạy', dot: 'status-dot status-dot--run deg-pulse' },
  waiting_approval: { label: 'Chờ duyệt', dot: 'status-dot status-dot--warn' },
  done: { label: 'Hoàn tất', dot: 'status-dot status-dot--pass' },
  failed: { label: 'Lỗi', dot: 'status-dot status-dot--fail' },
};

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onOpen: (id: string) => void;
  onNew: () => void;
  creating: boolean;
}

export function ConversationSidebar({ conversations, activeId, onOpen, onNew, creating }: Props) {
  return (
    <aside className="conv-sidebar">
      <button className="conv-sidebar__new" onClick={onNew} disabled={creating} type="button">
        {creating ? 'Đang tạo…' : '+ Ca mới'}
      </button>

      {conversations.length === 0 ? (
        <div className="conv-sidebar__empty">Chưa có ca nào — bấm “+ Ca mới” để bắt đầu.</div>
      ) : (
        <>
          <div className="conv-sidebar__section-label">CA CỦA BẠN</div>
          <div className="conv-sidebar__list">
            {conversations.map((c) => {
              const meta = STATUS_LABEL[c.status] ?? STATUS_LABEL.idle;
              const active = c.id === activeId;
              return (
                <div
                  key={c.id}
                  className={`conv-sidebar__item${active ? ' conv-sidebar__item--active' : ''}`}
                  onClick={() => onOpen(c.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && onOpen(c.id)}
                >
                  <div className="conv-sidebar__title">{c.title}</div>
                  <div className="conv-sidebar__meta">
                    <span className={meta.dot} />
                    {meta.label}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </aside>
  );
}
