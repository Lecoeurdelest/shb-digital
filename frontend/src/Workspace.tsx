// Workspace.tsx — màn chính S1: sidebar ca | chat Main (stream) | canvas placeholder.
// Scope = TÍNH NĂNG SPEC §9 (SSE chat.delta + task.status) + §11 (REST full-state) — KHÔNG canvas/card
// (S3), KHÔNG 3D (D-24), KHÔNG approval/sub-view (S4/S5). Look-and-feel tham khảo design/ (D-13).
// Container: giữ toàn bộ data/state ca hiện hành; presentational = components/. SSE upsert theo id,
// cùng shape với GET (1 codepath render — CLAUDE.md nghề FE). Auth do App gate; nhận user + báo
// onAuthExpired khi gặp 401 mid-session (cookie hết hạn).

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { conversationApi, USE_MOCK_API } from './api';
import { ApiRequestError } from './api/client';
import { useConversationSSE, type ConversationSSEHandlers } from './hooks/useConversationSSE';
import { ConversationSidebar } from './components/ConversationSidebar';
import { Composer } from './components/Composer';
import { MessageBubble, StreamingMessageBubble, type StreamingBubble } from './components/MessageBubble';
import { TaskBadge } from './components/TaskBadge';
import { Canvas } from './components/Canvas';
import { roleLabel } from './roles';
import type {
  AuthUser,
  Card,
  Conversation,
  ConversationFullState,
  ConversationStatus,
  Message,
  OrchTask,
} from './types';
import './App.css';

// upsert theo id, giữ thứ tự cũ + append cái mới (SSE task.created/status cùng shape GET).
function upsertById<T extends { id: string }>(list: T[], item: T): T[] {
  const idx = list.findIndex((x) => x.id === item.id);
  if (idx === -1) return [...list, item];
  const next = list.slice();
  next[idx] = item;
  return next;
}

const CONV_STATUS_LABEL: Record<ConversationStatus, string> = {
  idle: 'Sẵn sàng',
  running: 'Đội đang xử lý…',
  waiting_approval: 'Chờ phê duyệt',
  done: 'Hoàn tất',
  failed: 'Lỗi',
};

const ROLE_LABEL_USER: Record<AuthUser['role'], string> = { user: 'RM', admin: 'Quản lý' };

interface Props {
  user: AuthUser;
  onAuthExpired: () => void;
}

export function Workspace({ user, onAuthExpired }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [tasks, setTasks] = useState<OrchTask[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [convStatus, setConvStatus] = useState<ConversationStatus>('idle');
  const [streaming, setStreaming] = useState<StreamingBubble | null>(null);
  const [creating, setCreating] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  // ref theo activeId — dùng trong callback async (refetch) để kiểm còn đúng ca không (tránh race).
  const activeIdRef = useRef<string | null>(null);
  activeIdRef.current = activeId;

  // 401 mid-session (cookie hết hạn) → đẩy về login. Ổn định qua ref để callback không stale.
  const onAuthExpiredRef = useRef(onAuthExpired);
  onAuthExpiredRef.current = onAuthExpired;
  const handleError = useCallback((err: unknown, fallback: string): string => {
    if (err instanceof ApiRequestError && err.status === 401) {
      onAuthExpiredRef.current();
      return 'Phiên đăng nhập hết hạn — vui lòng đăng nhập lại.';
    }
    return describeError(err, fallback);
  }, []);

  // ── load danh sách ca lúc mount ──
  useEffect(() => {
    let alive = true;
    conversationApi
      .listConversations()
      .then((list) => {
        if (!alive) return;
        setConversations(list);
        setListError(null);
        if (list.length > 0) setActiveId((cur) => cur ?? list[0].id);
      })
      .catch((err: unknown) => {
        if (!alive) return;
        setListError(handleError(err, 'Không tải được danh sách ca'));
      });
    return () => {
      alive = false;
    };
  }, [handleError]);

  // ── SSE handlers (ref-stable qua useConversationSSE) ──
  const applyFullState = useCallback((state: ConversationFullState) => {
    setMessages(state.messages);
    setTasks(state.tasks);
    setCards(buildCanvas(state.cards ?? []));
    setConvStatus(state.conversation.status);
    setConversations((prev) => upsertById(prev, state.conversation));
    setStreaming(null);
    setLoadError(null);
  }, []);

  // SSE card → upsert canvas (upsert theo id + replace theo (task_id,type) giữ ts mới — §4).
  const upsertCard = useCallback((card: Card) => {
    setCards((prev) => upsertCardInto(prev, card));
  }, []);


  const appendText = useCallback((turnId: string, chunk: string) => {
    setStreaming((cur) =>
      cur && cur.turnId === turnId
        ? { turnId, text: cur.text + chunk }
        : { turnId, text: chunk },
    );
  }, []);

  const turnDone = useCallback((_turnId: string, fullText: string) => {
    // chốt lượt: đóng bubble streaming. Nội dung chính thức đến qua refetch/full state hoặc
    // full_text — ghim tạm 1 assistant message để không "mất chữ" giữa các event (DB là nguồn thật).
    setStreaming(null);
    if (fullText.trim()) {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.sender === 'assistant' && last.content === fullText) return prev;
        const msg: Message = {
          id: `local_${_turnId}`,
          conv_id: last?.conv_id ?? activeIdRef.current ?? '',
          ts: new Date().toISOString(),
          sender: 'assistant',
          content: fullText,
          meta: null,
        };
        return upsertById(prev, msg);
      });
    }
  }, []);

  const upsertTask = useCallback((task: OrchTask) => {
    setTasks((prev) => upsertById(prev, task));
  }, []);

  const setConversationStatus = useCallback((status: string) => {
    setConvStatus(status as ConversationStatus);
    const id = activeIdRef.current;
    setConversations((prev) =>
      id ? prev.map((c) => (c.id === id ? { ...c, status: status as ConversationStatus } : c)) : prev,
    );
    // Lượt kết thúc (done/failed) → refetch full-state: đồng bộ message DB chính thức (gồm
    // system message lỗi ở nhánh MAIN fail — CONTRACT §4b Gap2 B; DB là nguồn sự thật §0).
    if ((status === 'done' || status === 'failed') && id) {
      conversationApi
        .getConversation(id)
        .then((state) => {
          if (id === activeIdRef.current) applyFullState(state);
        })
        .catch(() => {
          // refetch lỗi không chí mạng — state realtime đã đủ dùng, reconnect sẽ tự lành
        });
    }
  }, [applyFullState]);

  const handlers: ConversationSSEHandlers = useMemo(
    () => ({ applyFullState, appendText, turnDone, upsertTask, setConversationStatus, upsertCard }),
    [applyFullState, appendText, turnDone, upsertTask, setConversationStatus, upsertCard],
  );

  useConversationSSE(activeId, handlers);

  // ── mở ca: reset view + refetch full state (SSE onopen cũng refetch — đây là đường mở tay) ──
  const openConversation = useCallback((id: string) => {
    setActiveId(id);
    setMessages([]);
    setTasks([]);
    setCards([]);
    setStreaming(null);
    setConvStatus('idle');
    setLoadError(null);
    conversationApi
      .getConversation(id)
      .then(applyFullState)
      .catch((err: unknown) => setLoadError(handleError(err, 'Không tải được nội dung ca')));
  }, [applyFullState, handleError]);

  const createConversation = useCallback(() => {
    if (creating) return;
    setCreating(true);
    conversationApi
      .createConversation('Ca mới')
      .then((conv) => {
        setConversations((prev) => upsertById(prev, conv));
        setListError(null);
        openConversation(conv.id);
      })
      .catch((err: unknown) => setListError(handleError(err, 'Không tạo được ca')))
      .finally(() => setCreating(false));
  }, [creating, openConversation, handleError]);

  const sendChat = useCallback((text: string) => {
    const id = activeIdRef.current;
    if (!id) return;
    // optimistic: user message hiện ngay (DB refetch/SSE sẽ xác nhận lại)
    setMessages((prev) => [
      ...prev,
      { id: `local_user_${Date.now()}`, conv_id: id, ts: new Date().toISOString(), sender: 'user', content: text, meta: null },
    ]);
    setConvStatus('running');
    conversationApi
      .sendChat(id, text)
      .catch((err: unknown) => setLoadError(handleError(err, 'Gửi câu hỏi thất bại')));
  }, [handleError]);

  // auto-scroll khi có message mới / chữ stream
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, streaming]);

  const activeConv = conversations.find((c) => c.id === activeId) ?? null;
  const busy = convStatus === 'running';
  const hasContent = messages.length > 0 || streaming !== null;

  return (
    <div className="ws">
      <header className="ws__topbar">
        <span className="ws__logo">G</span>
        <span className="ws__brand">Digital Expert Guild</span>
        <span className="ws__subtitle">Workspace · SHB #132</span>
        <div className="ws__spacer" />
        {USE_MOCK_API && <span className="ws__mockflag" title="VITE_USE_MOCK_API != false — dữ liệu mock, chưa nối backend thật">● MOCK API</span>}
        <span className="ws__user">{user.username} · {ROLE_LABEL_USER[user.role]}</span>
        <button className="ws__logout" onClick={onAuthExpired} type="button">Đăng xuất</button>
      </header>

      <div className="ws__body">
        <ConversationSidebar
          conversations={conversations}
          activeId={activeId}
          onOpen={openConversation}
          onNew={createConversation}
          creating={creating}
        />

        {/* khung giữa: chat với Main */}
        <section className="ws__chat">
          {listError && <div className="ws__banner ws__banner--error">{listError}</div>}
          {!activeId ? (
            <div className="ws__empty">
              <div className="ws__empty-title">Chưa mở ca nào</div>
              <div className="ws__empty-sub">Bấm “+ Ca mới” bên trái để bắt đầu một ca tư vấn.</div>
            </div>
          ) : (
            <>
              <div className="ws__chat-head">
                <div className="ws__chat-title">{activeConv?.title ?? 'Ca'}</div>
                <div className={`ws__chat-status ws__chat-status--${convStatus}`}>
                  {busy && <span className="status-dot status-dot--run deg-pulse" />}
                  {CONV_STATUS_LABEL[convStatus]}
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
                placeholder="Hỏi Main về ca này…"
                onSend={sendChat}
                disabled={busy}
              />
            </>
          )}
        </section>

        {/* canvas: live map 2D + bảng việc + card render (S2 — T2-3) */}
        <Canvas cards={cards} tasks={tasks} />
      </div>
    </div>
  );
}

// canvas-present §4: dựng canvas từ full-state cards[] — replace theo (task_id,type) giữ ts mới nhất
// (1 role trình lại cùng loại card → thay bản cũ, không nhân đôi). Sort theo ts để thứ tự ổn định.
function buildCanvas(cards: Card[]): Card[] {
  const byKey = new Map<string, Card>();
  for (const c of [...cards].sort((a, b) => (a.ts ?? '').localeCompare(b.ts ?? ''))) {
    byKey.set(canvasKey(c), c); // ts sau ghi đè ts trước
  }
  return [...byKey.values()];
}

// upsert 1 card (SSE) vào canvas: cùng id → replace; cùng (task_id,type) khác id → thay bản cũ giữ mới.
function upsertCardInto(prev: Card[], card: Card): Card[] {
  const key = canvasKey(card);
  const next = prev.filter((c) => c.id !== card.id && canvasKey(c) !== key);
  next.push(card);
  return next.sort((a, b) => (a.ts ?? '').localeCompare(b.ts ?? ''));
}

function canvasKey(c: Card): string {
  return `${c.task_id ?? 'null'}::${c.type}`;
}

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiRequestError) {
    return err.body?.message ?? `${fallback} (HTTP ${err.status})`;
  }
  if (err instanceof Error && err.message) return `${fallback}: ${err.message}`;
  return fallback;
}

// lý do lỗi từ task.result.reason (CONTRACT §4b Gap2 A — result là dict tự do, đọc an toàn).
function taskReason(task: OrchTask): string | null {
  const reason = task.result?.reason;
  return typeof reason === 'string' && reason.trim() ? reason : null;
}
