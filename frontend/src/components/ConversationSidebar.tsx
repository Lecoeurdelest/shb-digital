// components/ConversationSidebar.tsx — list ca + tạo ca mới (D-14 look-and-feel: chat.jsx).
// S15 T15-3: mỗi ca có rename inline (✎ → input → Enter/blur lưu) + delete 2-bước (🗑 → confirm
// nhỏ "Xoá ca? [Xoá][Huỷ]" — CẤM window.confirm, pattern B-07). showActions=false → ẩn (không đủ quyền).
import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react';
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
  // T15-3: CRUD (optional — chỉ hiện khi có quyền + handler). showActions=false → không render nút.
  onRename?: (id: string, title: string) => void;
  onDelete?: (id: string) => void;
  showActions?: boolean;
}

export function ConversationSidebar({ conversations, activeId, onOpen, onNew, creating, onRename, onDelete, showActions }: Props) {
  const canAct = showActions && !!onRename && !!onDelete;
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
            {conversations.map((c) => (
              <ConversationRow
                key={c.id}
                conv={c}
                active={c.id === activeId}
                onOpen={onOpen}
                onRename={onRename}
                onDelete={onDelete}
                canAct={!!canAct}
              />
            ))}
          </div>
        </>
      )}
    </aside>
  );
}

function ConversationRow({
  conv, active, onOpen, onRename, onDelete, canAct,
}: {
  conv: Conversation;
  active: boolean;
  onOpen: (id: string) => void;
  onRename?: (id: string, title: string) => void;
  onDelete?: (id: string) => void;
  canAct: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(conv.title);
  const [confirming, setConfirming] = useState(false); // delete 2-bước
  const inputRef = useRef<HTMLInputElement | null>(null);
  const meta = STATUS_LABEL[conv.status] ?? STATUS_LABEL.idle;

  useEffect(() => {
    if (editing) { setDraft(conv.title); inputRef.current?.focus(); inputRef.current?.select(); }
  }, [editing, conv.title]);

  // trap #3: mọi control bên trong row (div role=button) phải chặn bubble → không mở/đổi ca ngoài ý.
  const stop = (e: { stopPropagation: () => void }) => e.stopPropagation();

  const startEdit = (e: ReactMouseEvent) => { stop(e); setConfirming(false); setEditing(true); };
  const commitEdit = () => {
    setEditing(false);
    if (draft.trim() && draft.trim() !== conv.title) onRename?.(conv.id, draft.trim());
  };
  const cancelEdit = () => { setEditing(false); setDraft(conv.title); };

  const askDelete = (e: ReactMouseEvent) => { stop(e); setEditing(false); setConfirming(true); };
  const confirmDelete = (e: ReactMouseEvent) => { stop(e); setConfirming(false); onDelete?.(conv.id); };
  const cancelDelete = (e: ReactMouseEvent) => { stop(e); setConfirming(false); };

  return (
    <div
      className={`conv-sidebar__item${active ? ' conv-sidebar__item--active' : ''}`}
      onClick={() => { if (!editing) onOpen(conv.id); }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' && !editing) onOpen(conv.id); }}
      data-testid={`conv-item-${conv.id}`}
    >
      {editing ? (
        <input
          ref={inputRef}
          className="conv-sidebar__rename"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onClick={stop}
          onKeyDown={(e) => {
            stop(e); // Enter trong input KHÔNG được kích onKeyDown của div (mở ca) — trap #3
            if (e.key === 'Enter') commitEdit();
            else if (e.key === 'Escape') cancelEdit();
          }}
          onBlur={commitEdit}
          aria-label="Đổi tên ca"
          data-testid={`conv-rename-${conv.id}`}
        />
      ) : (
        <div className="conv-sidebar__title-row">
          <div className="conv-sidebar__title">{conv.title}</div>
          {canAct && !confirming && (
            <div className="conv-sidebar__actions">
              <button type="button" className="conv-sidebar__act" onClick={startEdit}
                aria-label="Đổi tên ca" title="Đổi tên" data-testid={`conv-edit-${conv.id}`}>✎</button>
              <button type="button" className="conv-sidebar__act conv-sidebar__act--del" onClick={askDelete}
                aria-label="Xoá ca" title="Xoá" data-testid={`conv-del-${conv.id}`}>🗑</button>
            </div>
          )}
        </div>
      )}

      {!editing && (
        <div className="conv-sidebar__meta">
          <span className={meta.dot} />
          {meta.label}
        </div>
      )}

      {confirming && (
        <div className="conv-sidebar__confirm" data-testid={`conv-confirm-${conv.id}`} onClick={stop}>
          <span className="conv-sidebar__confirm-q">Xoá ca này?</span>
          <button type="button" className="conv-sidebar__confirm-yes" onClick={confirmDelete}
            data-testid={`conv-del-yes-${conv.id}`}>Xoá</button>
          <button type="button" className="conv-sidebar__confirm-no" onClick={cancelDelete}>Huỷ</button>
        </div>
      )}
    </div>
  );
}
