// hooks/useWorkspaceController.ts — toàn bộ state + effect + callback của Workspace tách khỏi
// Workspace.tsx (nợ ghi từ S14 — file gốc >400 LOC). MỘT hook gọi 1 lần ở top Workspace() giữ
// đúng thứ tự hook — component chỉ còn JSX + gọi field trả về từ đây. 0 đổi hành vi: DI CHUYỂN
// nguyên state/effect/callback, không sửa logic.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { conversationApi } from '../api';
import { ApiRequestError } from '../api/client';
import { useConversationSSE, type ConversationSSEHandlers } from './useConversationSSE';
import { useApprovalBadge } from './useApprovalBadge';
import type { StreamingBubble } from '../components/MessageBubble';
import type {
  AuthUser,
  Card,
  Conversation,
  ConversationFullState,
  ConversationStatus,
  Message,
  OrchTask,
  Phieu,
  TraceItem,
} from '../types';
import { auditToTrace, buildCanvas, describeError, readApiError, upsertById, upsertCardInto } from '../workspaceUtil';

interface Params {
  user: AuthUser;
  onAuthExpired: () => void;
}

export function useWorkspaceController({ user, onAuthExpired }: Params) {
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
  // DF-A-04: form-draft values NÂNG lên đây (theo card.id) để sống qua đổi tab canvas (FormCard unmount
  // khi đổi tab → local state chết). Clear entry khi submit thành công (không dính form lần sau).
  const [formDrafts, setFormDrafts] = useState<Record<string, Record<string, string>>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  // ref theo activeId — dùng trong callback async (refetch) để kiểm còn đúng ca không (tránh race).
  const activeIdRef = useRef<string | null>(null);
  activeIdRef.current = activeId;
  // ref theo drafting — mount-effect auto-select ca (async) đọc REF để KHÔNG đè draft cố ý của user
  // (DF-A-07: fresh load → user bấm "+ Ca mới" TRƯỚC khi listConversations resolve → startDraft set
  // activeId=null → promise resolve `null ?? list[0]` ĐÈ về ca cũ → panel kẹt ca cũ. Guard ref chặn đè).
  const draftingRef = useRef(false);
  draftingRef.current = drafting;

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
        // auto-select ca đầu KHI chưa chọn gì — NHƯNG không đè nếu user đã chủ động vào draft "+ Ca mới"
        // trong lúc list đang tải (DF-A-07 race): draftingRef true → giữ nguyên draft, không select ca cũ.
        if (list.length > 0 && !draftingRef.current) setActiveId((cur) => cur ?? list[0].id);
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
    setFormDrafts({}); // đổi ca → clear form-draft (2 conv không lẫn — DF-A-04 defensive)
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
    setFormDrafts({}); // draft mới → clear form-draft ca cũ (DF-A-04)
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

  // khách nộp hồ sơ (T9-3 D-57). form-submit → SSE card update (status submitted) → FormCard read-only.
  // Ném lỗi lại cho FormCard hiển thị message 4-field (missing_fields/bad_income); 409 → refetch read-only.
  // DF-A-04: FormCard onChange → lưu draft theo card.id ở Workspace (sống qua đổi tab).
  const handleFormDraftChange = useCallback((cardId: string, values: Record<string, string>) => {
    setFormDrafts((prev) => ({ ...prev, [cardId]: values }));
  }, []);

  const handleFormSubmit = useCallback(async (cardId: string, values: Record<string, string>): Promise<void> => {
    const id = activeIdRef.current;
    if (!id) throw new Error('Chưa mở ca');
    try {
      await conversationApi.submitForm(id, cardId, values);
      // submit OK → clear draft entry (không dính sang form/lần sau — defensive DF-A-04)
      setFormDrafts((prev) => { const next = { ...prev }; delete next[cardId]; return next; });
    } catch (err: unknown) {
      // 409 đã nộp → refetch full-state để card về read-only (DB nguồn sự thật §0)
      if (err instanceof ApiRequestError && err.status === 409) {
        conversationApi.getConversation(id).then((s) => { if (id === activeIdRef.current) applyFullState(s); }).catch(() => {});
      }
      throw err; // FormCard bắt → hiện message
    }
  }, [applyFullState]);

  // ── S15 T15-2: per-turn model switch trong ca đang mở. Đổi → PATCH {provider,model} → lượt chat
  // sau đi model mới. Optimistic upsert conv (label sống qua re-render). 409 (running) → revert +
  // báo. Draft mode KHÔNG gọi đây (chỉ set pick* local, tạo ca kèm — createConversationForSend).
  const handleModelChange = useCallback((provider: string, model: string) => {
    const id = activeIdRef.current;
    if (!id) { setPickProvider(provider); setPickModel(model); return; } // draft: chỉ set local
    const prevConv = conversations.find((c) => c.id === id);
    // optimistic: cập nhật conv ngay để label đổi tức thì
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, provider, model } : c)));
    conversationApi
      .updateConversation(id, { provider, model })
      .then((conv) => setConversations((prev) => upsertById(prev, conv)))
      .catch((err: unknown) => {
        // revert về conv cũ (đặc biệt 409 running — BE chặn đổi giữa lượt)
        if (prevConv) setConversations((prev) => prev.map((c) => (c.id === id ? prevConv : c)));
        const { status, message } = readApiError(err);
        setLoadError(status === 409 ? (message ?? 'Ca đang chạy — không đổi model giữa lượt.') : handleError(err, 'Đổi model thất bại'));
      });
  }, [conversations, handleError]);

  // T15-3: rename ca (PATCH {title}). Optimistic + upsert kết quả. Fail → revert + báo.
  const handleRename = useCallback((id: string, title: string) => {
    const trimmed = title.trim();
    if (!trimmed) return; // rỗng → bỏ (giữ tên cũ)
    const prevConv = conversations.find((c) => c.id === id);
    if (prevConv && prevConv.title === trimmed) return; // không đổi → bỏ
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, title: trimmed } : c)));
    conversationApi
      .updateConversation(id, { title: trimmed })
      .then((conv) => setConversations((prev) => upsertById(prev, conv)))
      .catch((err: unknown) => {
        if (prevConv) setConversations((prev) => prev.map((c) => (c.id === id ? prevConv : c)));
        setListError(handleError(err, 'Đổi tên ca thất bại'));
      });
  }, [conversations, handleError]);

  // T15-3: xoá ca (DELETE). 409 (phiếu pending / đang chạy) → hiện hint từ BE, KHÔNG xoá. Xoá ca
  // đang mở → về draft (rời view ca vừa xoá). Thành công → gỡ khỏi list.
  const handleDelete = useCallback((id: string) => {
    conversationApi
      .deleteConversation(id)
      .then(() => {
        setConversations((prev) => prev.filter((c) => c.id !== id));
        setListError(null);
        if (activeIdRef.current === id) startDraft(); // đang mở ca vừa xoá → về khung nháp
      })
      .catch((err: unknown) => {
        const { status, message } = readApiError(err);
        setListError(status === 409 ? (message ?? 'Không xoá được ca (đang chạy / còn phiếu chờ).') : handleError(err, 'Xoá ca thất bại'));
      });
  }, [handleError, startDraft]);

  // Đăng xuất THẬT: gọi API xoá cookie httponly TRƯỚC (reload sau = anon, không auto-vào-lại), rồi set
  // anon client-side. logout lỗi/timeout → vẫn set anon (UI về Login; cookie có thể còn nhưng /me sẽ
  // 401 khi hết hạn — best-effort, không chặn user rời màn).
  const handleLogout = useCallback(() => {
    conversationApi.logout().catch(() => { /* best-effort — vẫn về anon */ }).finally(() => onAuthExpiredRef.current());
  }, []);

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

  return {
    conversations, activeId, messages, tasks, cards, trace, focusSub, setFocusSub,
    convStatus, streaming, creating, pickProvider, pickModel, drafting, formDrafts,
    loadError, listError, scrollRef,
    openConversation, startDraft, sendChat, handleDecide, handleFormDraftChange,
    handleFormSubmit, handleModelChange, handleRename, handleDelete, handleLogout,
    activeConv, busy, hasContent, isAdmin, pendingApprovals, focusedTask,
  };
}
