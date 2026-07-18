// api/client.ts — REST client thật, gọi backend qua contract T1-3 Exports (SPEC §11).
// Success = resource trần (không bọc {success,data}); error = 4-field {code,message,hint,retryable}.
// Auth: S1 bypass (D-13/task T1-4 cho phép bypass + ghi deviation) — không gắn JWT header ở đây.

import type { ApiError, AuthUser, Conversation, ConversationFullState, LoginResult } from '../types';

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
  // login: cookie httponly shb_token do server set (credentials:'include' → browser tự lưu +
  // gửi lại mọi call sau, gồm EventSource withCredentials). CONTRACT §1.
  login(username: string, password: string): Promise<LoginResult> {
    return request<LoginResult>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  },

  // boot-check (D-39/T3-0): 200 {user} nếu đã login HOẶC DEV_SKIP_AUTH ON → skip Login;
  // 401 (ApiRequestError) nếu chưa login + flag OFF → App bắt lỗi → hiện Login.
  me(): Promise<{ user: AuthUser }> {
    return request<{ user: AuthUser }>('/api/auth/me');
  },

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

  // admin quyết phiếu (T3-2 · CONTRACT §11). id = card.approval_id (phiếu vỏ-inject).
  // decision CHỐT "approved"|"rejected" (backend T3-2). Response 200 approval row trần; 409 already_decided.
  decideApproval(id: string, decision: 'approved' | 'rejected', reason: string): Promise<unknown> {
    return request<unknown>(`/api/approvals/${id}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decision, reason }),
    });
  },

  // list phiếu pending (approval queue Control Tower — admin). CONTRACT §11.
  listApprovals(status = 'pending'): Promise<unknown[]> {
    return request<unknown[]>(`/api/approvals?status=${encodeURIComponent(status)}`);
  },

  sendChat(id: string, content: string): Promise<void> {
    return request<void>(`/api/conversations/${id}/chat`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  },
};
