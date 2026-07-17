// api/index.ts — cổng duy nhất app dùng để nói chuyện với "backend". Cờ VITE_USE_MOCK_API
// chọn mock hay REST thật — MẶC ĐỊNH mock (bật) khi backend T1-3 chưa sẵn. Đặt
// VITE_USE_MOCK_API=false trong .env (hoặc export trước khi `npm run dev`) để ráp API thật.
// Mọi report/log PHẢI khai trạng thái cờ này (CLAUDE.md nghề FE — mock sau CỜ ENV tắt-được).

import { apiClient } from './client';
import { createMockEventSource, mockBackend, type MinimalEventSource } from './mock';
import type { Conversation, ConversationFullState, LoginResult } from '../types';

export const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API !== 'false';

export interface ConversationApi {
  login(username: string, password: string): Promise<LoginResult>;
  listConversations(): Promise<Conversation[]>;
  createConversation(title: string): Promise<Conversation>;
  getConversation(id: string): Promise<ConversationFullState>;
  sendChat(id: string, content: string): Promise<void>;
  openEventSource(convId: string): MinimalEventSource;
}

const mockApi: ConversationApi = {
  async login(username: string) {
    // mock không auth — chấp nhận mọi credential, trả role theo username (admin→admin, còn lại user).
    return { token: 'mock-token', user: { username, role: username === 'admin' ? 'admin' as const : 'user' as const } };
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
  listConversations: apiClient.listConversations,
  createConversation: apiClient.createConversation,
  getConversation: apiClient.getConversation,
  sendChat: apiClient.sendChat,
  openEventSource: browserEventSource,
};

export const conversationApi: ConversationApi = USE_MOCK_API ? mockApi : realApi;
