import { describe, expect, it } from 'vitest'
import { ChatTurnAssembler } from './chatAssembler'

describe('ChatTurnAssembler', () => {
  it('keeps done.full_text when the done sequence arrives before an earlier chunk', () => {
    const assembler = new ChatTurnAssembler()
    expect(
      assembler.push(2, {
        turn_id: 'turn-1',
        chunk: 'lo',
        done: true,
        full_text: 'hello canonical',
      }),
    ).toBeNull()

    expect(
      assembler.push(1, {
        turn_id: 'turn-1',
        chunk: 'hel',
        done: false,
      }),
    ).toEqual({
      turnId: 'turn-1',
      text: 'hello',
      done: true,
      fullText: 'hello canonical',
    })
  })

  it('drops duplicate and stale sequences', () => {
    const assembler = new ChatTurnAssembler()
    expect(assembler.push(1, { turn_id: 't', chunk: 'a', done: false })?.text).toBe('a')
    expect(assembler.push(1, { turn_id: 't', chunk: 'duplicate', done: false })).toBeNull()
    expect(assembler.push(null, { turn_id: 't', chunk: 'x', done: false })).toBeNull()
  })
})
