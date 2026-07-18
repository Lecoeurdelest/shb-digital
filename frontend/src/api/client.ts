// api/client.ts — REST client thật, gọi backend qua contract T1-3 Exports (SPEC §11).
// Success = resource trần (không bọc {success,data}); error = 4-field {code,message,hint,retryable}.
// Auth: S1 bypass (D-13/task T1-4 cho phép bypass + ghi deviation) — không gắn JWT header ở đây.

import type { ApiError, ApprovalRow, Assessment, AuditRow, AuthUser, CompareResult, Conversation, ConversationFullState, FormSubmitResult, LoginResult, ModelsResponse, NotificationItem, StatsResponse } from '../types';

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
  // Authenticate with username/password; server sets httponly JWT cookie on success.
  // login: cookie httponly shb_token do server set (credentials:'include' → browser tự lưu +
  // gửi lại mọi call sau, gồm EventSource withCredentials). CONTRACT §1.
  login(username: string, password: string): Promise<LoginResult> {
    return request<LoginResult>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  },

  // Log out — server clears the httponly cookie so reload no longer auto-authenticates.
  // đăng xuất THẬT (T11-x): POST /api/auth/logout → server delete_cookie shb_token. Sau đó reload =
  // anon (/me 401 → Landing). KHÁC "set anon client-side" cũ (cookie sống → reload tự vào lại = bug).
  logout(): Promise<void> {
    return request<void>('/api/auth/logout', { method: 'POST' });
  },

  // Register a new customer account; returns auth result and sets cookie (auto-login).
  // đăng ký khách mới (D-57 T9-3): {username, password, email?} → 201 {token, user} + cookie auto-login.
  // Lỗi 4-field: 400 bad_username/bad_password/bad_email · 409 username_taken.
  register(username: string, password: string, email?: string): Promise<LoginResult> {
    const body: { username: string; password: string; email?: string } = { username, password };
    if (email) body.email = email;
    return request<LoginResult>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // Fetch the current session user (boot-check); normalizes flat/wrapped payload shapes.
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

  // List enabled auth providers so the UI shows only available login buttons.
  // providers (public): FE render đúng nút login. Google bật = server đủ env (bool-only).
  getAuthProviders(): Promise<{ password: boolean; google: boolean }> {
    return request<{ password: boolean; google: boolean }>('/api/auth/providers');
  },

  // List conversations visible to the current user (server-scoped by role).
  listConversations(): Promise<Conversation[]> {
    return request<Conversation[]>('/api/conversations');
  },

  // Create a conversation; optional provider/model pin the LLM for every turn in it.
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

  // Patch a conversation: rename (title) and/or switch LLM per-turn (provider+model). S15 T15-2/3.
  // PATCH /api/conversations/{id}. Đổi title = rename ca; đổi provider/model = lượt CHAT sau đi model
  // mới (per-turn switch). Ca đang running → BE trả 409 (không đổi giữa lượt). Trả conv đã cập nhật.
  updateConversation(id: string, patch: { title?: string; provider?: string; model?: string }): Promise<Conversation> {
    return request<Conversation>(`/api/conversations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    });
  },

  // Delete a conversation. S15 T15-3. DELETE /api/conversations/{id}. 409 hai loại: phiếu pending
  // chưa quyết / ca đang chạy (BE trả message hint 4-field → FE hiện). 200/204 = xoá xong.
  deleteConversation(id: string): Promise<void> {
    return request<void>(`/api/conversations/${id}`, { method: 'DELETE' });
  },

  // Fetch full conversation state (messages, tasks, cards) — source of truth on reload.
  getConversation(id: string): Promise<ConversationFullState> {
    return request<ConversationFullState>(`/api/conversations/${id}`);
  },

  // Admin decision on an approval ticket (approve/reject) by approval_id.
  // admin quyết phiếu (T3-2 · CONTRACT §11). id = card.approval_id (phiếu vỏ-inject).
  // decision CHỐT "approved"|"rejected" (backend T3-2). Response 200 approval row trần; 409 already_decided.
  decideApproval(id: string, decision: 'approved' | 'rejected', reason: string): Promise<unknown> {
    return request<unknown>(`/api/approvals/${id}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decision, reason }),
    });
  },

  // List approval tickets by status (admin approval queue).
  // list phiếu (approval queue Control Tower — admin). CONTRACT §11.
  listApprovals(status = 'pending'): Promise<ApprovalRow[]> {
    return request<ApprovalRow[]>(`/api/approvals?status=${encodeURIComponent(status)}`);
  },

  // Query the system-wide tool-call audit log with optional filters.
  // audit toàn hệ + filter (Control Tower audit view). filters: conv_id/task_id/tool/actor.
  auditFiltered(filters: Record<string, string> = {}): Promise<AuditRow[]> {
    const qs = new URLSearchParams(filters).toString();
    return request<AuditRow[]>(`/api/audit${qs ? `?${qs}` : ''}`);
  },

  // List providers and their models for the model picker.
  // model/provider list (dropdown D-45b).
  getModels(): Promise<ModelsResponse> {
    return request<ModelsResponse>('/api/models');
  },

  // Dashboard counters for the admin overview tab (window=today|7d).
  // stats tab Tổng quan (S13 T13-2, admin): approvals/assessments/conversations + delta so kỳ trước.
  getStats(window: 'today' | '7d' = 'today'): Promise<StatsResponse> {
    return request<StatsResponse>(`/api/stats?window=${encodeURIComponent(window)}`);
  },

  // List credit assessments (newest-first, cap 100) for the AI-reasoning panel.
  // hồ sơ thẩm định (S13 T13-3, admin): row + criteria 3 trụ + basis (lý do AI). owner/limit optional.
  listAssessments(owner?: string, limit?: number): Promise<Assessment[]> {
    const qs = new URLSearchParams();
    if (owner) qs.set('owner', owner);
    if (limit) qs.set('limit', String(limit));
    const s = qs.toString();
    return request<Assessment[]>(`/api/assessments${s ? `?${s}` : ''}`);
  },

  // Submit a customer intake form; creates the customer profile on success.
  // khách nộp hồ sơ form (D-57 T9-3) → 200 {owner_id, customer_created}. 400 missing_fields/bad_income
  // · 409 form_already_submitted · 404 (đều 4-field).
  submitForm(convId: string, cardId: string, values: Record<string, string>): Promise<FormSubmitResult> {
    return request<FormSubmitResult>(`/api/conversations/${convId}/form-submit`, {
      method: 'POST',
      body: JSON.stringify({ card_id: cardId, values }),
    });
  },

  // Fetch customer notifications for the bell (404 while the endpoint is not yet deployed).
  // bell thông báo khách (D-57 T9-3 · T9-2). Server T9-2 chưa lên → 404 (bell ẩn im, hook lo).
  getNotifications(): Promise<NotificationItem[]> {
    return request<NotificationItem[]>('/api/notifications');
  },

  // Run the single-agent vs multi-agent comparison (long-running ~90s).
  // compare single vs multi-agent (deliverable #5). Chạy DÀI ~90s → FE loading rõ. body {question}.
  runCompare(question: string): Promise<CompareResult> {
    return request<CompareResult>('/api/compare', {
      method: 'POST',
      body: JSON.stringify({ question }),
    });
  },

  // Fetch persisted tool-call trace for a whole conversation (rehydrate on reload).
  // trace history toàn ca (TraceBlock reload T4-2): GET /api/audit?conv_id → tool_calls persist.
  auditByConv(convId: string): Promise<AuditRow[]> {
    return request<AuditRow[]>(`/api/audit?conv_id=${encodeURIComponent(convId)}`);
  },

  // Fetch persisted tool-call trace for a single sub-agent task (newest-first).
  // trace history 1 sub (SubAgentView T4-3): GET /api/audit?task_id → tool_calls persist newest-first.
  auditByTask(taskId: string): Promise<AuditRow[]> {
    return request<AuditRow[]>(`/api/audit?task_id=${encodeURIComponent(taskId)}`);
  },

  // Cancel a running sub-agent task by task_id.
  // huỷ 1 sub đang chạy (T4-3 · POST interrupt — BE chốt shape). target=task_id. 200 {cancelled} · 404/409.
  interruptTask(convId: string, taskId: string): Promise<unknown> {
    return request<unknown>(`/api/conversations/${convId}/interrupt`, {
      method: 'POST',
      body: JSON.stringify({ target: taskId }),
    });
  },

  // Send a user message into a conversation (202; streamed reply arrives via SSE).
  sendChat(id: string, content: string): Promise<void> {
    return request<void>(`/api/conversations/${id}/chat`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  },
};
