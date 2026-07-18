// api/index.ts — cổng duy nhất app dùng để nói chuyện với "backend". Cờ VITE_USE_MOCK_API
// chọn mock hay REST thật — MẶC ĐỊNH mock (bật) khi backend T1-3 chưa sẵn. Đặt
// VITE_USE_MOCK_API=false trong .env (hoặc export trước khi `npm run dev`) để ráp API thật.
// Mọi report/log PHẢI khai trạng thái cờ này (CLAUDE.md nghề FE — mock sau CỜ ENV tắt-được).

import { apiClient, ApiRequestError } from './client';
import { createMockEventSource, mockBackend, type MinimalEventSource } from './mock';
import type { AuditRow, AuthUser, Conversation, ConversationFullState, LoginResult } from '../types';

export const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API !== 'false';

export interface ConversationApi {
  login(username: string, password: string): Promise<LoginResult>;
  me(): Promise<{ user: AuthUser }>;
  listConversations(): Promise<Conversation[]>;
  createConversation(title: string): Promise<Conversation>;
  getConversation(id: string): Promise<ConversationFullState>;
  sendChat(id: string, content: string): Promise<void>;
  decideApproval(id: string, decision: 'approved' | 'rejected', reason: string): Promise<unknown>;
  auditByConv(convId: string): Promise<AuditRow[]>;
  auditByTask(taskId: string): Promise<AuditRow[]>;
  interruptTask(convId: string, taskId: string): Promise<unknown>;
  openEventSource(convId: string): MinimalEventSource;
}

const mockApi: ConversationApi = {
  async login(username: string) {
    // mock không auth — chấp nhận mọi credential, trả role theo username (admin→admin, còn lại user).
    return { token: 'mock-token', user: { username, role: username === 'admin' ? 'admin' as const : 'user' as const } };
  },
  async me() {
    // mock: luôn "chưa login" → App hiện Login (mock mode dùng để test luồng Login). Mock không
    // có DEV_SKIP_AUTH. Ném 401-shape để App bắt như /me thật khi flag OFF.
    throw new ApiRequestError(401, { code: 'unauthorized', message: 'mock: chưa đăng nhập', hint: 'đăng nhập', retryable: false }, 'unauthorized');
  },
  async listConversations() {
    return mockBackend.listConversations();
  },
  async createConversation(title: string) {
    return mockBackend.createConversation(title);
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
  src.onmessage = (ev: MessageEvent) => es.onmessage?.({ data: String(ev.data) });
  src.onerror = () => es.onerror?.();
  return es;
}

const realApi: ConversationApi = {
  login: apiClient.login,
  me: apiClient.me,
  listConversations: apiClient.listConversations,
  createConversation: apiClient.createConversation,
  getConversation: apiClient.getConversation,
  sendChat: apiClient.sendChat,
  decideApproval: apiClient.decideApproval,
  auditByConv: apiClient.auditByConv,
  auditByTask: apiClient.auditByTask,
  interruptTask: apiClient.interruptTask,
  openEventSource: browserEventSource,
};

export const conversationApi: ConversationApi = USE_MOCK_API ? mockApi : realApi;
