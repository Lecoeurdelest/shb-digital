import { act } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { BankDigitalClient, ConversationStreamHandlers } from '../core/types'
import {
  CUSTOMER_ASSISTANT_TAG,
  RM_COPILOT_TAG,
  defineBankDigitalElements,
} from './customElements'
import { mountRmCopilot } from './mount'

function fakeClient(): BankDigitalClient {
  return {
    me: vi.fn(),
    listConversations: vi.fn(),
    createConversation: vi.fn(),
    getConversation: vi.fn().mockResolvedValue({
      conversation: { id: 'conv', title: 'Case', status: 'idle', created_at: '2026-08-24' },
      messages: [],
      tasks: [],
      cards: [],
    }),
    sendMessage: vi.fn(),
    openConversationStream(_id: string, handlers: ConversationStreamHandlers) {
      queueMicrotask(() => handlers.onOpen?.())
      return { close: vi.fn() }
    },
  }
}

describe('element entry', () => {
  it('mounts into Shadow DOM and unmounts idempotently', async () => {
    const target = document.createElement('div')
    document.body.append(target)
    let handle: ReturnType<typeof mountRmCopilot>
    await act(async () => {
      handle = mountRmCopilot(target, { client: fakeClient(), conversationId: 'conv' })
    })
    expect(target.shadowRoot).not.toBeNull()
    expect(target.shadowRoot?.querySelector('[data-bank-digital-embed="rm"]')).not.toBeNull()
    expect(document.querySelector('[data-bank-digital-embed="rm"]')).toBeNull()
    act(() => {
      handle.unmount()
      handle.unmount()
    })
    expect(target.shadowRoot?.childElementCount).toBe(0)
  })

  it('defines both explicit elements idempotently and exposes no token attribute', () => {
    defineBankDigitalElements()
    defineBankDigitalElements()
    expect(customElements.get(CUSTOMER_ASSISTANT_TAG)).toBeDefined()
    expect(customElements.get(RM_COPILOT_TAG)).toBeDefined()
    const element = document.createElement(RM_COPILOT_TAG)
    document.body.append(element)
    expect(element.shadowRoot?.textContent).toContain('conversation-id')
    const constructor = customElements.get(RM_COPILOT_TAG) as CustomElementConstructor & {
      observedAttributes: string[]
    }
    expect(constructor.observedAttributes).toEqual([
      'api-base-url',
      'conversation-id',
      'heading',
      'style-nonce',
    ])
  })

  it('emits only non-bubbling event metadata from the declarative element', async () => {
    defineBankDigitalElements()
    const sensitiveEvent = {
      type: 'card',
      conversation_id: 'conv',
      seq: 1,
      ts: '2026-08-24T00:00:00Z',
      data: { card: { title: 'CIC secret' } },
    }
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      if (String(input).endsWith('/sse')) {
        return new Response(`data: ${JSON.stringify(sensitiveEvent)}\n\n`, {
          headers: { 'Content-Type': 'text/event-stream' },
        })
      }
      return new Response(JSON.stringify({
        conversation: { id: 'conv', title: 'Case', status: 'idle', created_at: '2026-08-24' },
        messages: [],
        tasks: [],
        cards: [],
      }), { headers: { 'Content-Type': 'application/json' } })
    })
    vi.stubGlobal('fetch', fetchMock)
    const element = document.createElement(RM_COPILOT_TAG)
    const documentSpy = vi.fn()
    document.addEventListener('bank-digital:event', documentSpy)
    const received = new Promise<Event>((resolve) => {
      element.addEventListener('bank-digital:event', resolve, { once: true })
    })
    document.body.append(element)
    expect(element.shadowRoot?.textContent).toContain('conversation-id')
    element.setAttribute('conversation-id', 'conv')
    const event = await received as CustomEvent

    expect(event.detail).toEqual({ type: 'card' })
    expect(event.bubbles).toBe(false)
    expect(event.composed).toBe(false)
    expect(documentSpy).not.toHaveBeenCalled()
    expect(element.shadowRoot?.textContent).not.toContain('Thiếu attribute')
    element.remove()
    document.removeEventListener('bank-digital:event', documentSpy)
    vi.unstubAllGlobals()
  })
})
