import { createContext, use } from 'react'
import type { BankDigitalClient } from '../core/types'
import type { BankConversationState } from './conversationState'

export interface BankConversationActions {
  refresh(): Promise<void>
  sendMessage(content: string): Promise<void>
  clearError(): void
}

export interface BankConversationMeta {
  client: BankDigitalClient
  conversationId: string
}

export interface BankConversationContextValue {
  state: BankConversationState
  actions: BankConversationActions
  meta: BankConversationMeta
}

export const ConversationContext = createContext<BankConversationContextValue | null>(null)

export function useBankConversation(): BankConversationContextValue {
  const context = use(ConversationContext)
  if (!context) throw new Error('useBankConversation phải nằm trong BankConversation.Provider')
  return context
}
