export { BankConversationProvider } from './react/ConversationProvider'
export { useBankConversation } from './react/ConversationContext'
export {
  Cards,
  Composer,
  ErrorNotice,
  Frame,
  Header,
  Messages,
  Status,
} from './react/components'
export { CustomerAssistant, RmCopilot } from './react/variants'
export { bankDigitalStyles } from './react/styles'
export type {
  BankConversationActions,
  BankConversationContextValue,
  BankConversationMeta,
} from './react/ConversationContext'
export type { BankConversationProviderProps } from './react/ConversationProvider'
export type { BankConversationState, StreamingMessage } from './react/conversationState'
export type {
  CardsProps,
  ComposerProps,
  FrameProps,
  HeaderProps,
  MessagesProps,
} from './react/components'
export type { CustomerAssistantProps, RmCopilotProps } from './react/variants'

import { BankConversationProvider } from './react/ConversationProvider'
import { Cards, Composer, ErrorNotice, Frame, Header, Messages, Status } from './react/components'

export const BankConversation = {
  Provider: BankConversationProvider,
  Frame,
  Header,
  Status,
  Messages,
  Cards,
  Composer,
  ErrorNotice,
}
