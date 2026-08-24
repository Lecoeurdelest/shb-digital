// types.ts — shape khớp CONTRACT chung `docs/CONTRACT.md` (D-30, architect chốt S1) =
// bản thi hành gọn của SPEC §5/§9/§10/§11. BE define, FE ăn theo (1 codepath render).
// Đổi shape → sửa CONTRACT.md TRƯỚC. KHÔNG tự chế field ngoài CONTRACT.

// ── Auth (CONTRACT §1 · D-56 persona) ──
// 'customer' = khách hàng (cửa khách, chat + agent tự duyệt khoản nhỏ); 'admin' = ngân hàng
// (duyệt khoản lớn, Control Tower); 'user' = nhân viên thường (giữ backward, không admin).
export type UserRole = 'customer' | 'user' | 'admin';

export interface AuthUser {
  username: string;
  role: UserRole;
  tenant_id?: string; // D-79 — server-owned; FE chỉ hiển thị/giữ context, không tự gửi tenant.
  owner_id?: string | null; // D-56 — mã khách của account (customer); admin/user = null. Thiếu (server cũ) → null.
}

// POST /api/auth/login trả {token, user} + set cookie httponly shb_token.
export interface LoginResult {
  token: string;
  user: AuthUser;
}

export type ConversationStatus = 'running' | 'waiting_approval' | 'done' | 'failed' | 'idle';

export interface Conversation {
  id: string;
  tenant_id?: string;
  group_id?: string | null;
  user_id?: string;
  title: string;
  status: ConversationStatus;
  sdk_session_id?: string | null;
  created_at: string;
  provider?: string; // D-45b — provider ca chạy (null = server-default)
  model?: string; // model string trong provider đó
}

export interface ConversationGroup {
  id: string;
  name: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export type MessageSender = 'user' | 'assistant' | 'system';

export interface Message {
  id: string;
  conv_id: string;
  ts: string;
  sender: MessageSender;
  content: string;
  meta?: Record<string, unknown> | null;
}

export type TaskStatus = 'queued' | 'running' | 'done' | 'failed';

export interface OrchTask {
  id: string;
  conv_id: string;
  role: string; // credit | legal | products | ops (§3 role động — không hardcode enum cứng)
  title: string;
  status: TaskStatus;
  input?: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  queued_at?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  cost?: Record<string, unknown> | null; // jsonb {cost_usd} (T16-1) — cost "ước tính" per task
  // S16 T16-1: metrics per task (ResultMessage.usage). NULLABLE — turn/task CŨ = null → không render
  // (backward mọi ca cũ). Field-name KHỚP TokenBreakdownBar (tokenSegments) → tái dùng không adapter.
  input_tokens?: number | null;
  output_tokens?: number | null;
  cache_read_tokens?: number | null;
  cache_create_tokens?: number | null;
  duration_ms?: number | null;
  model?: string | null; // model THẬT đã chạy task (null = turn cũ)
}

// S16 T16-1: metrics MAIN per turn (messages assistant meta.metrics, role='main'). Cùng shape token.
export interface TurnMetrics {
  input_tokens?: number | null;
  output_tokens?: number | null;
  cache_read_tokens?: number | null;
  cache_create_tokens?: number | null;
  duration_ms?: number | null;
  cost_usd?: number | null;
  model?: string | null;
}

// ── Card (canvas — CONTRACT §3 · canvas-present §3). N3 vỏ-mù: agent bơm items TỰ DO, vỏ chỉ
// khoá {type, title, items}. FE render DEFENSIVE — field thiếu → bỏ qua, type lạ → default branch.
// items = unknown[] (KHÔNG ép shape cứng); từng component tự đọc field an toàn qua helper.
export interface Card {
  id: string;
  conv_id: string;
  task_id: string | null;
  type: string; // metric | checklist | options | timeline | case_file | document | approval | (lạ)
  ts: string;
  title?: string;
  items?: unknown[];
  sources?: string[];
  // field tuỳ type (agent bơm): flags?, recommended?, total_days?, action?... — đọc qua record[key]
  [key: string]: unknown;
}

export interface CardEventData {
  card: Card;
}

// approval.decided SSE (T3-2): {phieu:{id, action, status, decided_by, reason}}. FE ghép card+phieu
// (card KHÔNG xoá §6): tìm card approval có approval_id === phieu.id → cập nhật status/decided_by/reason.
export interface Phieu {
  id: string;
  action?: string;
  status: 'pending' | 'approved' | 'rejected' | 'used';
  decided_by?: string;
  reason?: string;
}
export interface ApprovalDecidedData {
  phieu: Phieu;
}

export interface ConversationFullState {
  conversation: Conversation;
  messages: Message[];
  tasks: OrchTask[];
  cards?: Card[]; // S2: canvas reload (CONTRACT §3). optional — S1 backend có thể chưa trả.
}

// ── SSE envelope (streaming-sse.md §2) ──

export type SSEEventType =
  | 'conversation.status'
  | 'task.created'
  | 'task.status'
  | 'chat.delta'
  | 'card'
  | 'toolcall'
  | 'thinking'
  | 'approval.pending'
  | 'approval.decided'
  | 'ping'; // heartbeat backend (15s) — FE bỏ qua khi parse, chỉ dùng reset watchdog (D-54)

// ── Trace (F1 — D-43): thinking + toolcall hiện trong chat (khối collapsible). ──
// toolcall (T4-1): {id, task_id, tool, summary, cost} — id khớp GET /api/audit row.id (upsert dedup).
// thinking (T4-2 BE): {task_id|null, text} — trace tạm, KHÔNG persist DB (chỉ live).
export interface ToolcallData {
  id: string;
  task_id: string | null;
  tool: string;
  summary?: string;
  cost?: Record<string, unknown> | null;
}
export interface ThinkingData {
  task_id: string | null;
  text: string;
}

// item gộp trong TraceBlock (render 1 dòng). kind phân biệt thinking vs tool.
export type TraceItem =
  | { kind: 'thinking'; id: string; task_id: string | null; text: string }
  | { kind: 'tool'; id: string; task_id: string | null; tool: string; summary?: string };

// audit row (GET /api/audit — reload trace toolcall history). Cùng shape cột tool_calls.
export interface AuditRow {
  id: string;
  task_id: string | null;
  conv_id: string;
  ts: string;
  actor: string;
  tool: string;
  input?: Record<string, unknown> | null;
  output?: unknown;
  cost?: Record<string, unknown> | null;
}

// ── Control Tower (S4 — T4-6) ──
// approval queue row (GET /api/approvals?status=pending — admin, toàn hệ).
// display (DF-B-01 T14): BE enrich mỗi row cho render người-đọc (tên khách/tiền/loan/lane) — vắng → fallback.
export interface ApprovalDisplay {
  customer_name?: string | null;
  owner_id?: string | null;
  loan_id?: string | null;
  amount_vnd?: number | null;
  lane?: string | null;
}
export interface ApprovalRow {
  id: string;
  conv_id: string;
  task_id: string | null;
  action: string;
  payload?: Record<string, unknown> | null;
  payload_hash?: string;
  status: 'pending' | 'approved' | 'rejected' | 'used' | 'exec_failed';
  decided_by?: string | null;
  decided_at?: string | null;
  reason?: string | null;
  used_at?: string | null;
  receipt?: Record<string, unknown> | null;
  exec_attempts?: number;
  display?: ApprovalDisplay | null;
  [key: string]: unknown;
}

// model dropdown (GET /api/models — D-45b).
export interface Provider {
  name: string;
  kind: string;
  base_url: string | null;
  models: string[];
  default: boolean;
  has_key: boolean;
  note?: string;
}
export interface ModelsResponse {
  providers: Provider[];
  default: string;
}

export interface AgentPromptConfig {
  key: string;
  scope: string;
  description: string | null;
  variables: string[];
  active: { version: number; content: string; activated_by: string; activated_at: string } | null;
}
export interface AgentConfigResponse {
  environment: string;
  providers: Provider[];
  prompts: AgentPromptConfig[];
}

// compare 2-cột (POST /api/compare {question} — deliverable #5). Shape backend mới — đọc defensive.
export interface CompareResult {
  single?: CompareSide | null;
  multi?: CompareSide | null;
  [key: string]: unknown;
}
export interface CompareSide {
  text?: string;
  duration_s?: number;
  cost?: Record<string, unknown> | null;
  tool_calls?: number;
  cards?: number;
  conv_id?: string | null;
  [key: string]: unknown;
}

export interface SSEEnvelope<T = unknown> {
  type: SSEEventType;
  conversation_id: string;
  seq: number | null;
  ts: string;
  data: T;
}

export interface ChatDeltaData {
  turn_id: string;
  chunk: string;
  done: boolean;
  full_text?: string;
}

export interface ConversationStatusData {
  status: ConversationStatus;
}

export interface TaskEventData {
  task: OrchTask;
}

// 4-field error envelope (SPEC §5 / §11) — CHỈ error dùng shape này, success = resource trần.
export interface ApiError {
  code: string;
  message: string;
  hint: string;
  retryable: boolean;
}

// ── Form intake khách mới (D-57 T9-3) ──
// Card type='form' data: fields SERVER định nghĩa (FE render đúng, KHÔNG hardcode).
export interface FormField {
  name: string;
  label: string;
  type: 'text' | 'number';
  required: boolean;
}
export interface ConsentSnapshot {
  required: true;
  purpose: 'pre_pilot_shadow_preassessment';
  wording_version: string;
  wording_checksum: string;
  content_markdown: string;
}
// POST /form-submit {card_id, values, consent_granted:true} → 200 {owner_id, customer_created}.
export interface FormSubmitResult {
  owner_id: string;
  customer_created: boolean;
}

// ── Bell thông báo khách (D-57 T9-3 · GET /api/notifications) ──
export interface NotificationItem {
  type: 'approval_decided' | 'disbursed';
  title: string;
  ts: string;
  conv_id: string;
}

// ── Case workbench (CONTRACT §11 · D-77) ──
// Case có identity nghiệp vụ riêng; tuyệt đối không suy từ conversation title/conv_id.
export type CaseStatus =
  | 'received'
  | 'missing_information'
  | 'ready_for_preassessment'
  | 'preassessment_in_progress'
  | 'needs_specialist'
  | 'ready_for_handover'
  | 'cancelled';

export interface CaseSummary {
  id: string;
  source_system: string;
  external_case_id: string;
  internal_application_id: string | null;
  party_reference: string | null;
  product_code: string | null;
  loan_amount_vnd: number | null;
  case_status: CaseStatus;
  next_action: string;
  document_count: number;
  missing_fields: string[];
  source_version: number | null;
  data_as_of: string | null;
  synced_at: string;
  conversation_id: string | null;
  assessment: {
    lane: 'green' | 'yellow' | 'red' | null;
    created_at: string | null;
  };
}

export interface CaseListFilters {
  status?: CaseStatus;
  source?: string;
  limit?: number;
}

// ── Stats + assessments (S13 T13-1 · GET /api/stats, /api/assessments — admin) ──
// window thống nhất S16 (T16-3): 24h | 7d | 30d — thay 'today'|'7d' cũ (segmented control có 24h).
export type StatsWindow = '24h' | '7d' | '30d';

export interface StatsResponse {
  window: string;
  approvals: { approved: number; rejected: number; pending: number; auto: number };
  assessments: { green: number; yellow: number; red: number };
  conversations: { total: number; active: number };
  delta: { approvals_total: number; assessments_total: number };
  // S16 T16-3: mỗi KPI +spark 24-bucket chuẩn hoá mọi window (BE T16-2 sẽ trả). OPTIONAL —
  // thiếu → KpiCard render như cũ (backward). Shape provisional (grouped map — DECISIONS, BE khớp).
  sparks?: Partial<Record<string, number[]>>;
}

// ── Shadow match (S20 ·7b/7d) ──
export type ShadowLane = 'green' | 'yellow' | 'red' | null;
export type ShadowRecommendation = 'auto-eligible' | 'human-review' | 'reject-recommended';

export interface ShadowLaneBucket {
  lane: ShadowLane;
  total: number;
  comparable: number;
  matched: number;
  rate: number;
}

export interface ShadowDayBucket {
  date: string;
  total: number;
  comparable: number;
  matched: number;
  rate: number;
}

export interface ShadowMatchStats {
  total: number;
  comparable: number;
  matched: number;
  rate: number;
  by_lane: ShadowLaneBucket[];
  by_day: ShadowDayBucket[];
}

export interface ShadowMismatch {
  approval_id: string;
  conv_id: string;
  system_lane: ShadowLane;
  system_recommendation: ShadowRecommendation;
  human_decision: 'approved' | 'rejected';
  human_reason: string | null;
  decided_at: string;
}

export interface ShadowMismatchPage {
  items: ShadowMismatch[];
  next_cursor: string | null;
}

export interface ShadowMismatchFilters {
  from?: string;
  to?: string;
  lane?: Exclude<ShadowLane, null>;
  limit?: number;
  cursor?: string;
}

// ── S16 T16-3: cost & vận hành AI (contract architect chốt — BE T16-2 khớp NGUYÊN VĂN) ──
// GET /api/stats/cost?window=24h|7d|30d
export interface CostBreakdown {
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_create_tokens: number;
}
export interface CostByModel { model: string; cost_usd: number; turns: number; total_tokens: number }
export interface CostByRole { role: string; cost_usd: number; turns: number }
export interface CostAnomaly {
  conv_id: string;
  title: string;
  cost_usd: number;
  mean: number;
  stddev: number;
  z_score: number;
}
export interface CostResponse {
  window: string;
  total_cost_usd: number;
  cost_estimated: boolean; // provider ngoài: cost SDK không tin → label "ước tính"
  breakdown: CostBreakdown;
  by_model: CostByModel[];
  by_role: CostByRole[];
  anomalies: CostAnomaly[];
  delta: { total_cost_pct: number };
}

// GET /api/stats/cost-trend?window=&bucket=hour|day&group_by=model|role → long-format buckets.
export interface CostTrendBucket { ts: string; series: Record<string, number> }
export interface CostTrendResponse { buckets: CostTrendBucket[] }
export type AssessmentLevel = 'pass' | 'green' | 'yellow' | 'red' | string; // criteria level (defensive: chấp string lạ)
export interface AssessmentCriterion {
  key: string;
  level: AssessmentLevel;
  detail?: string;
}
export interface Assessment {
  id: string | number;
  owner_id: string;
  loan_type?: string;
  loan_amount_vnd?: number;
  lane: 'green' | 'yellow' | 'red' | string; // defensive: lane lạ → default branch
  criteria: AssessmentCriterion[];
  basis?: string;
  created_at?: string;
}
