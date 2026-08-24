import type { ChatTurnAssembler } from '../core/chatAssembler'
import type {
  Card,
  Conversation,
  ConversationFullState,
  Message,
  OrchTask,
  SSEEnvelope,
  StreamState,
} from '../core/types'

export interface StreamingMessage {
  turnId: string
  text: string
}

export interface BankConversationState {
  connection: StreamState
  loading: boolean
  sending: boolean
  conversation: Conversation | null
  messages: Message[]
  tasks: OrchTask[]
  cards: Card[]
  streaming: StreamingMessage | null
  error: unknown | null
}

export function emptyConversationState(): BankConversationState {
  return {
    connection: 'connecting',
    loading: true,
    sending: false,
    conversation: null,
    messages: [],
    tasks: [],
    cards: [],
    streaming: null,
    error: null,
  }
}

export function applyFullState(
  current: BankConversationState,
  full: ConversationFullState,
): BankConversationState {
  return {
    ...current,
    loading: false,
    conversation: full.conversation,
    messages: full.messages,
    tasks: full.tasks,
    cards: full.cards ?? [],
    streaming: null,
    error: null,
  }
}

function upsert<T extends { id: string }>(rows: T[], value: T): T[] {
  const index = rows.findIndex((row) => row.id === value.id)
  if (index < 0) return [...rows, value]
  const next = [...rows]
  next[index] = value
  return next
}

function upsertCard(rows: Card[], card: Card): Card[] {
  const withoutOlderEquivalent = rows.filter(
    (row) =>
      row.id === card.id ||
      row.task_id !== card.task_id ||
      row.type !== card.type,
  )
  return upsert(withoutOlderEquivalent, card)
}

export function applyEnvelope(
  current: BankConversationState,
  event: SSEEnvelope,
  assembler: ChatTurnAssembler,
): BankConversationState {
  if (event.type === 'ping') return current
  if (event.type === 'conversation.status') {
    const data = event.data as { status?: Conversation['status'] }
    if (!data.status || !current.conversation) return current
    return { ...current, conversation: { ...current.conversation, status: data.status } }
  }
  if (event.type === 'task.created' || event.type === 'task.status') {
    const task = (event.data as { task?: OrchTask }).task
    return task ? { ...current, tasks: upsert(current.tasks, task) } : current
  }
  if (event.type === 'card') {
    const card = (event.data as { card?: Card }).card
    return card ? { ...current, cards: upsertCard(current.cards, card) } : current
  }
  if (event.type === 'approval.decided') {
    const phieu = (event.data as { phieu?: Record<string, unknown> }).phieu
    if (!phieu || typeof phieu.id !== 'string') return current
    return {
      ...current,
      cards: current.cards.map((card) =>
        card.type === 'approval' && card.approval_id === phieu.id
          ? { ...card, status: phieu.status, decided_by: phieu.decided_by, reason: phieu.reason }
          : card,
      ),
    }
  }
  if (event.type !== 'chat.delta') return current
  const data = event.data as {
    turn_id?: string
    chunk?: string
    done?: boolean
    full_text?: string
  }
  if (!data.turn_id || typeof data.chunk !== 'string' || typeof data.done !== 'boolean') return current
  const assembly = assembler.push(event.seq, {
    turn_id: data.turn_id,
    chunk: data.chunk,
    done: data.done,
    ...(data.full_text === undefined ? {} : { full_text: data.full_text }),
  })
  if (!assembly) return current
  const previous = current.streaming?.turnId === assembly.turnId ? current.streaming.text : ''
  const accumulated = previous + assembly.text
  if (!assembly.done) {
    return { ...current, streaming: { turnId: assembly.turnId, text: accumulated } }
  }
  // done.full_text là bản đã persist trong DB, kể cả chuỗi rỗng. Không được phục hồi draft
  // đang stream bằng toán tử `||` vì như vậy UI có thể hiện nội dung lõi đã loại bỏ.
  const finalText = (assembly.fullText ?? accumulated).trim()
  const messages = finalText
    ? upsert(current.messages, {
        id: `local_${assembly.turnId}`,
        conv_id: event.conversation_id,
        ts: event.ts,
        sender: 'assistant',
        content: finalText,
        meta: null,
      })
    : current.messages
  return { ...current, messages, streaming: null }
}
