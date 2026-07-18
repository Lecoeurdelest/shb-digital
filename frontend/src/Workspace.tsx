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
import { useApprovalBadge } from './hooks/useApprovalBadge';
import { ConversationSidebar } from './components/ConversationSidebar';
import { ModelPicker } from './components/ModelPicker';
import { Composer } from './components/Composer';
import { MessageBubble, StreamingMessageBubble, type StreamingBubble } from './components/MessageBubble';
import { TaskBadge } from './components/TaskBadge';
import { Canvas } from './components/Canvas';
import { TraceBlock } from './components/TraceBlock';
import { SubAgentView } from './components/SubAgentView';
import { roleLabel } from './roles';
import type {
  AuditRow,
  AuthUser,
  Card,
  Conversation,
  ConversationFullState,
  ConversationStatus,
  Message,
  OrchTask,
  Phieu,
  TraceItem,
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

const ROLE_LABEL_USER: Record<AuthUser['role'], string> = { customer: 'Khách hàng', user: 'RM', admin: 'Quản lý' };

interface Props {
  user: AuthUser;
  onAuthExpired: () => void;
  onOpenTower?: () => void; // admin: mở Control Tower (D-19)
}

export function Workspace({ user, onAuthExpired, onOpenTower }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [tasks, setTasks] = useState<OrchTask[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [trace, setTrace] = useState<TraceItem[]>([]);
  const [focusSub, setFocusSub] = useState<string | null>(null); // task_id đang xem SubAgentView (F2a)
  const [convStatus, setConvStatus] = useState<ConversationStatus>('idle');
  const [streaming, setStreaming] = useState<StreamingBubble | null>(null);
  const [creating, setCreating] = useState(false);
  const [pickProvider, setPickProvider] = useState(''); // D-45b — provider/model cho ca MỚI ('' = server-default)
  const [pickModel, setPickModel] = useState('');
  // draft mode (D-45b): "+ Ca mới" KHÔNG tạo ca ngay — mở khung soạn (composer + picker hiện) để user
  // chọn provider/model TRƯỚC, ca tạo LAZY lúc gửi câu đầu (kèm model đã chọn). Fix dây "chọn-sau-khi-tạo".
  const [drafting, setDrafting] = useState(false);
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

  // SSE approval.decided → ghép card+phieu (card KHÔNG xoá §6): tìm card approval có approval_id ===
  // phieu.id → cập nhật status/decided_by/reason → panel re-render sang "đã duyệt/từ chối".
  const approvalDecided = useCallback((phieu: Phieu) => {
    setCards((prev) =>
      prev.map((c) =>
        c.type === 'approval' && c.approval_id === phieu.id
          ? { ...c, status: phieu.status, decided_by: phieu.decided_by, reason: phieu.reason }
          : c,
      ),
    );
  }, []);

  // SSE toolcall/thinking → append vào trace (F1). Backend chốt:
  // - toolcall: CÓ id (khớp audit row.id) → DEDUP upsert (reload GET /api/audit + SSE cùng id không trùng).
  // - thinking: KHÔNG id, LIVE-only (không persist) → LUÔN append theo thứ tự đến (mất khi reload — trace tạm).
  const addTrace = useCallback((item: TraceItem) => {
    setTrace((prev) => {
      if (item.kind === 'tool' && prev.some((t) => t.kind === 'tool' && t.id === item.id)) return prev;
      return [...prev, item];
    });
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
    () => ({ applyFullState, appendText, turnDone, upsertTask, setConversationStatus, upsertCard, approvalDecided, addTrace }),
    [applyFullState, appendText, turnDone, upsertTask, setConversationStatus, upsertCard, approvalDecided, addTrace],
  );

  useConversationSSE(activeId, handlers);

  // ── mở ca: reset view + refetch full state (SSE onopen cũng refetch — đây là đường mở tay) ──
  const openConversation = useCallback((id: string) => {
    activeIdRef.current = id; // set NGAY (trước async) — guard trong auditByConv/.then dùng đúng id
    setActiveId(id);
    setDrafting(false); // mở ca thật → rời draft mode
    setMessages([]);
    setTasks([]);
    setCards([]);
    setTrace([]);
    setFocusSub(null);
    setStreaming(null);
    setConvStatus('idle');
    setLoadError(null);
    conversationApi
      .getConversation(id)
      .then(applyFullState)
      .catch((err: unknown) => setLoadError(handleError(err, 'Không tải được nội dung ca')));
    // hydrate trace TOOLCALL từ DB (GET /api/audit?conv_id) — reload/mở lại ca thấy trace lại
    // (T4-2 fix: thinking live-only không khôi phục; toolcall persist → dựng lại). SSE live sau
    // upsert dedup theo id (addTrace). id audit row.id khớp toolcall SSE id → không trùng.
    conversationApi
      .auditByConv(id)
      .then((rows) => {
        if (id !== activeIdRef.current) return; // đổi ca giữa chừng → bỏ
        setTrace(rows.map(auditToTrace));
      })
      .catch(() => {
        // audit lỗi không chí mạng — trace live vẫn chạy, chỉ mất history khi reload
      });
  }, [applyFullState, handleError]);

  // "+ Ca mới" = MỞ KHUNG SOẠN (draft), KHÔNG POST. Ca tạo lazy lúc gửi câu đầu (kèm provider/model
  // user chọn ở picker). Vậy picker cạnh nút gửi mới THẬT áp vào ca — không còn "chọn sau khi đã tạo".
  const startDraft = useCallback(() => {
    activeIdRef.current = null;
    setActiveId(null);
    setDrafting(true);
    setMessages([]);
    setTasks([]);
    setCards([]);
    setTrace([]);
    setFocusSub(null);
    setStreaming(null);
    setConvStatus('idle');
    setLoadError(null);
    setListError(null);
  }, []);

  // tạo ca THẬT (lazy) với provider/model đã chọn → trả conv để gửi câu đầu vào. Fail → ném cho caller.
  const createConversationForSend = useCallback(async (): Promise<Conversation> => {
    const conv = await conversationApi.createConversation('Ca mới', pickProvider || undefined, pickModel || undefined);
    setConversations((prev) => upsertById(prev, conv));
    setListError(null);
    return conv;
  }, [pickProvider, pickModel]);

  const sendChat = useCallback((text: string) => {
    const pushUserMsg = (convId: string) => {
      // optimistic: user message hiện ngay (DB refetch/SSE sẽ xác nhận lại)
      setMessages((prev) => [
        ...prev,
        { id: `local_user_${Date.now()}`, conv_id: convId, ts: new Date().toISOString(), sender: 'user', content: text, meta: null },
      ]);
      setConvStatus('running');
    };

    const existingId = activeIdRef.current;
    if (existingId) {
      pushUserMsg(existingId);
      conversationApi
        .sendChat(existingId, text)
        .catch((err: unknown) => {
          setLoadError(handleError(err, 'Gửi câu hỏi thất bại'));
          setConvStatus('idle');
        });
      return;
    }

    // draft mode: chưa có ca → tạo LAZY với provider/model đã chọn, rồi gửi câu đầu vào ca đó.
    // KHÔNG dùng openConversation (nó getConversation→applyFullState set messages=[] → xoá optimistic
    // user-msg). Ca vừa tạo rỗng → chỉ cần gắn activeId + push optimistic; SSE lượt này dựng nội dung.
    if (creating) return;
    setCreating(true);
    createConversationForSend()
      .then((conv) => {
        activeIdRef.current = conv.id; // set NGAY trước SSE/refetch (tránh race — như openConversation)
        setActiveId(conv.id);
        setDrafting(false);
        pushUserMsg(conv.id);
        return conversationApi.sendChat(conv.id, text);
      })
      .catch((err: unknown) => {
        setListError(handleError(err, 'Không tạo được ca / gửi câu hỏi thất bại'));
        setConvStatus('idle');
      })
      .finally(() => setCreating(false));
  }, [creating, handleError, createConversationForSend]);

  // admin quyết phiếu (T3-2 · D-40). SSE approval.decided + card sẽ cập nhật panel (KHÔNG xoá card §6).
  // 409 approval_already_decided (2 admin bấm) → thông báo + refetch full-state (DB nguồn sự thật §0).
  const handleDecide = useCallback((approvalId: string, decision: 'approved' | 'rejected', reason: string) => {
    conversationApi
      .decideApproval(approvalId, decision, reason)
      .catch((err: unknown) => {
        if (err instanceof ApiRequestError && err.status === 409) {
          setLoadError('Phiếu đã được quyết trước đó — đang đồng bộ lại.');
          const id = activeIdRef.current;
          if (id) conversationApi.getConversation(id).then((s) => { if (id === activeIdRef.current) applyFullState(s); }).catch(() => {});
        } else {
          setLoadError(handleError(err, 'Quyết phiếu thất bại'));
        }
      });
  }, [handleError, applyFullState]);

  // auto-scroll khi có message mới / chữ stream
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, streaming]);

  const activeConv = conversations.find((c) => c.id === activeId) ?? null;
  const busy = convStatus === 'running';
  const hasContent = messages.length > 0 || streaming !== null;
  const isAdmin = user.role === 'admin';
  // badge phiếu-bay (D-56, admin-only): poll approvals?pending 5s → số phiếu chờ. Non-admin → 0 (hook tự tắt).
  const pendingApprovals = useApprovalBadge(isAdmin);
  // sub đang xem (F2a). Nếu task biến mất (đổi ca) → focusedTask null → về Canvas.
  const focusedTask = focusSub ? tasks.find((t) => t.id === focusSub) ?? null : null;

  return (
    <div className="ws">
      <header className="ws__topbar">
        <span className="ws__logo">G</span>
        <span className="ws__brand">Digital Expert Guild</span>
        <span className="ws__subtitle">Workspace · SHB #132</span>
        <div className="ws__spacer" />
        {USE_MOCK_API && <span className="ws__mockflag" title="VITE_USE_MOCK_API != false — dữ liệu mock, chưa nối backend thật">● MOCK API</span>}
        <span className="ws__user">{user.username} · {ROLE_LABEL_USER[user.role]}</span>
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
        <button className="ws__logout" onClick={onAuthExpired} type="button">Đăng xuất</button>
      </header>

      <div className="ws__body">
        <ConversationSidebar
          conversations={conversations}
          activeId={activeId}
          onOpen={openConversation}
          onNew={startDraft}
          creating={creating}
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
                  <ModelPicker
                    provider={pickProvider}
                    model={pickModel}
                    disabled={creating || hasContent}
                    onChange={(p, m) => { setPickProvider(p); setPickModel(m); }}
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
          <Canvas cards={cards} tasks={tasks} onDecide={handleDecide} canDecide={user.role === 'admin'} onSelectSub={setFocusSub} />
        )}
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

// AuditRow (GET /api/audit) → TraceItem toolcall. id khớp SSE toolcall id (dedup upsert). summary
// từ input (tóm tắt ≤120 char). thinking KHÔNG có trong audit (live-only) — reload chỉ toolcall.
function auditToTrace(row: AuditRow): TraceItem {
  let summary = '';
  if (row.input) {
    try {
      summary = JSON.stringify(row.input).slice(0, 120);
    } catch {
      summary = '';
    }
  }
  return { kind: 'tool', id: row.id, task_id: row.task_id, tool: row.tool, summary };
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
