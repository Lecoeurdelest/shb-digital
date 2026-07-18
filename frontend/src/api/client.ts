// api/client.ts — REST client thật, gọi backend qua contract T1-3 Exports (SPEC §11).
// Success = resource trần (không bọc {success,data}); error = 4-field {code,message,hint,retryable}.
// Auth: S1 bypass (D-13/task T1-4 cho phép bypass + ghi deviation) — không gắn JWT header ở đây.

import type { ApiError, ApprovalRow, AuditRow, AuthUser, CompareResult, Conversation, ConversationFullState, LoginResult, ModelsResponse } from '../types';

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

  // boot-check (D-39/T3-0 · D-56): GET /api/me → {username, role, owner_id, user:{...}}.
  // 200 nếu đã login HOẶC DEV_SKIP_AUTH ON → skip Login; 401 → App hiện Login.
  // Map từ TOP-LEVEL (có owner_id — role customer/admin/user); fallback `user` wrap nếu server cũ
  // chỉ trả wrap (owner_id thiếu → null, không crash — defensive D-56).
  async me(): Promise<{ user: AuthUser }> {
    const p = await request<{ username?: string; role?: string; owner_id?: string | null; user?: AuthUser }>('/api/me');
    const username = p.username ?? p.user?.username ?? '';
    const role = (p.role ?? p.user?.role ?? 'user') as AuthUser['role'];
    const owner_id = p.owner_id ?? null;
    return { user: { username, role, owner_id } };
  },

  // providers (public): FE render đúng nút login. Google bật = server đủ env (bool-only).
  getAuthProviders(): Promise<{ password: boolean; google: boolean }> {
    return request<{ password: boolean; google: boolean }>('/api/auth/providers');
  },

  listConversations(): Promise<Conversation[]> {
    return request<Conversation[]>('/api/conversations');
  },

  // Tạo ca. provider/model optional (D-45b c) — bỏ trống = server-default; provider = tên trong
  // GET /api/models, model = 1 string trong models[] của provider đó. Conv lưu → mọi lượt chạy đúng.
  createConversation(title: string, provider?: string, model?: string): Promise<Conversation> {
    const body: { title: string; provider?: string; model?: string } = { title };
    if (provider) body.provider = provider;
    if (model) body.model = model;
    return request<Conversation>('/api/conversations', {
      method: 'POST',
      body: JSON.stringify(body),
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

  // list phiếu (approval queue Control Tower — admin). CONTRACT §11.
  listApprovals(status = 'pending'): Promise<ApprovalRow[]> {
    return request<ApprovalRow[]>(`/api/approvals?status=${encodeURIComponent(status)}`);
  },

  // audit toàn hệ + filter (Control Tower audit view). filters: conv_id/task_id/tool/actor.
  auditFiltered(filters: Record<string, string> = {}): Promise<AuditRow[]> {
    const qs = new URLSearchParams(filters).toString();
    return request<AuditRow[]>(`/api/audit${qs ? `?${qs}` : ''}`);
  },

  // model/provider list (dropdown D-45b).
  getModels(): Promise<ModelsResponse> {
    return request<ModelsResponse>('/api/models');
  },

  // compare single vs multi-agent (deliverable #5). Chạy DÀI ~90s → FE loading rõ. body {question}.
  runCompare(question: string): Promise<CompareResult> {
    return request<CompareResult>('/api/compare', {
      method: 'POST',
      body: JSON.stringify({ question }),
    });
  },

  // trace history toàn ca (TraceBlock reload T4-2): GET /api/audit?conv_id → tool_calls persist.
  auditByConv(convId: string): Promise<AuditRow[]> {
    return request<AuditRow[]>(`/api/audit?conv_id=${encodeURIComponent(convId)}`);
  },

  // trace history 1 sub (SubAgentView T4-3): GET /api/audit?task_id → tool_calls persist newest-first.
  auditByTask(taskId: string): Promise<AuditRow[]> {
    return request<AuditRow[]>(`/api/audit?task_id=${encodeURIComponent(taskId)}`);
  },

  // huỷ 1 sub đang chạy (T4-3 · POST interrupt — BE chốt shape). target=task_id. 200 {cancelled} · 404/409.
  interruptTask(convId: string, taskId: string): Promise<unknown> {
    return request<unknown>(`/api/conversations/${convId}/interrupt`, {
      method: 'POST',
      body: JSON.stringify({ target: taskId }),
    });
  },

  sendChat(id: string, content: string): Promise<void> {
    return request<void>(`/api/conversations/${id}/chat`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  },
};
