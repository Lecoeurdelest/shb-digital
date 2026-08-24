import { createBankDigitalClient } from '../core/client'
import type { SSEEnvelope } from '../core/types'
import {
  mountCustomerAssistant,
  mountRmCopilot,
  type EmbedMountHandle,
} from './mount'

export const CUSTOMER_ASSISTANT_TAG = 'bank-digital-customer-assistant'
export const RM_COPILOT_TAG = 'bank-digital-rm-copilot'

interface ElementConstructorOptions {
  surface: 'customer' | 'rm'
}

function makeElementClass({ surface }: ElementConstructorOptions): CustomElementConstructor {
  return class BankDigitalEmbedElement extends HTMLElement {
    static observedAttributes = ['api-base-url', 'conversation-id', 'heading', 'style-nonce']
    private mounted: EmbedMountHandle | null = null

    connectedCallback(): void {
      this.renderEmbed()
    }

    disconnectedCallback(): void {
      this.mounted?.unmount()
      this.mounted = null
    }

    attributeChangedCallback(): void {
      if (this.isConnected) this.renderEmbed()
    }

    private renderEmbed(): void {
      this.mounted?.unmount()
      this.mounted = null
      const conversationId = this.getAttribute('conversation-id')?.trim()
      if (!conversationId) {
        const shadow = this.shadowRoot ?? this.attachShadow({ mode: 'open' })
        shadow.textContent = 'Thiếu attribute conversation-id.'
        return
      }
      const client = createBankDigitalClient({
        apiBaseUrl: this.getAttribute('api-base-url') ?? '',
      })
      const options = {
        client,
        conversationId,
        heading: this.getAttribute('heading') ?? undefined,
        styleNonce: this.getAttribute('style-nonce') ?? undefined,
        onEvent: (event: SSEEnvelope) => {
          // Web Component mặc định chỉ phát loại sự kiện. Full envelope có thể chứa CIC/card;
          // host cần dữ liệu thô phải dùng mount API + callback tường minh trong code tin cậy.
          this.dispatchEvent(
            new CustomEvent('bank-digital:event', {
              detail: { type: event.type },
              bubbles: false,
              composed: false,
            }),
          )
        },
      }
      this.mounted = surface === 'rm'
        ? mountRmCopilot(this, options)
        : mountCustomerAssistant(this, options)
    }
  }
}

export function defineBankDigitalElements(registry: CustomElementRegistry = customElements): void {
  if (!registry.get(CUSTOMER_ASSISTANT_TAG)) {
    registry.define(CUSTOMER_ASSISTANT_TAG, makeElementClass({ surface: 'customer' }))
  }
  if (!registry.get(RM_COPILOT_TAG)) {
    registry.define(RM_COPILOT_TAG, makeElementClass({ surface: 'rm' }))
  }
}
