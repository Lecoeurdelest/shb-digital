// api/client.ts — REST client thật, gọi backend qua contract T1-3 Exports (SPEC §11).
// Success = resource trần (không bọc {success,data}); error = 4-field {code,message,hint,retryable}.
// Auth: S1 bypass (D-13/task T1-4 cho phép bypass + ghi deviation) — không gắn JWT header ở đây.

import type { AgentConfigResponse, ApiError, ApprovalRow, Assessment, AuditRow, AuthUser, CaseListFilters, CaseSummary, CompareResult, Conversation, ConversationFullState, ConversationGroup, CostResponse, CostTrendResponse, FormSubmitResult, LoginResult, ModelsResponse, NotificationItem, ShadowMatchStats, ShadowMismatchFilters, ShadowMismatchPage, StatsResponse, StatsWindow } from '../types';

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

const DEFAULT_REQUEST_TIMEOUT_MS = 20_000;
const LONG_REQUEST_TIMEOUT_MS = 120_000;

function timeoutError(path: string): ApiRequestError {
  return new ApiRequestError(
    0,
    {
      code: 'request_timeout',
      message: 'Backend phản hồi quá lâu.',
      hint: `Thử lại sau khi kiểm tra server dev/API (${path}).`,
      retryable: true,
    },
    'request_timeout',
  );
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS): Promise<T> {
  const controller = !init?.signal && timeoutMs > 0 ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;

  try {
    const res = await fetch(path, {
      ...init,
      signal: init?.signal ?? controller?.signal,
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
  } catch (err) {
    if (controller?.signal.aborted) throw timeoutError(path);
    throw err;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export const apiClient = {
  getAgentConfig(): Promise<AgentConfigResponse> { return request<AgentConfigResponse>('/api/admin/agent-config'); },
  saveAgentPrompt(key: string, content: string): Promise<AgentConfigResponse> {
    return request<AgentConfigResponse>(`/api/admin/agent-config/prompts/${encodeURIComponent(key)}`, { method: 'POST', body: JSON.stringify({ content, activate: true }) });
  },
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
    const p = await request<{ username?: string; role?: string; tenant_id?: string; owner_id?: string | null; user?: AuthUser }>('/api/me');
    const username = p.username ?? p.user?.username ?? '';
    const role = (p.role ?? p.user?.role ?? 'user') as AuthUser['role'];
    const owner_id = p.owner_id ?? null;
    const tenant_id = p.tenant_id ?? p.user?.tenant_id;
    return { user: { username, role, owner_id, ...(tenant_id ? { tenant_id } : {}) } };
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

  listConversationGroups(): Promise<ConversationGroup[]> {
    return request<ConversationGroup[]>('/api/conversation-groups');
  },

  createConversationGroup(name: string): Promise<ConversationGroup> {
    return request<ConversationGroup>('/api/conversation-groups', {
      method: 'POST',
      body: JSON.stringify({ name }),
    });
  },

  updateConversationGroup(id: string, name: string): Promise<ConversationGroup> {
    return request<ConversationGroup>(`/api/conversation-groups/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    });
  },

  deleteConversationGroup(id: string): Promise<void> {
    return request<void>(`/api/conversation-groups/${encodeURIComponent(id)}`, { method: 'DELETE' });
  },

  // Create a conversation; optional provider/model pin the LLM for every turn in it.
  // Tạo ca. provider/model optional (D-45b c) — bỏ trống = server-default; provider = tên trong
  // GET /api/models, model = 1 string trong models[] của provider đó. Conv lưu → mọi lượt chạy đúng.
  createConversation(title: string, provider?: string, model?: string, groupId?: string | null): Promise<Conversation> {
    const body: { title: string; provider?: string; model?: string; group_id?: string | null } = { title };
    if (provider) body.provider = provider;
    if (model) body.model = model;
    if (groupId !== undefined) body.group_id = groupId;
    return request<Conversation>('/api/conversations', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // Patch a conversation: rename (title) and/or switch LLM per-turn (provider+model). S15 T15-2/3.
  // PATCH /api/conversations/{id}. Đổi title = rename ca; đổi provider/model = lượt CHAT sau đi model
  // mới (per-turn switch). Ca đang running → BE trả 409 (không đổi giữa lượt). Trả conv đã cập nhật.
  updateConversation(id: string, patch: { title?: string; provider?: string; model?: string; group_id?: string | null }): Promise<Conversation> {
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
  decideApproval(id: string, decision: 'approved' | 'rejected', reason: string): Promise<ApprovalRow> {
    return request<ApprovalRow>(`/api/approvals/${encodeURIComponent(id)}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decision, reason }),
    });
  },

  // Fetch one approval in any lifecycle status for the Control Tower deep-link.
  getApproval(id: string): Promise<ApprovalRow> {
    return request<ApprovalRow>(`/api/approvals/${encodeURIComponent(id)}`);
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

  // Dashboard counters for the admin overview tab (window=24h|7d|30d — S16 unified).
  // stats tab Tổng quan: approvals/assessments/conversations + delta + spark 24-bucket (T16-2).
  getStats(window: StatsWindow = '24h'): Promise<StatsResponse> {
    return request<StatsResponse>(`/api/stats?window=${encodeURIComponent(window)}`);
  },

  // S20: aggregate shadow ledger + danh sách tín hiệu hiệu chỉnh. Tenant/role do server
  // khóa từ session; FE không bao giờ gửi tenant_id.
  getShadowMatch(): Promise<ShadowMatchStats> {
    return request<ShadowMatchStats>('/api/stats/shadow-match');
  },

  listShadowMismatches(filters: ShadowMismatchFilters = {}): Promise<ShadowMismatchPage> {
    const qs = new URLSearchParams();
    if (filters.from) qs.set('from', filters.from);
    if (filters.to) qs.set('to', filters.to);
    if (filters.lane) qs.set('lane', filters.lane);
    if (filters.limit != null) qs.set('limit', String(filters.limit));
    if (filters.cursor) qs.set('cursor', filters.cursor);
    const query = qs.toString();
    return request<ShadowMismatchPage>(`/api/stats/shadow-match/mismatches${query ? `?${query}` : ''}`);
  },

  // S16 T16-3: cost & vận hành AI (contract). cost_estimated=true → provider ngoài "ước tính".
  getCost(window: StatsWindow = '24h'): Promise<CostResponse> {
    return request<CostResponse>(`/api/stats/cost?window=${encodeURIComponent(window)}`);
  },

  // S16 T16-3: cost-trend long-format (buckets[].series{name:cost}) — FE pivot sang wide cho recharts.
  getCostTrend(window: StatsWindow, bucket: 'hour' | 'day', groupBy: 'model' | 'role'): Promise<CostTrendResponse> {
    const qs = new URLSearchParams({ window, bucket, group_by: groupBy });
    return request<CostTrendResponse>(`/api/stats/cost-trend?${qs.toString()}`);
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

  // D-77: case read-model cho bàn làm việc middle-office. Case có identity riêng, không suy từ
  // conversation. Query chỉ gồm đúng status/source/limit đã khóa tại CONTRACT §11.
  listCases(filters: CaseListFilters = {}): Promise<CaseSummary[]> {
    const qs = new URLSearchParams();
    if (filters.status) qs.set('status', filters.status);
    if (filters.source?.trim()) qs.set('source', filters.source.trim());
    if (filters.limit != null) qs.set('limit', String(filters.limit));
    const query = qs.toString();
    return request<CaseSummary[]>(`/api/cases${query ? `?${query}` : ''}`);
  },

  // D-83: fetch one exact tenant-scoped case for the admin-only Tower deep-link.
  getCase(id: string): Promise<CaseSummary> {
    return request<CaseSummary>(`/api/cases/${encodeURIComponent(id)}`);
  },

  // Submit form + grant consent D-80. Wording/version/hash/tenant/subject đều do server/card
  // sở hữu; client chỉ có quyền gửi literal consent_granted=true.
  submitForm(
    convId: string,
    cardId: string,
    values: Record<string, string>,
    consentGranted: true,
  ): Promise<FormSubmitResult> {
    return request<FormSubmitResult>(`/api/conversations/${convId}/form-submit`, {
      method: 'POST',
      body: JSON.stringify({ card_id: cardId, values, consent_granted: consentGranted }),
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
    }, LONG_REQUEST_TIMEOUT_MS);
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
