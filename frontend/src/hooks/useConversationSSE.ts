// hooks/useConversationSSE.ts — transport + ghép chunk + reconnect refetch.
// Khung theo docs/patterns/streaming-sse.md §3 — seq scope THEO LƯỢT (turn_id), KHÔNG phải
// cursor toàn cuộc hội thoại (spec §14 cấm replay-cursor). DB (refetch full state) là nguồn
// sự thật; SSE chỉ là thông báo "có cái mới" (streaming-sse.md §0).

import { useEffect, useRef } from 'react';
import { conversationApi } from '../api';
import type {
  Card,
  ChatDeltaData,
  ConversationFullState,
  OrchTask,
  Phieu,
  SSEEnvelope,
  ThinkingData,
  ToolcallData,
  TraceItem,
} from '../types';

export interface ConversationSSEHandlers {
  applyFullState: (state: ConversationFullState) => void;
  appendText: (turnId: string, chunk: string) => void;
  turnDone: (turnId: string, fullText: string) => void;
  upsertTask: (task: OrchTask) => void;
  setConversationStatus: (status: string) => void;
  upsertCard: (card: Card) => void;
  approvalDecided: (phieu: Phieu) => void;
  addTrace: (item: TraceItem) => void;
}

interface TurnBuffer {
  last: number;
  done?: number;
  buf: Map<number, ChatDeltaData>;
}

export function useConversationSSE(convId: string | null, handlers: ConversationSSEHandlers): void {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!convId) return;

    const turns = new Map<string, TurnBuffer>();
    let es: ReturnType<typeof conversationApi.openEventSource> | null = null;
    let timer = 0;
    let watchdog = 0;
    let retry = 0;
    let dead = false;

    // Watchdog (D-54): EventSource.onerror KHÔNG fire khi server chết SIGKILL (không FIN gói) →
    // reconnect không được gọi → UI treo câm. Backend gửi named event `ping` mỗi 15s;
    // im lặng > WATCHDOG_MS (heartbeat 15s + dư 10 = 25s) = coi như kết nối chết → đóng + reconnect.
    const WATCHDOG_MS = 25000;
    const scheduleReconnect = () => {
      es?.close();
      if (dead) return;
      const delayMs = Math.min(1000 * 2 ** retry, 30000);
      retry += 1;
      timer = window.setTimeout(connect, delayMs + Math.random() * 300);
    };
    const armWatchdog = () => {
      window.clearTimeout(watchdog);
      if (dead) return;
      watchdog = window.setTimeout(() => {
        // eslint-disable-next-line no-console
        console.debug('[SSE watchdog] im lặng > 40s — đóng + reconnect (server có thể đã chết câm)');
        scheduleReconnect();
      }, WATCHDOG_MS);
    };

    const connect = () => {
      es = conversationApi.openEventSource(convId);
      armWatchdog(); // bắt đầu đếm ngay khi mở — nếu không có cả frame đầu cũng bắt được

      es.onopen = () => {
        retry = 0;
        armWatchdog(); // có tín hiệu open → gia hạn
        turns.clear(); // lượt dở dang → chờ done.full_text hoặc refetch tự lành
        conversationApi
          .getConversation(convId)
          .then((state) => handlersRef.current.applyFullState(state))
          .catch(() => {
            // refetch lỗi không phải sự cố chí mạng — SSE vẫn tiếp tục nghe, retry tự nhiên ở lần sau
          });
      };

      es.onmessage = (m) => {
        armWatchdog(); // NHẬN BẤT KỲ data nào (event thật HOẶC ping) → reset đồng hồ treo
        let ev: SSEEnvelope;
        try {
          ev = JSON.parse(m.data);
        } catch {
          return; // frame malformed — bỏ, không crash cả kết nối
        }

        if (ev.type === 'ping') return; // heartbeat — chỉ để reset watchdog (đã reset ở trên), không render

        if (ev.type === 'task.created' || ev.type === 'task.status') {
          const data = ev.data as { task: OrchTask };
          handlersRef.current.upsertTask(data.task);
          return;
        }
        if (ev.type === 'conversation.status') {
          const data = ev.data as { status: string };
          handlersRef.current.setConversationStatus(data.status);
          return;
        }
        if (ev.type === 'card') {
          const data = ev.data as { card: Card };
          if (data.card) handlersRef.current.upsertCard(data.card);
          return;
        }
        if (ev.type === 'approval.pending') {
          // phiếu tạo → card approval đã đến qua event 'card' (vỏ sinh cùng lúc). Chỉ badge/status
          // cần — conversation.status→waiting_approval đã lo. Không cần xử thêm ở đây.
          return;
        }
        if (ev.type === 'approval.decided') {
          const data = ev.data as { phieu: Phieu };
          if (data.phieu) handlersRef.current.approvalDecided(data.phieu);
          return;
        }
        if (ev.type === 'toolcall') {
          const d = ev.data as ToolcallData;
          if (d && d.id) {
            handlersRef.current.addTrace({ kind: 'tool', id: d.id, task_id: d.task_id ?? null, tool: d.tool, summary: d.summary });
          }
          return;
        }
        if (ev.type === 'thinking') {
          const d = ev.data as ThinkingData;
          if (d && typeof d.text === 'string' && d.text.trim()) {
            // thinking không có id (không persist DB) → sinh id ổn định theo (task_id, seq/ts) để dedup.
            handlersRef.current.addTrace({ kind: 'thinking', id: `think_${d.task_id ?? 'main'}_${ev.ts}`, task_id: d.task_id ?? null, text: d.text });
          }
          return;
        }
        if (ev.type !== 'chat.delta') return;

        const d = ev.data as ChatDeltaData;
        const t = turns.get(d.turn_id) ?? { last: 0, buf: new Map<number, ChatDeltaData>() };
        turns.set(d.turn_id, t);

        if (ev.seq == null || ev.seq <= t.last) return; // trùng/stale → bỏ
        t.buf.set(ev.seq, d);
        if (d.done) t.done = ev.seq;

        while (t.buf.has(t.last + 1)) {
          t.last += 1;
          const nx = t.buf.get(t.last)!;
          t.buf.delete(t.last);
          if (nx.chunk) handlersRef.current.appendText(d.turn_id, nx.chunk);
        }

        if (t.done !== undefined && t.last >= t.done) {
          const finalChunk = t.buf.get(t.done) ?? d;
          handlersRef.current.turnDone(d.turn_id, finalChunk.full_text ?? d.full_text ?? '');
          turns.delete(d.turn_id);
        }
      };

      es.onerror = () => {
        window.clearTimeout(watchdog); // đóng đường này → dừng watchdog, scheduleReconnect tự arm lại khi connect
        scheduleReconnect();
      };
    };

    connect();

    return () => {
      dead = true;
      es?.close();
      window.clearTimeout(timer);
      window.clearTimeout(watchdog);
    };
  }, [convId]);
}
