import type { BankDigitalClient, SSEEnvelope } from '../core/types'
import { BankConversationProvider } from './ConversationProvider'
import { Cards, Composer, ErrorNotice, Frame, Header, Messages } from './components'

interface VariantProps {
  client: BankDigitalClient
  conversationId: string
  heading?: string
  onEvent?: (event: SSEEnvelope) => void
  styleNonce?: string
}

export type CustomerAssistantProps = VariantProps

export function CustomerAssistant({
  client,
  conversationId,
  heading = 'Hỗ trợ hoàn thiện hồ sơ',
  onEvent,
  styleNonce,
}: CustomerAssistantProps) {
  return (
    <BankConversationProvider client={client} conversationId={conversationId} onEvent={onEvent}>
      <Frame variant="customer" styleNonce={styleNonce}>
        <Header heading={heading} />
        <Messages />
        <ErrorNotice />
        <Composer />
      </Frame>
    </BankConversationProvider>
  )
}

export type RmCopilotProps = VariantProps

export function RmCopilot({
  client,
  conversationId,
  heading = 'Hỗ trợ sơ thẩm',
  onEvent,
  styleNonce,
}: RmCopilotProps) {
  return (
    <BankConversationProvider client={client} conversationId={conversationId} onEvent={onEvent}>
      <Frame variant="rm" styleNonce={styleNonce}>
        <Header heading={heading} />
        <div className="bd-disclaimer" role="note">
          Kết quả sơ thẩm không phải phê duyệt. Quyết định cuối cùng thuộc người có thẩm quyền.
        </div>
        <Messages />
        <Cards />
        <ErrorNotice />
        <Composer />
      </Frame>
    </BankConversationProvider>
  )
}
