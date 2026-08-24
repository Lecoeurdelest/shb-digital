import { describe, expect, it } from 'vitest'
import { SseDataParser } from './sseParser'

describe('SseDataParser', () => {
  it('parses comments, CRLF and frames split across chunks', () => {
    const parser = new SseDataParser()
    expect(parser.push(': connected\r\n\r\ndata: {"type":"pi')).toEqual([])
    expect(parser.push('ng"}\r\n\r\n')).toEqual(['{"type":"ping"}'])
  })

  it('joins multiline data and ignores fields other than data', () => {
    const parser = new SseDataParser()
    expect(parser.push('event: ignored\ndata: first\ndata: second\nid: 4\n\n')).toEqual([
      'first\nsecond',
    ])
  })

  it('flushes a final frame without a trailing boundary', () => {
    const parser = new SseDataParser()
    expect(parser.push('data: final')).toEqual([])
    expect(parser.finish()).toEqual(['final'])
  })
})
