import { describe, expect, it, vi } from 'vitest'
import { createBankDigitalClient } from './client'
import { BankDigitalApiError } from './error'
import type { ConversationStream } from './types'

const JSON_HEADERS = { 'Content-Type': 'application/json' }

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

describe('createBankDigitalClient', () => {
  it('uses configurable base URL, dynamic Bearer auth and credentials', async () => {
    const tokens = ['token-one', 'token-two']
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ username: 'rm', role: 'user', owner_id: null }), {
          headers: JSON_HEADERS,
        }),
      )
      .mockResolvedValueOnce(new Response('[]', { headers: JSON_HEADERS }))
    const client = createBankDigitalClient({
      apiBaseUrl: 'https://agent.bank.example/',
      fetch: fetchMock,
      credentials: 'omit',
      getAccessToken: () => tokens.shift() ?? null,
      headers: { 'X-Bank-Channel': 'los' },
    })

    await client.me()
    await client.listConversations()

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'https://agent.bank.example/api/me',
      expect.objectContaining({ credentials: 'omit' }),
    )
    const firstHeaders = fetchMock.mock.calls[0][1]?.headers as Headers
    const secondHeaders = fetchMock.mock.calls[1][1]?.headers as Headers
    expect(firstHeaders.get('Authorization')).toBe('Bearer token-one')
    expect(secondHeaders.get('Authorization')).toBe('Bearer token-two')
    expect(firstHeaders.get('X-Bank-Channel')).toBe('los')
  })

  it('throws the canonical API error without inventing a body', async () => {
    const body = {
      code: 'forbidden',
      message: 'Không có quyền.',
      hint: 'Đăng nhập đúng vai.',
      retryable: false,
    }
    const client = createBankDigitalClient({
      fetch: vi.fn<typeof fetch>().mockResolvedValue(
        new Response(JSON.stringify(body), { status: 403, headers: JSON_HEADERS }),
      ),
    })
    await expect(client.listConversations()).rejects.toMatchObject({ status: 403, body })

    const malformed = createBankDigitalClient({
      fetch: vi.fn<typeof fetch>().mockResolvedValue(new Response('proxy html', { status: 502 })),
    })
    try {
      await malformed.listConversations()
      throw new Error('expected rejection')
    } catch (error) {
      expect(error).toBeInstanceOf(BankDigitalApiError)
      expect((error as BankDigitalApiError).body).toBeNull()
    }
  })

  it('fails closed when /api/me returns a malformed 200 identity', async () => {
    const client = createBankDigitalClient({
      fetch: vi.fn<typeof fetch>().mockResolvedValue(
        new Response('{}', { headers: JSON_HEADERS }),
      ),
    })

    await expect(client.me()).rejects.toThrow('Response /api/me không đúng contract')
  })

  it('trims chat content and normalizes a 202 empty acknowledgement', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response('{}', { status: 202, headers: JSON_HEADERS }),
    )
    const client = createBankDigitalClient({ fetch: fetchMock })
    await expect(client.sendMessage('conv/1', '  hello  ')).resolves.toEqual({ queued: true })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/conversations/conv%2F1/chat')
    expect(fetchMock.mock.calls[0][1]?.body).toBe('{"content":"hello"}')
    await expect(client.sendMessage('conv', '   ')).rejects.toBeInstanceOf(TypeError)
  })

  it('streams SSE over fetch with Authorization and can be closed by the host', async () => {
    const event = {
      type: 'ping',
      conversation_id: 'conv',
      seq: null,
      ts: '2026-08-24T00:00:00Z',
      data: {},
    }
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(`: connected\n\ndata: ${JSON.stringify(event)}\n\n`, {
        headers: { 'Content-Type': 'text/event-stream' },
      }),
    )
    const client = createBankDigitalClient({
      fetch: fetchMock,
      getAccessToken: () => 'stream-token',
    })
    let stream: ConversationStream
    const received = new Promise<void>((resolve) => {
      stream = client.openConversationStream('conv', {
        onEvent: (value) => {
          expect(value).toEqual(event)
          stream.close()
          resolve()
        },
      })
    })
    await received
    const headers = fetchMock.mock.calls[0][1]?.headers as Headers
    expect(headers.get('Accept')).toBe('text/event-stream')
    expect(headers.get('Authorization')).toBe('Bearer stream-token')
  })

  it('does not deliver buffered events after close()', async () => {
    const first = {
      type: 'ping',
      conversation_id: 'conv',
      seq: null,
      ts: '2026-08-24T00:00:00Z',
      data: { index: 1 },
    }
    const second = { ...first, data: { index: 2 } }
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        `data: ${JSON.stringify(first)}\n\ndata: ${JSON.stringify(second)}\n\n`,
        { headers: { 'Content-Type': 'text/event-stream' } },
      ),
    )
    const client = createBankDigitalClient({ fetch: fetchMock })
    const received: number[] = []
    let stream: ConversationStream
    const closed = new Promise<void>((resolve) => {
      stream = client.openConversationStream('conv', {
        onEvent: (event) => {
          received.push((event.data as { index: number }).index)
          stream.close()
          queueMicrotask(resolve)
        },
      })
    })

    await closed
    expect(received).toEqual([1])
  })

  it('stays closed when an injected fetch resolves after close()', async () => {
    const response = deferred<Response>()
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(() => response.promise)
    const client = createBankDigitalClient({ fetch: fetchMock })
    const states: string[] = []
    const onOpen = vi.fn()
    const stream = client.openConversationStream('conv', {
      onEvent: vi.fn(),
      onOpen,
      onStateChange: ({ state }) => states.push(state),
    })

    stream.close()
    response.resolve(
      new Response('data: {"type":"ping"}\n\n', {
        headers: { 'Content-Type': 'text/event-stream' },
      }),
    )
    await response.promise
    await new Promise<void>((resolve) => queueMicrotask(resolve))

    expect(onOpen).not.toHaveBeenCalled()
    expect(states).toEqual(['connecting', 'closed'])
  })
})
