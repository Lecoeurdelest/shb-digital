// api/mock.ts — mock server-shape đúng contract T1-3 Exports, TẮT ĐƯỢC bằng env
// VITE_USE_MOCK_API=false (mặc định true khi backend chưa sẵn — mọi báo cáo khai trạng thái cờ).
// Mô phỏng: tạo ca → gõ câu hỏi chứa "C001"/"DSCR" → main "dispatch" task credit → task done
// kèm DSCR=3.709 có nguồn → main stream câu trả lời tổng hợp qua chat.delta.
// Đây LÀ đường dây thay cho backend thật — swap: đổi VITE_USE_MOCK_API=false, không đụng UI.

import type {
  ApprovalRow,
  AuditRow,
  Card,
  ChatDeltaData,
  CompareResult,
  Conversation,
  ConversationFullState,
  Assessment,
  FormSubmitResult,
  Message,
  ModelsResponse,
  NotificationItem,
  OrchTask,
  SSEEnvelope,
  StatsResponse,
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
  cards: Card[];
  listeners: Set<(ev: SSEEnvelope) => void>;
}

class MockBackend {
  private rooms = new Map<string, MockRoom>();
  private turnText = new Map<string, string>(); // tích lũy text trọn lượt (cho full_text ở done)

  // reset toàn bộ state — test-isolation (mockBackend là singleton module-level; không reset thì
  // rooms/tasks leak giữa test, ca cũ auto-select lúc mount làm panel task test khác hiện nhầm).
  reset(): void {
    this.rooms.clear();
    this.turnText.clear();
  }

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

  // provider/model optional (D-45b c) — mock chấp nhận để khớp signature thật; lưu để phản ánh nếu cần.
  createConversation(title: string, provider?: string, model?: string): Conversation {
    const id = uid('c');
    const conv: Conversation = {
      id,
      title: title || `Ca ${this.rooms.size + 1}`,
      status: 'idle',
      created_at: nowIso(),
      ...(provider ? { provider } : {}),
      ...(model ? { model } : {}),
    };
    this.rooms.set(id, { conversation: conv, messages: [], tasks: [], cards: [], listeners: new Set() });
    return conv;
  }

  getFullState(convId: string): ConversationFullState {
    const r = this.room(convId);
    return {
      conversation: r.conversation,
      messages: r.messages,
      tasks: r.tasks,
      cards: r.cards,
    };
  }

  subscribe(convId: string, cb: (ev: SSEEnvelope) => void): () => void {
    // subscribing to a room we don't know about yet is fine — room may be created after mount
    let r = this.rooms.get(convId);
    if (!r) {
      r = { conversation: { id: convId, title: convId, status: 'idle', created_at: nowIso() }, messages: [], tasks: [], cards: [], listeners: new Set() };
      this.rooms.set(convId, r);
    }
    r.listeners.add(cb);
    return () => r!.listeners.delete(cb);
  }

  // ── Control Tower (T4-6) — mock data giả đúng shape ──
  async listApprovals(status: string): Promise<ApprovalRow[]> {
    // gom phiếu approval từ mọi room (card type=approval) → row queue.
    const out: ApprovalRow[] = [];
    for (const r of this.rooms.values()) {
      for (const c of r.cards) {
        if (c.type === 'approval' && (status === 'all' || c.status === status)) {
          out.push({
            id: String(c.approval_id ?? c.id), conv_id: r.conversation.id, task_id: c.task_id ?? null,
            action: String(c.action ?? 'disburse'), payload: { items: c.items ?? [] },
            status: (c.status as ApprovalRow['status']) ?? 'pending', decided_by: (c.decided_by as string) ?? null,
          });
        }
      }
    }
    return out;
  }

  async auditFiltered(filters: Record<string, string>): Promise<AuditRow[]> {
    if (filters.conv_id) return this.auditByConv(filters.conv_id);
    if (filters.task_id) return this.auditByTask(filters.task_id);
    return [];
  }

  async getModels(): Promise<ModelsResponse> {
    return {
      providers: [
        { name: 'claude-cli', kind: 'subscription', base_url: null, models: ['haiku', 'sonnet', 'opus'], default: true, has_key: true, note: 'đường chính (mock)' },
        { name: 'zai', kind: 'api', base_url: 'https://api.z.ai', models: ['glm-4.6', 'glm-4.5'], default: false, has_key: true, note: 'GLM z.ai (mock)' },
      ],
      default: 'claude-cli',
    };
  }

  // ── Form intake khách mới (T9-3): submitForm flip card pending→submitted + emit card update ──
  async submitForm(convId: string, cardId: string, values: Record<string, string>): Promise<FormSubmitResult> {
    await delay(MOCK_LATENCY_MS);
    const r = this.room(convId);
    const card = r.cards.find((c) => c.id === cardId && c.type === 'form');
    if (!card) throw new ApiErrorLike(404, 'not_found', 'Không tìm thấy form hồ sơ (mock).');
    if (card.status === 'submitted') throw new ApiErrorLike(409, 'form_already_submitted', 'Hồ sơ đã được nộp (mock).');
    // validate thiếu field bắt buộc (mock: full_name + monthly_income tiêu biểu)
    const required = ((card.fields as { name: string; required: boolean }[]) ?? []).filter((f) => f.required).map((f) => f.name);
    const missing = required.filter((n) => !String(values[n] ?? '').trim());
    if (missing.length) throw new ApiErrorLike(400, 'missing_fields', `Thiếu thông tin bắt buộc: ${missing.join(', ')} (mock).`);
    // flip submitted + emit card update (SSE) → FE render read-only
    card.status = 'submitted';
    this.emit(convId, envelope(convId, 'card', { card }));
    return { owner_id: 'C9' + Math.floor(Math.random() * 900 + 100), customer_created: true };
  }

  // bell thông báo khách (T9-3 · T9-2 shape). Mock: 2 sự kiện gần đây.
  async getNotifications(): Promise<NotificationItem[]> {
    await delay(MOCK_LATENCY_MS);
    const anyConv = [...this.rooms.keys()][0] ?? uid('c');
    return [
      { type: 'approval_decided', title: 'Khoản vay L001 đã được ngân hàng duyệt', ts: nowIso(), conv_id: anyConv },
      { type: 'disbursed', title: 'Giải ngân 500 triệu vào tài khoản của bạn', ts: nowIso(), conv_id: anyConv },
    ];
  }

  // ── Stats + assessments (S13 T13-2/T13-3) ──
  async getStats(window: 'today' | '7d' = 'today'): Promise<StatsResponse> {
    await delay(MOCK_LATENCY_MS);
    // số phân bố gần thực; 7d lớn hơn today (delta dương). Không series (spark optional theo dispatch).
    const mul = window === '7d' ? 6 : 1;
    return {
      window,
      approvals: { approved: 12 * mul, rejected: 3 * mul, pending: 5, auto: 7 * mul },
      assessments: { green: 9 * mul, yellow: 6 * mul, red: 2 * mul },
      conversations: { total: 20 * mul, active: 3 },
      delta: { approvals_total: window === '7d' ? 14 : 4, assessments_total: window === '7d' ? -3 : 2 },
    };
  }

  async listAssessments(owner?: string, limit = 50): Promise<Assessment[]> {
    await delay(MOCK_LATENCY_MS);
    const all: Assessment[] = [
      {
        id: 'as_001', owner_id: 'C001', loan_type: 'Thế chấp', loan_amount_vnd: 5_000_000_000, lane: 'green',
        basis: 'lane_policy: green — DSCR ≥ 1.2, LTV ≤ 70%, CIC nhóm 1.',
        created_at: '2026-07-19T09:12:00',
        criteria: [
          { key: 'DSCR', level: 'pass', detail: 'DSCR 1.501 ≥ ngưỡng 1.2 (credit_assess).' },
          { key: 'LTV', level: 'pass', detail: 'LTV 62% ≤ 70% (tài sản định giá 8 tỷ).' },
          { key: 'CIC', level: 'pass', detail: 'Nhóm 1 — lịch sử tín dụng tốt (credit_cic_get).' },
        ],
      },
      {
        id: 'as_002', owner_id: 'C029', loan_type: 'Tín chấp', loan_amount_vnd: 800_000_000, lane: 'yellow',
        basis: 'lane_policy: yellow — DSCR biên, cần bổ sung tài sản đảm bảo.',
        created_at: '2026-07-19T08:40:00',
        criteria: [
          { key: 'DSCR', level: 'yellow', detail: 'DSCR 1.05 — dưới ngưỡng an toàn 1.2, sát rủi ro.' },
          { key: 'LTV', level: 'pass', detail: 'LTV 45% ≤ 70%.' },
          { key: 'CIC', level: 'pass', detail: 'Nhóm 1.' },
        ],
      },
      {
        id: 'as_003', owner_id: 'DN2024001', loan_type: 'Thế chấp DN', loan_amount_vnd: 12_000_000_000, lane: 'red',
        basis: 'lane_policy: red — DSCR < 1.0, giấy tờ pháp lý thiếu (pháp chế chặn).',
        created_at: '2026-07-19T07:55:00',
        criteria: [
          { key: 'DSCR', level: 'red', detail: 'DSCR 0.62 < 1.0 — không đủ dòng tiền trả nợ.' },
          { key: 'Pháp lý', level: 'red', detail: 'Thiếu giấy chứng nhận quyền sử dụng đất (check_documents).' },
          { key: 'CIC', level: 'yellow', detail: 'Nhóm 2 — có nợ quá hạn nhẹ.' },
        ],
      },
    ];
    const filtered = owner ? all.filter((a) => a.owner_id === owner) : all;
    return filtered.slice(0, limit);
  }

  async runCompare(question: string): Promise<CompareResult> {
    await delay(MOCK_LATENCY_MS * 3);
    return {
      single: { text: `[Single-agent] Trả lời trực tiếp cho: ${question}. DSCR ước ~0.24, không đủ điều kiện.`, duration_s: 4.2, tool_calls: 0, cards: 0, conv_id: null },
      multi: { text: `[Multi-agent] Đội thẩm định: DSCR 0.236 (credit_assess), CIC nhóm 1, khuyến nghị vay nhỏ hơn — có nguồn từng số.`, duration_s: 38.5, tool_calls: 4, cards: 2, conv_id: uid('c') },
    };
  }

  // trace history toàn ca (TraceBlock reload) — mock trả vài tool-call giả (main + sub credit).
  async auditByConv(convId: string): Promise<AuditRow[]> {
    const r = this.rooms.get(convId);
    const creditTask = r?.tasks.find((t) => t.role === 'credit');
    const mk = (taskId: string | null, actor: string, tool: string, input: Record<string, unknown>): AuditRow => ({
      id: uid('au'), task_id: taskId, conv_id: convId, ts: nowIso(), actor, tool, input, output: {}, cost: null,
    });
    return [
      mk(null, 'main', 'orch_dispatch', { role: 'credit', input: 'C001' }),
      ...(creditTask
        ? [
            mk(creditTask.id, 'credit', 'cust_get', { customer_id: 'C001' }),
            mk(creditTask.id, 'credit', 'credit_assess', { owner_id: 'C001', loan_amount_vnd: 5_000_000_000 }),
          ]
        : []),
    ];
  }

  // trace history 1 sub (SubAgentView) — mock trả vài tool-call giả đúng shape AuditRow (T4-1).
  async auditByTask(taskId: string): Promise<AuditRow[]> {
    // tìm task để biết role + conv
    let role = 'credit';
    let convId = '';
    for (const r of this.rooms.values()) {
      const t = r.tasks.find((x) => x.id === taskId);
      if (t) { role = t.role; convId = r.conversation.id; break; }
    }
    const mk = (tool: string, input: Record<string, unknown>, output: Record<string, unknown>): AuditRow => ({
      id: uid('au'), task_id: taskId, conv_id: convId, ts: nowIso(), actor: role, tool, input, output, cost: null,
    });
    return [
      mk('cust_get', { customer_id: 'C001' }, { name: 'Nguyễn Văn An', income: 30_000_000 }),
      mk('credit_cic_get', { owner_id: 'C001' }, { cic_group: 1 }),
      mk('credit_assess', { owner_id: 'C001', loan_amount_vnd: 5_000_000_000 }, { dscr: 3.709 }),
    ];
  }

  // huỷ 1 sub (mock): task→failed(cancel) + emit task.status. task không running → 409.
  async interruptTask(convId: string, taskId: string): Promise<{ cancelled: boolean }> {
    const r = this.room(convId);
    const task = r.tasks.find((t) => t.id === taskId);
    if (!task) throw new ApiErrorLike(404, 'not_found', 'Task không tồn tại (mock)');
    if (task.status !== 'running' && task.status !== 'queued') {
      throw new ApiErrorLike(409, 'task_not_running', 'Sub không còn chạy (mock)');
    }
    await delay(MOCK_LATENCY_MS);
    const updated: OrchTask = { ...task, status: 'failed', result: { reason: 'Đã huỷ bởi người dùng' }, ended_at: nowIso() };
    r.tasks = r.tasks.map((t) => (t.id === taskId ? updated : t));
    this.emit(convId, envelope(convId, 'task.status', { task: updated }));
    return { cancelled: true };
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

    // ── Nhánh FORM INTAKE (D-57 T9-3): khách mới hỏi vay → MAIN present_form → card type 'form' ──
    if (/(hồ sơ|đăng ký hồ sơ|form|thu thập|khai báo|vay.*mới|mở hồ sơ)/i.test(question)) {
      await delay(MOCK_LATENCY_MS);
      await this.streamText(convId, turnId, seq, 'Dạ, để bắt đầu em cần thu thập một số thông tin hồ sơ của anh/chị. Mời điền form bên phải ạ.', true);
      await delay(MOCK_LATENCY_MS);
      const card: Card = {
        id: uid('card'), conv_id: convId, task_id: null, type: 'form', ts: nowIso(),
        title: 'Hồ sơ vay — thông tin khách hàng', status: 'pending',
        fields: [
          { name: 'full_name', label: 'Họ và tên', type: 'text', required: true },
          { name: 'id_number', label: 'Số CMND/CCCD', type: 'text', required: true },
          { name: 'address', label: 'Địa chỉ thường trú', type: 'text', required: true },
          { name: 'occupation', label: 'Nghề nghiệp', type: 'text', required: true },
          { name: 'monthly_income', label: 'Thu nhập hàng tháng (VND)', type: 'number', required: true },
          { name: 'loan_purpose', label: 'Mục đích vay', type: 'text', required: true },
        ],
      };
      this.pushCard(convId, card);
      return;
    }

    // Trigger nhánh FAILED để drive contract §4b (test/demo được) — từ khoá trong câu hỏi.
    const mainFail = /(main fail|lỗi main|quá tải|hết trần)/i.test(question);
    const subFail = /(sub fail|credit fail|lỗi tín dụng|timeout)/i.test(question);
    const wantsDisburse = /(giải ngân|disburse|duyệt vay|phê duyệt)/i.test(question);
    const wantsCredit = /dscr|c001|tín dụng|vay/i.test(question);

    // ── Nhánh PHANH (D-40 happy-path): câu "giải ngân" → Ops gọi disburse → wrapper phanh chặn →
    //    VỎ tự sinh card approval (type='approval') + conversation.status=waiting_approval. Chờ admin
    //    duyệt (decideApproval). Mock mô phỏng đúng shape T3-1 §E cho FE render panel. ──
    if (wantsDisburse) {
      await delay(MOCK_LATENCY_MS);
      const opener = 'Dạ, để em xử lý giải ngân cho khoản vay này… Thao tác cần người có thẩm quyền duyệt ạ.';
      await this.streamText(convId, turnId, seq, opener, true);
      await delay(MOCK_LATENCY_MS);
      // card approval VỎ tự sinh (id vỏ-inject = approval_id phiếu). task_id null (main dispatch ops).
      const approvalPhieuId = uid('appr');
      const card: Card = {
        id: uid('card'), conv_id: convId, task_id: null, type: 'approval', ts: nowIso(),
        title: 'Phê duyệt giải ngân', action: 'Giải ngân khoản vay L001',
        approval_id: approvalPhieuId, status: 'pending',
        items: [
          { label: 'Khoản vay', value: 'L001' },
          { label: 'Số tiền', value: '5,000,000,000 VND' },
          { label: 'Khách hàng', value: 'DN Gỗ Việt Phát (B001)' },
        ],
        options: ['Duyệt', 'Từ chối'],
      };
      this.pushCard(convId, card);
      this.emit(convId, envelope(convId, 'approval.pending', { phieu: { id: approvalPhieuId, action: 'disburse', status: 'pending' } }));
      r.conversation.status = 'waiting_approval';
      this.emit(convId, envelope(convId, 'conversation.status', { status: 'waiting_approval' }));
      return;
    }

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
      // trace F1 (D-43): main thinking + dispatch tool + sub tool-calls (mock đúng shape T4-1/T4-2)
      this.emit(convId, envelope(convId, 'thinking', { task_id: null, text: 'Yêu cầu cần thẩm định tín dụng — giao chuyên gia Credit tra hồ sơ C001.' }));
      this.emit(convId, envelope(convId, 'toolcall', { id: uid('tc'), task_id: null, tool: 'orch_dispatch', summary: 'role=credit, C001' }));
      this.emit(convId, envelope(convId, 'toolcall', { id: uid('tc'), task_id: task.id, tool: 'cust_get', summary: 'customer_id=C001' }));
      this.emit(convId, envelope(convId, 'toolcall', { id: uid('tc'), task_id: task.id, tool: 'credit_cic_get', summary: 'C001' }));
      this.emit(convId, envelope(convId, 'toolcall', { id: uid('tc'), task_id: task.id, tool: 'credit_assess', summary: 'C001, khoản vay 5 tỷ' }));
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

      // credit sub present card metric (DSCR có nguồn) — shape đúng CONTRACT §3 (value mixed, pass nullable)
      this.presentCard(convId, task.id, 'metric', 'Chỉ số thẩm định — C001', [
        { name: 'DSCR', value: dscr, threshold: '>= 1.2', pass: true, source: 'credit_assess' },
        { name: 'Nhóm CIC', value: 1, threshold: 'nhóm 1-2', pass: true, source: 'credit_cic_get' },
        { name: 'Thu nhập/tháng', value: '30,000,000 VND', threshold: 'N/A', pass: null, source: 'cust_get' },
        { name: 'Nợ hiện tại/tháng', value: '8,088,576 VND', threshold: 'N/A', pass: null, source: 'cust_get' },
      ]);
      await delay(MOCK_LATENCY_MS);
      // main present thêm options + timeline + document để canvas đủ nhiều loại (mock demo canvas)
      this.presentCard(convId, null, 'options', 'Gói vay phù hợp', [
        { name: 'Vay tiêu dùng 700tr', rate: '13.5%/năm', tenor: '60 tháng', source: 'products_catalog' },
        { name: 'Vay thế chấp 5 tỷ', rate: '9.2%/năm', tenor: '120 tháng', source: 'products_catalog' },
      ], { recommended: 'Vay thế chấp 5 tỷ' });
      this.presentCard(convId, null, 'timeline', 'Lộ trình xử lý', [
        { step: 'Thẩm định tín dụng', owner: 'Tín dụng', eta: 'xong' },
        { step: 'Bổ sung tài sản đảm bảo', owner: 'RM', eta: '2 ngày' },
        { step: 'Trình duyệt + giải ngân', owner: 'Vận hành', eta: '3 ngày' },
      ], { total_days: 5 });

      const answer =
        ` Đã có kết quả từ Tín dụng: DSCR = ${dscr.toFixed(3)} (thu nhập 30tr/tháng, nợ hiện tại 8tr/tháng — nguồn: credit_assess). ` +
        'Bảng chỉ số + gói vay + lộ trình đã trình bên canvas. Cần đối chiếu thêm CIC trước khi kết luận.';
      await this.streamText(convId, turnId, seq, answer, true);
    } else {
      await this.streamText(convId, turnId, seq, ' (mock không nhận diện yêu cầu cần tra tín dụng — gõ câu có "C001" hoặc "DSCR" để xem luồng đầy đủ)', true);
    }

    r.conversation.status = 'done';
    this.emit(convId, envelope(convId, 'conversation.status', { status: 'done' }));
  }

  // present 1 card: ghi vào room.cards (persist reload) + emit SSE card event. id VỎ-inject (mock sinh).
  // extra = field top-level tuỳ type (recommended, total_days, flags...).
  private presentCard(convId: string, taskId: string | null, type: string, title: string, items: unknown[], extra: Record<string, unknown> = {}): void {
    const r = this.room(convId);
    const card: Card = { id: uid('card'), conv_id: convId, task_id: taskId, type, ts: nowIso(), title, items, ...extra };
    // replace theo (task_id,type) giữ mới nhất (canvas-present §4) — mock giữ nhất quán với FE
    r.cards = r.cards.filter((c) => !(c.task_id === taskId && c.type === type));
    r.cards.push(card);
    this.emit(convId, envelope(convId, 'card', { card }));
  }

  // ghi card đã dựng sẵn (approval — vỏ tự sinh, không replace-by-type vì mỗi phiếu 1 card riêng).
  private pushCard(convId: string, card: Card): void {
    this.room(convId).cards.push(card);
    this.emit(convId, envelope(convId, 'card', { card }));
  }

  // admin quyết phiếu (mock — mô phỏng T3-2): cập nhật card approval status + emit approval.decided
  // + card mới (KHÔNG xoá card — bằng chứng §6) + resume (conversation.status). D-40 happy-path.
  async decideApproval(approvalId: string, decision: 'approved' | 'rejected', reason: string): Promise<void> {
    // tìm ĐÚNG conv chứa card approval có approval_id này (mock quyết từ queue có thể khác conv đang mở)
    let target: MockRoom | undefined;
    let card: Card | undefined;
    for (const room of this.rooms.values()) {
      const c = room.cards.find((x) => x.type === 'approval' && x.approval_id === approvalId);
      if (c) { target = room; card = c; break; }
    }
    if (!target || !card) throw new ApiErrorLike(404, 'not_found', 'Phiếu không tồn tại (mock)');
    if (card.status !== 'pending') throw new ApiErrorLike(409, 'approval_already_decided', 'Phiếu đã được quyết (mock)');

    await delay(MOCK_LATENCY_MS);
    // decision đã là 'approved'|'rejected' (chốt backend T3-2) — dùng thẳng làm card.status.
    card.status = decision;
    card.decided_by = 'admin';
    if (reason) card.reason = reason;
    card.ts = nowIso();
    const cid = target.conversation.id;
    this.emit(cid, envelope(cid, 'card', { card }));
    this.emit(cid, envelope(cid, 'approval.decided', { phieu: { id: approvalId, action: 'disburse', status: decision, decided_by: 'admin', reason } }));

    // resume (D-42): approved → main giao lại → giải ngân xong → done; rejected → main báo từ chối → failed.
    target.conversation.status = decision === 'approved' ? 'done' : 'failed';
    this.emit(cid, envelope(cid, 'conversation.status', { status: target.conversation.status }));
    if (decision === 'approved') {
      const turnId = uid('turn');
      const seq = { n: 0 };
      await this.streamText(cid, turnId, seq, '✓ Phiếu đã được duyệt — em đã thực hiện giải ngân khoản vay L001. Biên nhận đã lưu.', true);
    }
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
