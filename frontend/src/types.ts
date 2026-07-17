// types.ts — shape khớp CONTRACT chung `docs/CONTRACT.md` (D-30, architect chốt S1) =
// bản thi hành gọn của SPEC §5/§9/§10/§11. BE define, FE ăn theo (1 codepath render).
// Đổi shape → sửa CONTRACT.md TRƯỚC. KHÔNG tự chế field ngoài CONTRACT.

export type ConversationStatus = 'running' | 'waiting_approval' | 'done' | 'failed' | 'idle';

export interface Conversation {
  id: string;
  user_id?: string;
  title: string;
  status: ConversationStatus;
  sdk_session_id?: string | null;
  created_at: string;
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
  cost?: Record<string, unknown> | null;
}

export interface ConversationFullState {
  conversation: Conversation;
  messages: Message[];
  tasks: OrchTask[];
}

// ── SSE envelope (streaming-sse.md §2) ──

export type SSEEventType =
  | 'conversation.status'
  | 'task.created'
  | 'task.status'
  | 'chat.delta'
  | 'card'
  | 'toolcall'
  | 'approval.pending'
  | 'approval.decided';

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
