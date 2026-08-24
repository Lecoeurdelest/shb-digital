// Workspace.tsx — bề mặt nghiệp vụ cho một Phiên xử lý (D-75): danh sách phiên | trao đổi/yêu cầu |
// sản phẩm công việc và tiến độ. Runtime/SSE/card/nguồn/phanh duyệt giữ nguyên, telemetry kỹ thuật
// không được trình bày cho RM/khách hàng.

import { useEffect, useRef } from 'react';
import { USE_MOCK_API } from './api';
import { useWorkspaceController } from './hooks/useWorkspaceController';
import { NotificationBell } from './components/NotificationBell';
import { ThemeToggle } from './components/ThemeToggle';
import { ConversationSidebar } from './components/ConversationSidebar';
import { Composer } from './components/Composer';
import { MessageBubble, StreamingMessageBubble } from './components/MessageBubble';
import { Canvas } from './components/Canvas';
import { roleLabel } from './roles';
import type { AuthUser, ConversationStatus } from './types';
import './App.css';

const CONV_STATUS_LABEL: Record<ConversationStatus, string> = {
  idle: 'Sẵn sàng',
  running: 'Đang xử lý…',
  waiting_approval: 'Chờ phê duyệt',
  done: 'Hoàn tất',
  failed: 'Lỗi',
};

const ROLE_LABEL_USER: Record<AuthUser['role'], string> = { customer: 'Khách hàng', user: 'RM', admin: 'Quản lý' };

interface Props {
  user: AuthUser;
  onAuthExpired: () => void;
  onOpenTower?: () => void; // admin: mở Control Tower (D-19)
  initialConversationId?: string | null;
  onInitialConversationHandled?: (conversationId: string) => void;
}

export function Workspace({
  user,
  onAuthExpired,
  onOpenTower,
  initialConversationId,
  onInitialConversationHandled,
}: Props) {
  const {
    conversations, conversationGroups, activeId, messages, tasks, cards,
    convStatus, streaming, creating, drafting, formDrafts,
    loadError, listError, scrollRef,
    openConversation, startDraft, sendChat, handleInterruptTask, handleFormDraftChange,
    handleFormSubmit, handleRename, handleDelete, handleCreateGroup, handleMoveConversation, handleLogout,
    activeConv, busy, hasContent, pendingApprovals,
  } = useWorkspaceController({ user, onAuthExpired });

  // D-77: handoff từ case read-model chỉ mở resource đã tồn tại. Ref chặn StrictMode/rerender
  // gọi lại; App xóa handoff ngay sau khi Workspace đã nhận. Không create/send/auto-run ở đây.
  const handledInitialConversation = useRef<string | null>(null);
  useEffect(() => {
    const conversationId = initialConversationId?.trim();
    if (!conversationId || handledInitialConversation.current === conversationId) return;
    handledInitialConversation.current = conversationId;
    openConversation(conversationId);
    onInitialConversationHandled?.(conversationId);
  }, [initialConversationId, onInitialConversationHandled, openConversation]);

  return (
    <div className="ws">
      <header className="ws__topbar">
        <span className="ws__logo">G</span>
        <span className="ws__brand">BANK Digital</span>
        <span className="ws__subtitle">Sơ thẩm — quyết định cuối thuộc người có thẩm quyền</span>
        <div className="ws__spacer" />
        {USE_MOCK_API && <span className="ws__mockflag" title="VITE_USE_MOCK_API != false — dữ liệu mock, chưa nối backend thật">● MOCK API</span>}
        <span className="ws__user">{user.username} · {ROLE_LABEL_USER[user.role]}</span>
        <ThemeToggle />
        <NotificationBell enabled={user.role === 'customer'} onOpenConv={openConversation} />
        {onOpenTower && (
          <button className="ws__logout ws__tower-btn" onClick={onOpenTower} type="button" data-testid="open-tower">
            🗼 Control Tower
            {pendingApprovals > 0 && (
              <span className="ws__tower-badge" data-testid="tower-badge" aria-label={`${pendingApprovals} phiếu chờ duyệt`}>
                {pendingApprovals}
              </span>
            )}
          </button>
        )}
        <button className="ws__logout" onClick={handleLogout} type="button">Đăng xuất</button>
      </header>

      <div className="ws__body">
        <ConversationSidebar
          conversations={conversations}
          groups={conversationGroups}
          activeId={activeId}
          onOpen={openConversation}
          onNew={startDraft}
          creating={creating}
          onRename={handleRename}
          onDelete={handleDelete}
          onCreateGroup={handleCreateGroup}
          onMoveConversation={handleMoveConversation}
          // T15-3 ownership: listConversations scope server-side theo cookie → MỌI phiên khách thấy là
          // của họ → hiện CRUD cho khách (customer) + RM (user). Admin quản ca ở Control Tower, không
          // ở sidebar cá nhân này. (Conversation không mang user_id ở mock — báo architect nếu BE
          // thật cần guard chặt hơn owner-check per-row.)
          showActions={user.role !== 'admin'}
        />

        {/* khung giữa: trao đổi và yêu cầu nghiệp vụ */}
        <section className="ws__chat">
          {listError && <div className="ws__banner ws__banner--error">{listError}</div>}
          {!activeId && !drafting ? (
            <div className="ws__empty">
              <div className="ws__empty-title">Chưa mở phiên xử lý nào</div>
              <div className="ws__empty-sub">Bấm “+ Phiên xử lý” bên trái để bắt đầu.</div>
            </div>
          ) : (
            <>
              <div className="ws__chat-head">
                <div className="ws__chat-title">{drafting ? 'Phiên xử lý mới (nháp)' : activeConv?.title ?? 'Phiên xử lý'}</div>
                <div className={`ws__chat-status ws__chat-status--${convStatus}`}>
                  {busy && <span className="status-dot status-dot--run deg-pulse" />}
                  {drafting ? 'Nhập yêu cầu đầu tiên để bắt đầu' : CONV_STATUS_LABEL[convStatus]}
                </div>
              </div>

              {loadError && <div className="ws__banner ws__banner--error">{loadError}</div>}

              <div className="ws__messages" ref={scrollRef} data-scroll>
                {!hasContent && (
                  <div className="ws__hint">
                    Nhập yêu cầu nghiệp vụ, ví dụ: “Khách C001 xin vay 5 tỷ — kiểm tra khả năng trả nợ
                    và tài liệu còn thiếu”. Kết quả sẽ kèm nguồn và bước xử lý tiếp theo.
                  </div>
                )}
                {messages.map((m) => (
                  <MessageBubble key={m.id} msg={m} />
                ))}
                {streaming && <StreamingMessageBubble bubble={streaming} />}

                {tasks.some((task) => task.status === 'failed') && (
                  <div className="ws__tasks" aria-label="Cảnh báo xử lý">
                    <span className="ws__tasks-label">CẦN KIỂM TRA</span>
                    {tasks
                      .filter((t) => t.status === 'failed')
                      .map((t) => (
                        <div key={`reason-${t.id}`} className="ws__task-reason" role="alert">
                          ✗ {roleLabel(t.role)}: Không hoàn tất bước xử lý. Vui lòng thử lại hoặc liên hệ bộ phận vận hành.
                        </div>
                      ))}
                  </div>
                )}

              </div>

              <Composer
                placeholder={drafting ? 'Nhập yêu cầu nghiệp vụ đầu tiên…' : 'Trao đổi hoặc bổ sung yêu cầu…'}
                onSend={sendChat}
                disabled={busy || creating}
              />
            </>
          )}
        </section>

        <Canvas cards={cards} tasks={tasks} onInterruptTask={handleInterruptTask} onFormSubmit={handleFormSubmit}
          formDrafts={formDrafts} onFormDraftChange={handleFormDraftChange} />
      </div>
    </div>
  );
}
