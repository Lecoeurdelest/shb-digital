import type { ChatDeltaData } from './types'

interface TurnBuffer {
  last: number
  pending: Map<number, ChatDeltaData>
  doneSeq?: number
  doneFullText?: string
}

export interface ChatAssembly {
  turnId: string
  text: string
  done: boolean
  fullText?: string
}

export class ChatTurnAssembler {
  private readonly turns = new Map<string, TurnBuffer>()

  push(seq: number | null, data: ChatDeltaData): ChatAssembly | null {
    if (seq === null) return null
    const turn = this.turns.get(data.turn_id) ?? { last: 0, pending: new Map<number, ChatDeltaData>() }
    this.turns.set(data.turn_id, turn)
    if (seq <= turn.last || turn.pending.has(seq)) return null

    turn.pending.set(seq, data)
    if (data.done) {
      turn.doneSeq = seq
      turn.doneFullText = data.full_text ?? ''
    }

    let text = ''
    while (turn.pending.has(turn.last + 1)) {
      const nextSeq = turn.last + 1
      const next = turn.pending.get(nextSeq)!
      turn.pending.delete(nextSeq)
      turn.last = nextSeq
      text += next.chunk
    }

    const isDone = turn.doneSeq !== undefined && turn.last >= turn.doneSeq
    if (isDone) {
      const fullText = turn.doneFullText ?? ''
      this.turns.delete(data.turn_id)
      return { turnId: data.turn_id, text, done: true, fullText }
    }
    return text ? { turnId: data.turn_id, text, done: false } : null
  }

  clear(): void {
    this.turns.clear()
  }
}
