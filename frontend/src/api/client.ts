// api/client.ts — REST client thật, gọi backend qua contract T1-3 Exports (SPEC §11).
// Success = resource trần (không bọc {success,data}); error = 4-field {code,message,hint,retryable}.
// Auth: S1 bypass (D-13/task T1-4 cho phép bypass + ghi deviation) — không gắn JWT header ở đây.

import type { ApiError, Conversation, ConversationFullState } from '../types';

export class ApiRequestError extends Error {
  readonly status: number;
  readonly body: ApiError | null;

  constructor(status: number, body: ApiError | null, fallbackMessage: string) {
    super(body?.message ?? fallbackMessage);
    this.name = 'ApiRequestError';
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    // JWT qua cookie (CONTRACT §1 · streaming-sse §4 — EventSource không set custom header,
    // nên cả REST dùng cookie cho nhất quán). S1 có thể bypass auth (deviation), header sẵn.
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    let body: ApiError | null = null;
    try {
      body = await res.json();
    } catch {
      // non-JSON error body (e.g. 404 from routing) — fall through with null body
    }
    throw new ApiRequestError(res.status, body, `HTTP ${res.status}`);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export const apiClient = {
  listConversations(): Promise<Conversation[]> {
    return request<Conversation[]>('/api/conversations');
  },

  createConversation(title: string): Promise<Conversation> {
    return request<Conversation>('/api/conversations', {
      method: 'POST',
      body: JSON.stringify({ title }),
    });
  },

  getConversation(id: string): Promise<ConversationFullState> {
    return request<ConversationFullState>(`/api/conversations/${id}`);
  },

  sendChat(id: string, content: string): Promise<void> {
    return request<void>(`/api/conversations/${id}/chat`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  },
};
