// api/mock.ts — mock server-shape đúng contract T1-3 Exports, TẮT ĐƯỢC bằng env
// VITE_USE_MOCK_API=false (mặc định true khi backend chưa sẵn — mọi báo cáo khai trạng thái cờ).
// Mô phỏng: tạo ca → gõ câu hỏi chứa "C001"/"DSCR" → main "dispatch" task credit → task done
// kèm DSCR=3.709 có nguồn → main stream câu trả lời tổng hợp qua chat.delta.
// Đây LÀ đường dây thay cho backend thật — swap: đổi VITE_USE_MOCK_API=false, không đụng UI.

import type {
  ChatDeltaData,
  Conversation,
  ConversationFullState,
  Message,
  OrchTask,
  SSEEnvelope,
} from '../types';

const MOCK_LATENCY_MS = 220;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function uid(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function nowIso(): string {
  return new Date().toISOString();
}

interface MockRoom {
  conversation: Conversation;
  messages: Message[];
  tasks: OrchTask[];
  listeners: Set<(ev: SSEEnvelope) => void>;
}

class MockBackend {
  private rooms = new Map<string, MockRoom>();
  private turnText = new Map<string, string>(); // tích lũy text trọn lượt (cho full_text ở done)

  private room(id: string): MockRoom {
    const r = this.rooms.get(id);
    if (!r) throw new ApiErrorLike(404, 'not_found', 'Ca không tồn tại (mock)');
    return r;
  }

  private emit(convId: string, ev: SSEEnvelope): void {
    const r = this.rooms.get(convId);
    if (!r) return;
    for (const listener of r.listeners) listener(ev);
  }

  listConversations(): Conversation[] {
    return [...this.rooms.values()].map((r) => r.conversation).sort((a, b) => b.created_at.localeCompare(a.created_at));
  }

  createConversation(title: string): Conversation {
    const id = uid('c');
    const conv: Conversation = {
      id,
      title: title || `Ca ${this.rooms.size + 1}`,
      status: 'idle',
      created_at: nowIso(),
    };
    this.rooms.set(id, { conversation: conv, messages: [], tasks: [], listeners: new Set() });
    return conv;
  }

  getFullState(convId: string): ConversationFullState {
    const r = this.room(convId);
    return {
      conversation: r.conversation,
      messages: r.messages,
      tasks: r.tasks,
    };
  }

  subscribe(convId: string, cb: (ev: SSEEnvelope) => void): () => void {
    // subscribing to a room we don't know about yet is fine — room may be created after mount
    let r = this.rooms.get(convId);
    if (!r) {
      r = { conversation: { id: convId, title: convId, status: 'idle', created_at: nowIso() }, messages: [], tasks: [], listeners: new Set() };
      this.rooms.set(convId, r);
    }
    r.listeners.add(cb);
    return () => r!.listeners.delete(cb);
  }

  async sendChat(convId: string, content: string): Promise<void> {
    const r = this.room(convId);
    const userMsg: Message = {
      id: uid('m'),
      conv_id: convId,
      ts: nowIso(),
      sender: 'user',
      content,
      meta: null,
    };
    r.messages.push(userMsg);
    r.conversation.status = 'running';
    this.emit(convId, envelope(convId, 'conversation.status', { status: 'running' }));

    // fire-and-forget: mô phỏng lượt main (ack ngay, giống 202 thật — §11 T1-3 B flow)
    void this.runMainTurn(convId, content);
  }

  private async runMainTurn(convId: string, question: string): Promise<void> {
    const r = this.room(convId);
    const turnId = uid('turn');
    const seq = { n: 0 }; // seq TĂNG DẦN theo lượt (turn) — hook re-order/dedup theo (turn_id, seq)

    // Trigger nhánh FAILED để drive contract §4b (test/demo được) — từ khoá trong câu hỏi.
    const mainFail = /(main fail|lỗi main|quá tải|hết trần)/i.test(question);
    const subFail = /(sub fail|credit fail|lỗi tín dụng|timeout)/i.test(question);
    const wantsCredit = /dscr|c001|tín dụng|vay/i.test(question);

    // ── Nhánh MAIN FAIL (§4b Gap2 B): main hết trần retry → ghi system message lỗi +
    //    VẪN bắn chat.delta done (full_text = phần đã stream) + conversation.status:failed ──
    if (mainFail) {
      await delay(MOCK_LATENCY_MS);
      // §4b Gap1 (a): main stream phần mở đầu rồi lỗi — VẪN kết lượt bằng done (full_text =
      // phần main ĐÃ nói) để bubble không treo.
      const opener = 'Dạ em đang xử lý…';
      await this.streamText(convId, turnId, seq, opener, true); // persist assistant opener + done
      await delay(MOCK_LATENCY_MS);
      // §4b Gap2 B: nội dung lỗi = message sender='system' persist DB → user thấy trong lịch sử.
      // FE lấy qua full-state refetch (App refetch khi status→failed). Bản thật: BE INSERT messages.
      r.messages.push({
        id: uid('m'), conv_id: convId, ts: nowIso(), sender: 'system',
        content: '⚠ Lượt xử lý gặp lỗi: MAIN hết trần retry khi điều phối. Vui lòng thử lại — nếu lặp lại, báo quản trị.',
        meta: { error: true },
      });
      r.conversation.status = 'failed';
      this.emit(convId, envelope(convId, 'conversation.status', { status: 'failed' }));
      return;
    }

    // 1) main "nhận diện" cần tra credit → dispatch task
    await delay(MOCK_LATENCY_MS);
    let task: OrchTask | null = null;
    if (wantsCredit) {
      task = {
        id: uid('t'), conv_id: convId, role: 'credit',
        title: 'Thẩm định tín dụng — DSCR khách hàng C001',
        status: 'running', input: { customer_id: 'C001' }, result: null,
        queued_at: nowIso(), started_at: nowIso(), ended_at: null, cost: null,
      };
      r.tasks.push(task);
      this.emit(convId, envelope(convId, 'task.created', { task }));
    }

    // 2) main mở lời stream trong lúc chờ sub
    const opener = wantsCredit
      ? 'Dạ để em tra hồ sơ tín dụng của khách hàng C001 trước ạ, chờ em một chút…'
      : 'Dạ em ghi nhận câu hỏi, em đang xử lý ạ…';
    await this.streamText(convId, turnId, seq, opener, false);

    // ── Nhánh SUB FAIL (§4b Gap2 A): task.status='failed' + result.reason. Main VẪN kết
    //    lượt bằng done (§4b Gap1) rồi conversation.status:failed ──
    if (task && subFail) {
      await delay(MOCK_LATENCY_MS * 2);
      task = {
        ...task, status: 'failed',
        result: { reason: 'Sub Tín dụng timeout sau 120s — không lấy được hồ sơ CIC của C001 (nguồn cic_records không phản hồi).' },
        ended_at: nowIso(), cost: { tool_calls: 0 },
      };
      r.tasks = r.tasks.map((t) => (t.id === task!.id ? task! : t));
      this.emit(convId, envelope(convId, 'task.status', { task }));

      const answer = ' Rất tiếc, phần Tín dụng gặp sự cố nên em chưa thể đưa kết luận cho ca này. Chi tiết lỗi hiển thị ở thẻ công việc bên cạnh.';
      await this.streamText(convId, turnId, seq, answer, true);
      r.conversation.status = 'failed';
      this.emit(convId, envelope(convId, 'conversation.status', { status: 'failed' }));
      return;
    }

    if (task) {
      await delay(MOCK_LATENCY_MS * 2);
      // sub credit "xong" — kết quả có nguồn (mock đúng shape credit_assess thật sẽ trả)
      const dscr = 3.709;
      task = {
        ...task, status: 'done',
        result: { dscr, source: 'credit_assess', monthly_income: 30_000_000, monthly_debt: 8_000_000 },
        ended_at: nowIso(), cost: { tool_calls: 1 },
      };
      r.tasks = r.tasks.map((t) => (t.id === task!.id ? task! : t));
      this.emit(convId, envelope(convId, 'task.status', { task }));

      const answer =
        ` Đã có kết quả từ Tín dụng: DSCR = ${dscr.toFixed(3)} (thu nhập 30tr/tháng, nợ hiện tại 8tr/tháng — nguồn: credit_assess). ` +
        'DSCR > 1 nên khả năng trả nợ đạt ngưỡng an toàn cơ bản, cần đối chiếu thêm CIC trước khi kết luận.';
      await this.streamText(convId, turnId, seq, answer, true);
    } else {
      await this.streamText(convId, turnId, seq, ' (mock không nhận diện yêu cầu cần tra tín dụng — gõ câu có "C001" hoặc "DSCR" để xem luồng đầy đủ)', true);
    }

    r.conversation.status = 'done';
    this.emit(convId, envelope(convId, 'conversation.status', { status: 'done' }));
  }

  // Stream 1 đoạn text theo từng "từ". seq TĂNG DẦN xuyên suốt lượt (dùng chung counter cho
  // opener + answer) — chunk cuối của lượt (isFinal) mang done:true + full_text = TRỌN nội dung
  // lượt (opener + answer) để hook chốt bubble assistant chính thức (DB thật là nguồn cuối).
  private async streamText(
    convId: string,
    turnId: string,
    seq: { n: number },
    text: string,
    isFinal: boolean,
  ): Promise<void> {
    const r = this.room(convId);
    const words = text.split(/(?<=\s)/);
    const turnBuf = this.turnText.get(turnId) ?? '';
    let acc = turnBuf;
    for (const w of words) {
      acc += w;
      seq.n += 1;
      this.emit(
        convId,
        envelope(convId, 'chat.delta', { turn_id: turnId, chunk: w, done: false } satisfies ChatDeltaData, seq.n),
      );
      await delay(28);
    }
    this.turnText.set(turnId, acc);

    if (isFinal) {
      const msg: Message = {
        id: uid('m'),
        conv_id: convId,
        ts: nowIso(),
        sender: 'assistant',
        content: acc,
        meta: null,
      };
      r.messages.push(msg);
      seq.n += 1;
      this.emit(
        convId,
        envelope(convId, 'chat.delta', { turn_id: turnId, chunk: '', done: true, full_text: acc } satisfies ChatDeltaData, seq.n),
      );
      this.turnText.delete(turnId);
    }
  }
}

class ApiErrorLike extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function envelope<T>(convId: string, type: SSEEnvelope['type'], data: T, seq: number | null = null): SSEEnvelope<T> {
  return { type, conversation_id: convId, seq, ts: nowIso(), data };
}

export const mockBackend = new MockBackend();

// ── transport SSE tối giản (drop-in cho hook) ──
// Interface chung cho mock (in-memory) và REST thật (wrap DOM EventSource ở realApi).
// Handler không nhận event-object — hook chỉ cần onopen/onerror làm tín hiệu và
// onmessage.data (chuỗi JSON). Giữ hẹp để cả hai transport gán vào cùng type.
export interface MinimalEventSource {
  onopen: (() => void) | null;
  onmessage: ((ev: { data: string }) => void) | null;
  onerror: (() => void) | null;
  close(): void;
}

export function createMockEventSource(convId: string): MinimalEventSource {
  const es: MinimalEventSource = {
    onopen: null,
    onmessage: null,
    onerror: null,
    close() {
      unsubscribe();
    },
  };
  const unsubscribe = mockBackend.subscribe(convId, (ev) => {
    es.onmessage?.({ data: JSON.stringify(ev) });
  });
  // mô phỏng độ trễ mở kết nối thật
  setTimeout(() => es.onopen?.(), 30);
  return es;
}
