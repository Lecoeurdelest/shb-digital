import { act, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type {
  BankDigitalClient,
  ConversationFullState,
  ConversationStreamHandlers,
} from '../core/types'
import {
  useBankConversation,
  type BankConversationContextValue,
} from './ConversationContext'
import { BankConversationProvider } from './ConversationProvider'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((done, fail) => {
    resolve = done
    reject = fail
  })
  return { promise, resolve, reject }
}

function fullState(id: string, message = `message-${id}`): ConversationFullState {
  return {
    conversation: {
      id,
      title: `Case ${id}`,
      status: 'idle',
      created_at: '2026-08-24T00:00:00Z',
    },
    messages: [
      {
        id: `message-${id}`,
        conv_id: id,
        ts: '2026-08-24T00:00:00Z',
        sender: 'assistant',
        content: message,
      },
    ],
    tasks: [],
    cards: [],
  }
}

interface ControlledClient extends BankDigitalClient {
  handlers: ConversationStreamHandlers | null
  close: ReturnType<typeof vi.fn>
}

function controlledClient(
  getConversation: BankDigitalClient['getConversation'],
  sendMessage: BankDigitalClient['sendMessage'] = vi.fn().mockResolvedValue({ queued: true }),
): ControlledClient {
  const close = vi.fn()
  const client: ControlledClient = {
    handlers: null,
    close,
    me: vi.fn(),
    listConversations: vi.fn(),
    createConversation: vi.fn(),
    getConversation,
    sendMessage,
    openConversationStream(_id, handlers) {
      client.handlers = handlers
      queueMicrotask(() => handlers.onOpen?.())
      return { close }
    },
  }
  return client
}

function Probe({ capture }: { capture: { current: BankConversationContextValue | null } }) {
  const value = useBankConversation()
  capture.current = value
  const error = value.state.error
  return (
    <div>
      <span data-testid="conversation-id">{value.state.conversation?.id ?? 'empty'}</span>
      <span data-testid="messages">{value.state.messages.map((row) => row.content).join('|')}</span>
      <span data-testid="cards">{value.state.cards.map((row) => row.title).join('|')}</span>
      <span data-testid="sending">{String(value.state.sending)}</span>
      <span data-testid="error">{error instanceof Error ? error.message : ''}</span>
    </div>
  )
}

function Harness({
  client,
  conversationId,
  capture,
}: {
  client: BankDigitalClient
  conversationId: string
  capture: { current: BankConversationContextValue | null }
}) {
  return (
    <BankConversationProvider client={client} conversationId={conversationId}>
      <Probe capture={capture} />
    </BankConversationProvider>
  )
}

describe('BankConversationProvider lifecycle', () => {
  it('cannot apply a completed refresh from the previous conversation scope', async () => {
    const requestA = deferred<ConversationFullState>()
    const requestB = deferred<ConversationFullState>()
    const clientA = controlledClient(vi.fn(() => requestA.promise))
    const clientB = controlledClient(vi.fn(() => requestB.promise))
    const capture = { current: null as BankConversationContextValue | null }
    const view = render(<Harness client={clientA} conversationId="A" capture={capture} />)
    await waitFor(() => expect(clientA.getConversation).toHaveBeenCalledOnce())

    view.rerender(<Harness client={clientB} conversationId="B" capture={capture} />)
    await waitFor(() => expect(clientB.getConversation).toHaveBeenCalledOnce())
    await act(async () => {
      requestA.resolve(fullState('A'))
      await requestA.promise
    })
    expect(screen.queryByText('message-A')).not.toBeInTheDocument()
    expect(screen.getByTestId('conversation-id')).toHaveTextContent('empty')

    await act(async () => {
      requestB.resolve(fullState('B'))
      await requestB.promise
    })
    expect(await screen.findByText('message-B')).toBeInTheDocument()
    expect(screen.getByTestId('conversation-id')).toHaveTextContent('B')
  })

  it('does not surface an old sendMessage failure after switching conversations', async () => {
    const sendA = deferred<{ queued: boolean }>()
    const clientA = controlledClient(
      vi.fn().mockResolvedValue(fullState('A')),
      vi.fn(() => sendA.promise),
    )
    const clientB = controlledClient(vi.fn().mockResolvedValue(fullState('B')))
    const capture = { current: null as BankConversationContextValue | null }
    const view = render(<Harness client={clientA} conversationId="A" capture={capture} />)
    expect(await screen.findByText('message-A')).toBeInTheDocument()

    let oldSend!: Promise<void>
    act(() => {
      oldSend = capture.current!.actions.sendMessage('old request').catch(() => undefined)
    })
    expect(screen.getByTestId('sending')).toHaveTextContent('true')

    view.rerender(<Harness client={clientB} conversationId="B" capture={capture} />)
    expect(await screen.findByText('message-B')).toBeInTheDocument()
    await act(async () => {
      sendA.reject(new Error('failure from A'))
      await oldSend
    })

    expect(screen.getByTestId('conversation-id')).toHaveTextContent('B')
    expect(screen.getByTestId('sending')).toHaveTextContent('false')
    expect(screen.getByTestId('error')).toBeEmptyDOMElement()
  })

  it('ignores ping for refresh invalidation and replays business events over the snapshot', async () => {
    const request = deferred<ConversationFullState>()
    const getConversation = vi.fn(() => request.promise)
    const client = controlledClient(getConversation)
    const capture = { current: null as BankConversationContextValue | null }
    render(<Harness client={client} conversationId="A" capture={capture} />)
    await waitFor(() => expect(getConversation).toHaveBeenCalledOnce())

    act(() => {
      client.handlers?.onEvent({
        type: 'ping',
        conversation_id: 'A',
        seq: null,
        ts: '2026-08-24T00:00:01Z',
        data: {},
      })
      client.handlers?.onEvent({
        type: 'card',
        conversation_id: 'A',
        seq: null,
        ts: '2026-08-24T00:00:02Z',
        data: {
          card: {
            id: 'live-card',
            conv_id: 'A',
            task_id: 'credit',
            type: 'memo',
            ts: '2026-08-24T00:00:02Z',
            title: 'Live memo',
          },
        },
      })
    })
    await act(async () => {
      request.resolve(fullState('A'))
      await request.promise
    })

    expect(getConversation).toHaveBeenCalledOnce()
    expect(screen.getByTestId('cards')).toHaveTextContent('Live memo')
  })

  it('coalesces concurrent refresh requests into one active and one queued pass', async () => {
    const requests: Array<ReturnType<typeof deferred<ConversationFullState>>> = []
    const getConversation = vi.fn(() => {
      const request = deferred<ConversationFullState>()
      requests.push(request)
      return request.promise
    })
    const client = controlledClient(getConversation)
    const capture = { current: null as BankConversationContextValue | null }
    render(<Harness client={client} conversationId="A" capture={capture} />)
    await waitFor(() => expect(requests).toHaveLength(1))
    await act(async () => {
      requests[0].resolve(fullState('A'))
      await requests[0].promise
    })

    let first!: Promise<void>
    act(() => {
      first = capture.current!.actions.refresh()
      void capture.current!.actions.refresh()
      void capture.current!.actions.refresh()
    })
    await waitFor(() => expect(requests).toHaveLength(2))
    await act(async () => {
      requests[1].resolve(fullState('A', 'pass-one'))
      await requests[1].promise
    })
    await waitFor(() => expect(requests).toHaveLength(3))
    await act(async () => {
      requests[2].resolve(fullState('A', 'pass-two'))
      await first
    })

    expect(getConversation).toHaveBeenCalledTimes(3)
    expect(screen.getByTestId('messages')).toHaveTextContent('pass-two')
  })
})
