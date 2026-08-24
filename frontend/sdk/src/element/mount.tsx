import { createRoot, type Root } from 'react-dom/client'
import type { BankDigitalClient, SSEEnvelope } from '../core/types'
import { CustomerAssistant, RmCopilot } from '../react/variants'

export interface EmbedMountOptions {
  client: BankDigitalClient
  conversationId: string
  heading?: string
  onEvent?: (event: SSEEnvelope) => void
  styleNonce?: string
}

export interface EmbedMountHandle {
  unmount(): void
}

const roots = new WeakMap<HTMLElement, Root>()

function shadowContainer(target: HTMLElement): ShadowRoot {
  return target.shadowRoot ?? target.attachShadow({ mode: 'open' })
}

function mount(
  target: HTMLElement,
  options: EmbedMountOptions,
  surface: 'customer' | 'rm',
): EmbedMountHandle {
  roots.get(target)?.unmount()
  const container = shadowContainer(target)
  // Custom element có thể đã render lỗi cấu hình tĩnh trước khi host gắn conversation-id.
  // React root mới phải sở hữu toàn bộ Shadow DOM, không để text lỗi cũ nằm cạnh widget.
  container.replaceChildren()
  const root = createRoot(container)
  roots.set(target, root)
  const props = {
    client: options.client,
    conversationId: options.conversationId,
    ...(options.heading === undefined ? {} : { heading: options.heading }),
    ...(options.onEvent === undefined ? {} : { onEvent: options.onEvent }),
    ...(options.styleNonce === undefined ? {} : { styleNonce: options.styleNonce }),
  }
  root.render(surface === 'rm' ? <RmCopilot {...props} /> : <CustomerAssistant {...props} />)
  let mounted = true
  return {
    unmount() {
      if (!mounted) return
      mounted = false
      root.unmount()
      if (roots.get(target) === root) roots.delete(target)
    },
  }
}

export function mountCustomerAssistant(
  target: HTMLElement,
  options: EmbedMountOptions,
): EmbedMountHandle {
  return mount(target, options, 'customer')
}

export function mountRmCopilot(target: HTMLElement, options: EmbedMountOptions): EmbedMountHandle {
  return mount(target, options, 'rm')
}
