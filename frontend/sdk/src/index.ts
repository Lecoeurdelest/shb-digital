export { createBankDigitalClient } from './core/client'
export { BankDigitalApiError, isApiErrorPayload } from './core/error'
export { ChatTurnAssembler } from './core/chatAssembler'
export { SseDataParser } from './core/sseParser'
export type {
  ApiErrorPayload,
  BankDigitalClient,
  BankDigitalClientOptions,
  Card,
  ChatAssembly,
  ChatDeltaData,
  Conversation,
  ConversationFullState,
  ConversationStatus,
  ConversationStream,
  ConversationStreamHandlers,
  CreateConversationInput,
  CurrentUser,
  HeaderProvider,
  Message,
  MessageSender,
  OrchTask,
  SSEEnvelope,
  SSEEventType,
  StreamState,
  StreamStateChange,
  TaskStatus,
  UserRole,
} from './publicTypes'
