// Workspace.tsx — màn chính S1: sidebar ca | chat Main (stream) | canvas placeholder.
// Scope = TÍNH NĂNG SPEC §9 (SSE chat.delta + task.status) + §11 (REST full-state) — KHÔNG canvas/card
// (S3), KHÔNG 3D (D-24), KHÔNG approval/sub-view (S4/S5). Look-and-feel tham khảo design/ (D-13).
// Container: giữ toàn bộ data/state ca hiện hành; presentational = components/. SSE upsert theo id,
// cùng shape với GET (1 codepath render — CLAUDE.md nghề FE). Auth do App gate; nhận user + báo
// onAuthExpired khi gặp 401 mid-session (cookie hết hạn).
// State/effect/callback sống ở hooks/useWorkspaceController.ts (nợ ghi từ S14 — file gốc >400 LOC,
// tách để component chỉ còn JSX). Helper thuần (upsert/canvas/error-shape) ở workspaceUtil.ts.

import { USE_MOCK_API } from './api';
import { useWorkspaceController } from './hooks/useWorkspaceController';
import { NotificationBell } from './components/NotificationBell';
import { ThemeToggle } from './components/ThemeToggle';
import { ConversationSidebar } from './components/ConversationSidebar';
import { ModelSelect } from './components/ModelSelect';
import { Composer } from './components/Composer';
import { MessageBubble, StreamingMessageBubble } from './components/MessageBubble';
import { TaskBadge } from './components/TaskBadge';
import { Canvas } from './components/Canvas';
import { TraceBlock } from './components/TraceBlock';
import { SubAgentView } from './components/SubAgentView';
import { roleLabel } from './roles';
import { taskReason } from './workspaceUtil';
import type { AuthUser, ConversationStatus } from './types';
import './App.css';

const CONV_STATUS_LABEL: Record<ConversationStatus, string> = {
  idle: 'Sẵn sàng',
  running: 'Đội đang xử lý…',
  waiting_approval: 'Chờ phê duyệt',
  done: 'Hoàn tất',
  failed: 'Lỗi',
};

const ROLE_LABEL_USER: Record<AuthUser['role'], string> = { customer: 'Khách hàng', user: 'RM', admin: 'Quản lý' };

interface Props {
  user: AuthUser;
  onAuthExpired: () => void;
  onOpenTower?: () => void; // admin: mở Control Tower (D-19)
}

export function Workspace({ user, onAuthExpired, onOpenTower }: Props) {
  const {
    conversations, activeId, messages, tasks, cards, trace, setFocusSub,
    convStatus, streaming, creating, pickProvider, pickModel, drafting, formDrafts,
    loadError, listError, scrollRef,
    openConversation, startDraft, sendChat, handleDecide, handleFormDraftChange,
    handleFormSubmit, handleModelChange, handleRename, handleDelete, handleLogout,
    activeConv, busy, hasContent, pendingApprovals, focusedTask,
  } = useWorkspaceController({ user, onAuthExpired });

  return (
    <div className="ws">
      <header className="ws__topbar">
        <span className="ws__logo">G</span>
        <span className="ws__brand">Digital Expert Guild</span>
        <span className="ws__subtitle">Workspace · BANK Digital</span>
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
          activeId={activeId}
          onOpen={openConversation}
          onNew={startDraft}
          creating={creating}
          onRename={handleRename}
          onDelete={handleDelete}
          // T15-3 ownership: listConversations scope server-side theo cookie → MỌI ca khách thấy là
          // của họ → hiện CRUD cho khách (customer) + RM (user). Admin quản ca ở Control Tower, không
          // ở sidebar cá nhân này. (Conversation không mang user_id ở mock — báo architect nếu BE
          // thật cần guard chặt hơn owner-check per-row.)
          showActions={user.role !== 'admin'}
        />

        {/* khung giữa: chat với Main */}
        <section className="ws__chat">
          {listError && <div className="ws__banner ws__banner--error">{listError}</div>}
          {!activeId && !drafting ? (
            <div className="ws__empty">
              <div className="ws__empty-title">Chưa mở ca nào</div>
              <div className="ws__empty-sub">Bấm “+ Ca mới” bên trái để bắt đầu một ca tư vấn.</div>
            </div>
          ) : (
            <>
              <div className="ws__chat-head">
                <div className="ws__chat-title">{drafting ? 'Ca mới (nháp)' : activeConv?.title ?? 'Ca'}</div>
                <div className={`ws__chat-status ws__chat-status--${convStatus}`}>
                  {busy && <span className="status-dot status-dot--run deg-pulse" />}
                  {drafting ? 'Chọn model rồi gõ câu hỏi đầu tiên' : CONV_STATUS_LABEL[convStatus]}
                </div>
              </div>

              {loadError && <div className="ws__banner ws__banner--error">{loadError}</div>}

              <div className="ws__messages" ref={scrollRef} data-scroll>
                {!hasContent && (
                  <div className="ws__hint">
                    Gõ một yêu cầu tư vấn (VD: “Khách C001 xin vay — DSCR bao nhiêu?”).
                    Main sẽ điều phối đội chuyên gia và trả lời có nguồn.
                  </div>
                )}
                {messages.map((m) => (
                  <MessageBubble key={m.id} msg={m} />
                ))}
                {streaming && <StreamingMessageBubble bubble={streaming} />}

                {/* khối trace F1 (thinking + toolcall collapsible) — D-43 user track */}
                <TraceBlock items={trace} taskRole={(id) => tasks.find((t) => t.id === id)?.role} />

                {tasks.length > 0 && (
                  <div className="ws__tasks" aria-label="Đội đang làm việc">
                    <span className="ws__tasks-label">ĐỘI ĐANG LÀM VIỆC</span>
                    <div className="ws__tasks-row">
                      {tasks.map((t) => (
                        <TaskBadge key={t.id} task={t} />
                      ))}
                    </div>
                    {/* lý do lỗi từ task.result.reason khi sub failed (CONTRACT §4b Gap2 A) */}
                    {tasks
                      .filter((t) => t.status === 'failed')
                      .map((t) => {
                        const reason = taskReason(t);
                        return reason ? (
                          <div key={`reason-${t.id}`} className="ws__task-reason" role="alert">
                            ✗ {roleLabel(t.role)}: {reason}
                          </div>
                        ) : null;
                      })}
                  </div>
                )}

              </div>

              <Composer
                placeholder={drafting ? 'Gõ câu hỏi đầu tiên — ca sẽ tạo với model đã chọn…' : 'Hỏi Main về ca này…'}
                onSend={sendChat}
                disabled={busy || creating}
                extras={
                  // T15-2: draft → giá trị pick* local (chọn trước, tạo ca kèm). open-conv → provider/model
                  // của ca (per-turn switch qua PATCH trong handleModelChange). autoDefault CHỈ ở draft
                  // (open-conv giữ đúng model ca đã lưu, không tự đổi). disabled CHỈ khi running (T15-2
                  // per-turn switch: enable cả khi đã có tin nhắn — bỏ guard hasContent cũ).
                  <ModelSelect
                    provider={activeId ? (activeConv?.provider ?? '') : pickProvider}
                    model={activeId ? (activeConv?.model ?? '') : pickModel}
                    disabled={busy || creating}
                    autoDefault={!activeId}
                    onChange={handleModelChange}
                  />
                }
              />
            </>
          )}
        </section>

        {/* vùng phải: click sub → SubAgentView (F2a T4-3); else Canvas (live map + card + approval) */}
        {focusedTask ? (
          <SubAgentView
            task={focusedTask}
            liveTrace={trace.filter((t) => t.task_id === focusedTask.id)}
            convId={activeId ?? ''}
            onBack={() => setFocusSub(null)}
          />
        ) : (
          <Canvas cards={cards} tasks={tasks} messages={messages} trace={trace} onDecide={handleDecide} canDecide={user.role === 'admin'} onFormSubmit={handleFormSubmit}
            formDrafts={formDrafts} onFormDraftChange={handleFormDraftChange} onSelectSub={setFocusSub} />
        )}
      </div>
    </div>
  );
}
