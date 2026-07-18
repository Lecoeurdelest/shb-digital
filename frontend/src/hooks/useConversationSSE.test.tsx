// useConversationSSE.test.tsx — test cơ chế ghép chunk streaming (seq/buffer/dedup/done.full_text).
// Đây là phần logic tinh vi nhất của FE (van tự lành streaming-sse §3) — test độc lập BE bằng
// EventSource giả điều khiển tay: bơm event theo thứ tự bất kỳ, assert handler được gọi đúng.
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { MinimalEventSource } from '../api/mock';
import type { ConversationFullState, SSEEnvelope, ChatDeltaData, OrchTask } from '../types';

// ── EventSource giả: giữ ref để test bơm event + kích onopen/onerror tay ──
let fakeES: MinimalEventSource & { emit: (ev: SSEEnvelope) => void; fire: (k: 'open' | 'error') => void };

function makeFakeES(): typeof fakeES {
  const es = {
    onopen: null as null | (() => void),
    onmessage: null as null | ((ev: { data: string }) => void),
    onerror: null as null | (() => void),
    closed: false,
    close() { this.closed = true; },
    emit(ev: SSEEnvelope) { this.onmessage?.({ data: JSON.stringify(ev) }); },
    fire(k: 'open' | 'error') { if (k === 'open') this.onopen?.(); else this.onerror?.(); },
  };
  return es as unknown as typeof fakeES;
}

const EMPTY_STATE: ConversationFullState = {
  conversation: { id: 'c1', title: 'x', status: 'idle', created_at: '' },
  messages: [],
  tasks: [],
};
const getFullState = vi.fn(() => Promise.resolve(EMPTY_STATE));

// mock module ../api để hook dùng EventSource giả + getConversation giả (không chạm mock thật/network)
vi.mock('../api', () => ({
  conversationApi: {
    openEventSource: () => fakeES,
    getConversation: () => getFullState(),
  },
}));

import { useConversationSSE, type ConversationSSEHandlers } from './useConversationSSE';

function delta(seq: number | null, turn: string, chunk: string, done = false, full?: string): SSEEnvelope<ChatDeltaData> {
  return { type: 'chat.delta', conversation_id: 'c1', seq, ts: '', data: { turn_id: turn, chunk, done, full_text: full } };
}
function taskEv(type: 'task.created' | 'task.status', task: OrchTask): SSEEnvelope {
  return { type, conversation_id: 'c1', seq: null, ts: '', data: { task } };
}

function makeHandlers(): ConversationSSEHandlers & { calls: Record<string, unknown[][]> } {
  const calls: Record<string, unknown[][]> = { appendText: [], turnDone: [], upsertTask: [], setConversationStatus: [], applyFullState: [], upsertCard: [], approvalDecided: [], addTrace: [] };
  return {
    calls,
    applyFullState: (s) => calls.applyFullState.push([s]),
    appendText: (t, c) => calls.appendText.push([t, c]),
    turnDone: (t, f) => calls.turnDone.push([t, f]),
    upsertTask: (t) => calls.upsertTask.push([t]),
    setConversationStatus: (s) => calls.setConversationStatus.push([s]),
    upsertCard: (c) => calls.upsertCard.push([c]),
    approvalDecided: (p) => calls.approvalDecided.push([p]),
    addTrace: (i) => calls.addTrace.push([i]),
  };
}

describe('useConversationSSE — ghép chunk streaming', () => {
  beforeEach(() => {
    fakeES = makeFakeES();
    getFullState.mockReset();
    getFullState.mockResolvedValue(EMPTY_STATE);
  });

  it('onopen → refetch full state (DB là nguồn sự thật)', async () => {
    const h = makeHandlers();
    renderHook(() => useConversationSSE('c1', h));
    await act(async () => { fakeES.fire('open'); });
    await waitFor(() => expect(h.calls.applyFullState.length).toBe(1));
  });

  it('chunk đúng thứ tự → appendText theo thứ tự', async () => {
    const h = makeHandlers();
    renderHook(() => useConversationSSE('c1', h));
    await act(async () => {
      fakeES.fire('open');
      fakeES.emit(delta(1, 't1', 'A '));
      fakeES.emit(delta(2, 't1', 'B '));
      fakeES.emit(delta(3, 't1', 'C'));
    });
    expect(h.calls.appendText.map((c) => c[1])).toEqual(['A ', 'B ', 'C']);
  });

  it('chunk đến LỆCH thứ tự → buffer rồi flush đúng', async () => {
    const h = makeHandlers();
    renderHook(() => useConversationSSE('c1', h));
    await act(async () => {
      fakeES.fire('open');
      fakeES.emit(delta(3, 't1', 'C'));   // đến trước — vào buffer
      fakeES.emit(delta(1, 't1', 'A '));  // flush A
      fakeES.emit(delta(2, 't1', 'B '));  // flush B rồi C
    });
    expect(h.calls.appendText.map((c) => c[1])).toEqual(['A ', 'B ', 'C']);
  });

  it('chunk TRÙNG seq → bỏ (dedup)', async () => {
    const h = makeHandlers();
    renderHook(() => useConversationSSE('c1', h));
    await act(async () => {
      fakeES.fire('open');
      fakeES.emit(delta(1, 't1', 'A '));
      fakeES.emit(delta(1, 't1', 'A '));  // trùng → bỏ
      fakeES.emit(delta(2, 't1', 'B '));
    });
    expect(h.calls.appendText.map((c) => c[1])).toEqual(['A ', 'B ']);
  });

  it('done.full_text → turnDone với toàn văn (van tự lành)', async () => {
    const h = makeHandlers();
    renderHook(() => useConversationSSE('c1', h));
    await act(async () => {
      fakeES.fire('open');
      fakeES.emit(delta(1, 't1', 'Chào '));
      fakeES.emit(delta(2, 't1', '', true, 'Chào bạn (bản DB)'));
    });
    expect(h.calls.turnDone).toEqual([['t1', 'Chào bạn (bản DB)']]);
  });

  it('task.created + task.status → upsertTask; conversation.status → setConversationStatus', async () => {
    const h = makeHandlers();
    renderHook(() => useConversationSSE('c1', h));
    const task: OrchTask = { id: 't', conv_id: 'c1', role: 'credit', title: 'x', status: 'running' };
    await act(async () => {
      fakeES.fire('open');
      fakeES.emit(taskEv('task.created', task));
      fakeES.emit(taskEv('task.status', { ...task, status: 'done' }));
      fakeES.emit({ type: 'conversation.status', conversation_id: 'c1', seq: null, ts: '', data: { status: 'done' } });
    });
    expect(h.calls.upsertTask.length).toBe(2);
    expect((h.calls.upsertTask[1][0] as OrchTask).status).toBe('done');
    expect(h.calls.setConversationStatus).toEqual([['done']]);
  });

  it('card event → upsertCard với full card row', async () => {
    const h = makeHandlers();
    renderHook(() => useConversationSSE('c1', h));
    const card = { id: 'card1', conv_id: 'c1', task_id: 't', type: 'metric', ts: '', title: 'DSCR', items: [] };
    await act(async () => {
      fakeES.fire('open');
      fakeES.emit({ type: 'card', conversation_id: 'c1', seq: null, ts: '', data: { card } });
    });
    expect(h.calls.upsertCard.length).toBe(1);
    expect((h.calls.upsertCard[0][0] as { id: string }).id).toBe('card1');
  });

  it('approval.decided event → approvalDecided với phieu', async () => {
    const h = makeHandlers();
    renderHook(() => useConversationSSE('c1', h));
    const phieu = { id: 'appr1', action: 'disburse', status: 'approved', decided_by: 'admin', reason: 'ok' };
    await act(async () => {
      fakeES.fire('open');
      fakeES.emit({ type: 'approval.decided', conversation_id: 'c1', seq: null, ts: '', data: { phieu } });
    });
    expect(h.calls.approvalDecided.length).toBe(1);
    expect((h.calls.approvalDecided[0][0] as { id: string }).id).toBe('appr1');
  });

  it('toolcall event → addTrace {kind:tool} với id (dedup)', async () => {
    const h = makeHandlers();
    renderHook(() => useConversationSSE('c1', h));
    await act(async () => {
      fakeES.fire('open');
      fakeES.emit({ type: 'toolcall', conversation_id: 'c1', seq: null, ts: '', data: { id: 'tc1', task_id: 't', tool: 'credit_assess', summary: 'DSCR C001' } });
    });
    expect(h.calls.addTrace.length).toBe(1);
    const it0 = h.calls.addTrace[0][0] as { kind: string; id: string; tool: string };
    expect(it0.kind).toBe('tool');
    expect(it0.id).toBe('tc1');
    expect(it0.tool).toBe('credit_assess');
  });

  it('thinking event → addTrace {kind:thinking}; text rỗng → bỏ qua', async () => {
    const h = makeHandlers();
    renderHook(() => useConversationSSE('c1', h));
    await act(async () => {
      fakeES.fire('open');
      fakeES.emit({ type: 'thinking', conversation_id: 'c1', seq: null, ts: 't1', data: { task_id: null, text: 'đang cân nhắc DSCR' } });
      fakeES.emit({ type: 'thinking', conversation_id: 'c1', seq: null, ts: 't2', data: { task_id: null, text: '   ' } }); // rỗng → bỏ
    });
    expect(h.calls.addTrace.length).toBe(1);
    expect((h.calls.addTrace[0][0] as { kind: string; text: string }).kind).toBe('thinking');
  });

  it('frame malformed (JSON hỏng) → không crash, bỏ qua', async () => {
    const h = makeHandlers();
    renderHook(() => useConversationSSE('c1', h));
    await act(async () => {
      fakeES.fire('open');
      fakeES.onmessage?.({ data: '{broken json' });
      fakeES.emit(delta(1, 't1', 'OK'));
    });
    expect(h.calls.appendText.map((c) => c[1])).toEqual(['OK']);
  });

  it('seq=null trên chat.delta → bỏ (cần seq để ghép — CONTRACT §4)', async () => {
    const h = makeHandlers();
    renderHook(() => useConversationSSE('c1', h));
    await act(async () => {
      fakeES.fire('open');
      fakeES.emit(delta(null, 't1', 'X'));  // seq null → drop
    });
    expect(h.calls.appendText.length).toBe(0);
  });
});
