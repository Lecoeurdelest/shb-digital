import { describe, expect, it } from 'vitest'
import { ChatTurnAssembler } from '../core/chatAssembler'
import type { ConversationFullState, SSEEnvelope } from '../core/types'
import { applyEnvelope, applyFullState, emptyConversationState } from './conversationState'

const FULL: ConversationFullState = {
  conversation: {
    id: 'conv',
    title: 'Case',
    status: 'idle',
    created_at: '2026-08-24T00:00:00Z',
  },
  messages: [],
  tasks: [],
  cards: [],
}

function delta(seq: number, data: Record<string, unknown>): SSEEnvelope {
  return {
    type: 'chat.delta',
    conversation_id: 'conv',
    seq,
    ts: '2026-08-24T00:00:00Z',
    data,
  }
}

describe('conversation state', () => {
  it('uses canonical full_text for an out-of-order completed turn', () => {
    const assembler = new ChatTurnAssembler()
    let state = applyFullState(emptyConversationState(), FULL)
    state = applyEnvelope(
      state,
      delta(2, { turn_id: 't', chunk: 'lo', done: true, full_text: 'canonical' }),
      assembler,
    )
    expect(state.messages).toEqual([])
    state = applyEnvelope(
      state,
      delta(1, { turn_id: 't', chunk: 'hel', done: false }),
      assembler,
    )
    expect(state.messages.at(-1)?.content).toBe('canonical')
    expect(state.streaming).toBeNull()
  })

  it('does not resurrect streamed draft when canonical full_text is empty', () => {
    const assembler = new ChatTurnAssembler()
    let state = applyFullState(emptyConversationState(), FULL)
    state = applyEnvelope(
      state,
      delta(1, { turn_id: 't-empty', chunk: 'unsafe draft', done: false }),
      assembler,
    )
    expect(state.streaming?.text).toBe('unsafe draft')

    state = applyEnvelope(
      state,
      delta(2, { turn_id: 't-empty', chunk: '', done: true, full_text: '' }),
      assembler,
    )
    expect(state.streaming).toBeNull()
    expect(state.messages).toEqual([])
  })

  it('replaces an older card with the same task and type', () => {
    const assembler = new ChatTurnAssembler()
    let state = applyFullState(emptyConversationState(), {
      ...FULL,
      cards: [{ id: 'old', conv_id: 'conv', task_id: 'task', type: 'memo', ts: '1' }],
    })
    state = applyEnvelope(
      state,
      {
        type: 'card',
        conversation_id: 'conv',
        seq: null,
        ts: '2',
        data: { card: { id: 'new', conv_id: 'conv', task_id: 'task', type: 'memo', ts: '2' } },
      },
      assembler,
    )
    expect(state.cards.map((card) => card.id)).toEqual(['new'])
  })
})
