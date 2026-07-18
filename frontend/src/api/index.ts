// api/index.ts — cổng duy nhất app dùng để nói chuyện với "backend". Cờ VITE_USE_MOCK_API
// chọn mock hay REST thật — MẶC ĐỊNH mock (bật) khi backend T1-3 chưa sẵn. Đặt
// VITE_USE_MOCK_API=false trong .env (hoặc export trước khi `npm run dev`) để ráp API thật.
// Mọi report/log PHẢI khai trạng thái cờ này (CLAUDE.md nghề FE — mock sau CỜ ENV tắt-được).

import { apiClient, ApiRequestError } from './client';
import { createMockEventSource, mockBackend, type MinimalEventSource } from './mock';
import type { ApprovalRow, AuditRow, AuthUser, CompareResult, Conversation, ConversationFullState, FormSubmitResult, LoginResult, ModelsResponse, NotificationItem } from '../types';

export const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API !== 'false';

export interface ConversationApi {
  login(username: string, password: string): Promise<LoginResult>;
  register(username: string, password: string, email?: string): Promise<LoginResult>;
  me(): Promise<{ user: AuthUser }>;
  listConversations(): Promise<Conversation[]>;
  createConversation(title: string, provider?: string, model?: string): Promise<Conversation>;
  getConversation(id: string): Promise<ConversationFullState>;
  sendChat(id: string, content: string): Promise<void>;
  decideApproval(id: string, decision: 'approved' | 'rejected', reason: string): Promise<unknown>;
  auditByConv(convId: string): Promise<AuditRow[]>;
  auditByTask(taskId: string): Promise<AuditRow[]>;
  interruptTask(convId: string, taskId: string): Promise<unknown>;
  // Control Tower (T4-6)
  listApprovals(status?: string): Promise<ApprovalRow[]>;
  auditFiltered(filters?: Record<string, string>): Promise<AuditRow[]>;
  getModels(): Promise<ModelsResponse>;
  runCompare(question: string): Promise<CompareResult>;
  // Form intake + bell (T9-3)
  submitForm(convId: string, cardId: string, values: Record<string, string>): Promise<FormSubmitResult>;
  getNotifications(): Promise<NotificationItem[]>;
  openEventSource(convId: string): MinimalEventSource;
}

const mockApi: ConversationApi = {
  async login(username: string) {
    // mock không auth — chấp nhận mọi credential, trả role theo username (admin→admin, còn lại user).
    return { token: 'mock-token', user: { username, role: username === 'admin' ? 'admin' as const : 'user' as const } };
  },
  async register(username: string) {
    // mock đăng ký: khách MỚI → role customer + owner_id giả (như /register thật auto-login).
    return { token: 'mock-token', user: { username, role: 'customer' as const, owner_id: null } };
  },
  async me() {
    // mock: luôn "chưa login" → App hiện Login (mock mode dùng để test luồng Login). Mock không
    // có DEV_SKIP_AUTH. Ném 401-shape để App bắt như /me thật khi flag OFF.
    throw new ApiRequestError(401, { code: 'unauthorized', message: 'mock: chưa đăng nhập', hint: 'đăng nhập', retryable: false }, 'unauthorized');
  },
  async listConversations() {
    return mockBackend.listConversations();
  },
  async createConversation(title: string, provider?: string, model?: string) {
    return mockBackend.createConversation(title, provider, model);
  },
  async getConversation(id: string) {
    return mockBackend.getFullState(id);
  },
  async sendChat(id: string, content: string) {
    await mockBackend.sendChat(id, content);
  },
  async decideApproval(id: string, decision: 'approved' | 'rejected', reason: string) {
    await mockBackend.decideApproval(id, decision, reason);
  },
  async auditByConv(convId: string) {
    return mockBackend.auditByConv(convId);
  },
  async auditByTask(taskId: string) {
    return mockBackend.auditByTask(taskId);
  },
  async interruptTask(convId: string, taskId: string) {
    return mockBackend.interruptTask(convId, taskId);
  },
  async listApprovals(status = 'pending') {
    return mockBackend.listApprovals(status);
  },
  async auditFiltered(filters: Record<string, string> = {}) {
    return mockBackend.auditFiltered(filters);
  },
  async getModels() {
    return mockBackend.getModels();
  },
  async runCompare(question: string) {
    return mockBackend.runCompare(question);
  },
  async submitForm(convId: string, cardId: string, values: Record<string, string>) {
    return mockBackend.submitForm(convId, cardId, values);
  },
  async getNotifications() {
    return mockBackend.getNotifications();
  },
  openEventSource(convId: string) {
    return createMockEventSource(convId);
  },
};

// wrap DOM EventSource → MinimalEventSource (bỏ event-arg, chỉ chuyển .data + tín hiệu open/error).
function browserEventSource(convId: string): MinimalEventSource {
  const src = new EventSource(`/api/conversations/${convId}/sse`, { withCredentials: true });
  const es: MinimalEventSource = {
    onopen: null,
    onmessage: null,
    onerror: null,
    close: () => src.close(),
  };
  src.onopen = () => es.onopen?.();
  // heartbeat backend = DATA-frame `data:{"type":"ping",...}` (event MẶC ĐỊNH, không named) → vào
  // onmessage như mọi event khác. Hook parse type==='ping' → reset watchdog + bỏ qua render. D-54.
  src.onmessage = (ev: MessageEvent) => es.onmessage?.({ data: String(ev.data) });
  src.onerror = () => es.onerror?.();
  return es;
}

const realApi: ConversationApi = {
  login: apiClient.login,
  register: apiClient.register,
  me: apiClient.me,
  listConversations: apiClient.listConversations,
  createConversation: apiClient.createConversation,
  getConversation: apiClient.getConversation,
  sendChat: apiClient.sendChat,
  decideApproval: apiClient.decideApproval,
  auditByConv: apiClient.auditByConv,
  auditByTask: apiClient.auditByTask,
  interruptTask: apiClient.interruptTask,
  listApprovals: apiClient.listApprovals,
  auditFiltered: apiClient.auditFiltered,
  getModels: apiClient.getModels,
  runCompare: apiClient.runCompare,
  submitForm: apiClient.submitForm,
  getNotifications: apiClient.getNotifications,
  openEventSource: browserEventSource,
};

export const conversationApi: ConversationApi = USE_MOCK_API ? mockApi : realApi;
