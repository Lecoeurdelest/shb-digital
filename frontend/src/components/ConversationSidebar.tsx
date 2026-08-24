// components/ConversationSidebar.tsx — danh sách Phiên xử lý (D-75) + CRUD inline.
import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react';
import type { Conversation, ConversationGroup } from '../types';
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
  groups?: ConversationGroup[];
  activeId: string | null;
  onOpen: (id: string) => void;
  onNew: () => void;
  creating: boolean;
  // T15-3: CRUD (optional — chỉ hiện khi có quyền + handler). showActions=false → không render nút.
  onRename?: (id: string, title: string) => void;
  onDelete?: (id: string) => void;
  showActions?: boolean;
  onCreateGroup?: (name: string) => Promise<void> | void;
  onMoveConversation?: (id: string, groupId: string | null) => void;
}

export function ConversationSidebar({
  conversations,
  groups = [],
  activeId,
  onOpen,
  onNew,
  creating,
  onRename,
  onDelete,
  showActions,
  onCreateGroup,
  onMoveConversation,
}: Props) {
  const canAct = showActions && !!onRename && !!onDelete;
  const [addingGroup, setAddingGroup] = useState(false);
  const [groupDraft, setGroupDraft] = useState('');
  const [savingGroup, setSavingGroup] = useState(false);

  const commitGroup = async () => {
    const name = groupDraft.trim();
    if (!name || !onCreateGroup || savingGroup) return;
    setSavingGroup(true);
    try {
      await onCreateGroup(name);
      setGroupDraft('');
      setAddingGroup(false);
    } catch {
      // Controller đã đưa lỗi API lên banner; giữ input để người dùng sửa/thử lại.
    } finally {
      setSavingGroup(false);
    }
  };

  const rows = (items: Conversation[]) => items.map((c) => (
    <ConversationRow
      key={c.id}
      conv={c}
      groups={groups}
      active={c.id === activeId}
      onOpen={onOpen}
      onRename={onRename}
      onDelete={onDelete}
      onMoveConversation={onMoveConversation}
      canAct={!!canAct}
    />
  ));

  return (
    <aside className="conv-sidebar">
      <button className="conv-sidebar__new" onClick={onNew} disabled={creating} type="button">
        {creating ? 'Đang tạo…' : '+ Phiên xử lý'}
      </button>

      {onCreateGroup && (
        <div className="conv-sidebar__group-create">
          {addingGroup ? (
            <input
              autoFocus
              className="conv-sidebar__group-input"
              value={groupDraft}
              maxLength={80}
              onChange={(event) => setGroupDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void commitGroup();
                if (event.key === 'Escape') { setAddingGroup(false); setGroupDraft(''); }
              }}
              onBlur={() => { if (!groupDraft.trim()) setAddingGroup(false); }}
              placeholder="Tên nhóm"
              aria-label="Tên nhóm phiên xử lý"
            />
          ) : (
            <button type="button" className="conv-sidebar__add-group" onClick={() => setAddingGroup(true)}>
              + Nhóm
            </button>
          )}
        </div>
      )}

      {conversations.length === 0 ? (
        <div className="conv-sidebar__empty">Chưa có phiên xử lý nào — bấm “+ Phiên xử lý” để bắt đầu.</div>
      ) : (
        <>
          <div className="conv-sidebar__section-label">PHIÊN XỬ LÝ CỦA BẠN</div>
          <div className="conv-sidebar__list">
            {groups.length === 0 ? rows(conversations) : (
              <>
                {groups.map((group) => {
                  const items = conversations.filter((conv) => conv.group_id === group.id);
                  return (
                    <section className="conv-sidebar__group" key={group.id} aria-label={`Nhóm ${group.name}`}>
                      <div className="conv-sidebar__group-label">{group.name}</div>
                      {items.length > 0 ? rows(items) : <div className="conv-sidebar__group-empty">Chưa có phiên</div>}
                    </section>
                  );
                })}
                <section className="conv-sidebar__group" aria-label="Chưa phân nhóm">
                  <div className="conv-sidebar__group-label">Chưa phân nhóm</div>
                  {rows(conversations.filter((conv) => !conv.group_id))}
                </section>
              </>
            )}
          </div>
        </>
      )}
    </aside>
  );
}

function ConversationRow({
  conv, active, onOpen, onRename, onDelete, canAct,
  groups, onMoveConversation,
}: {
  conv: Conversation;
  groups: ConversationGroup[];
  active: boolean;
  onOpen: (id: string) => void;
  onRename?: (id: string, title: string) => void;
  onDelete?: (id: string) => void;
  onMoveConversation?: (id: string, groupId: string | null) => void;
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
          aria-label="Đổi tên phiên xử lý"
          data-testid={`conv-rename-${conv.id}`}
        />
      ) : (
        <div className="conv-sidebar__title-row">
          <div className="conv-sidebar__title">{conv.title}</div>
          {canAct && !confirming && (
            <div className="conv-sidebar__actions">
              <button type="button" className="conv-sidebar__act" onClick={startEdit}
                aria-label="Đổi tên phiên xử lý" title="Đổi tên" data-testid={`conv-edit-${conv.id}`}>✎</button>
              <button type="button" className="conv-sidebar__act conv-sidebar__act--del" onClick={askDelete}
                aria-label="Xoá phiên xử lý" title="Xoá" data-testid={`conv-del-${conv.id}`}>🗑</button>
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

      {!editing && onMoveConversation && groups.length > 0 && (
        <select
          className="conv-sidebar__group-select"
          value={conv.group_id ?? ''}
          onClick={stop}
          onChange={(event) => {
            stop(event);
            onMoveConversation(conv.id, event.target.value || null);
          }}
          aria-label={`Nhóm của ${conv.title}`}
        >
          <option value="">Chưa phân nhóm</option>
          {groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
        </select>
      )}

      {confirming && (
        <div className="conv-sidebar__confirm" data-testid={`conv-confirm-${conv.id}`} onClick={stop}>
          <span className="conv-sidebar__confirm-q">Xoá phiên xử lý này?</span>
          <button type="button" className="conv-sidebar__confirm-yes" onClick={confirmDelete}
            data-testid={`conv-del-yes-${conv.id}`}>Xoá</button>
          <button type="button" className="conv-sidebar__confirm-no" onClick={cancelDelete}>Huỷ</button>
        </div>
      )}
    </div>
  );
}
