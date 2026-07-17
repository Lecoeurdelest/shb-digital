// hooks/useConversationSSE.ts — transport + ghép chunk + reconnect refetch.
// Khung theo docs/patterns/streaming-sse.md §3 — seq scope THEO LƯỢT (turn_id), KHÔNG phải
// cursor toàn cuộc hội thoại (spec §14 cấm replay-cursor). DB (refetch full state) là nguồn
// sự thật; SSE chỉ là thông báo "có cái mới" (streaming-sse.md §0).

import { useEffect, useRef } from 'react';
import { conversationApi } from '../api';
import type {
  ChatDeltaData,
  ConversationFullState,
  OrchTask,
  SSEEnvelope,
} from '../types';

export interface ConversationSSEHandlers {
  applyFullState: (state: ConversationFullState) => void;
  appendText: (turnId: string, chunk: string) => void;
  turnDone: (turnId: string, fullText: string) => void;
  upsertTask: (task: OrchTask) => void;
  setConversationStatus: (status: string) => void;
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
    let retry = 0;
    let dead = false;

    const connect = () => {
      es = conversationApi.openEventSource(convId);

      es.onopen = () => {
        retry = 0;
        turns.clear(); // lượt dở dang → chờ done.full_text hoặc refetch tự lành
        conversationApi
          .getConversation(convId)
          .then((state) => handlersRef.current.applyFullState(state))
          .catch(() => {
            // refetch lỗi không phải sự cố chí mạng — SSE vẫn tiếp tục nghe, retry tự nhiên ở lần sau
          });
      };

      es.onmessage = (m) => {
        let ev: SSEEnvelope;
        try {
          ev = JSON.parse(m.data);
        } catch {
          return; // frame malformed — bỏ, không crash cả kết nối
        }

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
        if (ev.type !== 'chat.delta') return; // card/toolcall/approval — sprint sau (S3+)

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
        es?.close();
        if (dead) return;
        const delayMs = Math.min(1000 * 2 ** retry, 30000);
        retry += 1;
        timer = window.setTimeout(connect, delayMs + Math.random() * 300);
      };
    };

    connect();

    return () => {
      dead = true;
      es?.close();
      window.clearTimeout(timer);
    };
  }, [convId]);
}
