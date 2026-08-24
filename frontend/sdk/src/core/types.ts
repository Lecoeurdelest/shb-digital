export interface ApiErrorPayload {
  code: string
  message: string
  hint: string
  retryable: boolean
}

export type UserRole = 'customer' | 'user' | 'admin'

export interface CurrentUser {
  username: string
  role: UserRole
  owner_id: string | null
}

export type ConversationStatus = 'running' | 'waiting_approval' | 'done' | 'failed' | 'idle'

export interface Conversation {
  id: string
  user_id?: string
  title: string
  status: ConversationStatus
  sdk_session_id?: string | null
  created_at: string
  provider?: string
  model?: string
}

export type MessageSender = 'user' | 'assistant' | 'system'

export interface Message {
  id: string
  conv_id: string
  ts: string
  sender: MessageSender
  content: string
  meta?: Record<string, unknown> | null
}

export type TaskStatus = 'queued' | 'running' | 'done' | 'failed'

export interface OrchTask {
  id: string
  conv_id: string
  role: string
  title: string
  status: TaskStatus
  input?: Record<string, unknown>
  result?: Record<string, unknown> | null
  queued_at?: string | null
  started_at?: string | null
  ended_at?: string | null
  cost?: Record<string, unknown> | null
  input_tokens?: number | null
  output_tokens?: number | null
  cache_read_tokens?: number | null
  cache_create_tokens?: number | null
  duration_ms?: number | null
  model?: string | null
}

export interface Card {
  id: string
  conv_id: string
  task_id: string | null
  type: string
  ts: string
  title?: string
  items?: unknown[]
  sources?: string[]
  [key: string]: unknown
}

export interface ConversationFullState {
  conversation: Conversation
  messages: Message[]
  tasks: OrchTask[]
  cards: Card[]
}

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
  | 'ping'

export interface SSEEnvelope<T = unknown> {
  type: SSEEventType
  conversation_id: string
  seq: number | null
  ts: string
  data: T
}

export interface ChatDeltaData {
  turn_id: string
  chunk: string
  done: boolean
  full_text?: string
}

export type StreamState = 'connecting' | 'open' | 'reconnecting' | 'closed'

export interface StreamStateChange {
  state: StreamState
  retryInMs?: number
}

export interface ConversationStreamHandlers {
  onOpen?: () => void
  onEvent: (event: SSEEnvelope) => void
  onError?: (error: unknown) => void
  onStateChange?: (change: StreamStateChange) => void
}

export interface ConversationStream {
  close(): void
}

export interface CreateConversationInput {
  title: string
  provider?: string
  model?: string
}

export type HeaderProvider =
  | Record<string, string>
  | (() => Record<string, string> | Promise<Record<string, string>>)

export interface BankDigitalClientOptions {
  apiBaseUrl?: string
  credentials?: RequestCredentials
  fetch?: typeof globalThis.fetch
  getAccessToken?: () => string | null | Promise<string | null>
  headers?: HeaderProvider
}

export interface BankDigitalClient {
  me(): Promise<CurrentUser>
  listConversations(): Promise<Conversation[]>
  createConversation(input: CreateConversationInput): Promise<Conversation>
  getConversation(id: string): Promise<ConversationFullState>
  sendMessage(id: string, content: string): Promise<{ queued: boolean }>
  openConversationStream(id: string, handlers: ConversationStreamHandlers): ConversationStream
}
