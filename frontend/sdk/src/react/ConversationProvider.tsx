import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { ChatTurnAssembler } from '../core/chatAssembler'
import type {
  BankDigitalClient,
  ConversationStream,
  SSEEnvelope,
} from '../core/types'
import {
  applyEnvelope,
  applyFullState,
  emptyConversationState,
  type BankConversationState,
} from './conversationState'
import {
  ConversationContext,
  type BankConversationContextValue,
} from './ConversationContext'

export interface BankConversationProviderProps {
  client: BankDigitalClient
  conversationId: string
  children: ReactNode
  onEvent?: (event: SSEEnvelope) => void
}

interface ConversationScope {
  active: boolean
  activation: number
  bufferedEvents: SSEEnvelope[] | null
  client: BankDigitalClient
  conversationId: string
  refreshPromise: Promise<void> | null
  refreshQueued: boolean
}

interface ScopedConversationState {
  scope: ConversationScope
  value: BankConversationState
}

export function BankConversationProvider({
  client,
  conversationId,
  children,
  onEvent,
}: BankConversationProviderProps) {
  // Mỗi cặp client/conversation có scope riêng. Promise/callback của scope cũ không thể trở
  // thành "current" lần nữa chỉ vì counter của scope mới tình cờ có cùng giá trị (ABA).
  const scope = useMemo<ConversationScope>(
    () => ({
      active: false,
      activation: 0,
      bufferedEvents: null,
      client,
      conversationId,
      refreshPromise: null,
      refreshQueued: false,
    }),
    [client, conversationId],
  )
  const [scopedState, setScopedState] = useState<ScopedConversationState>(() => ({
    scope,
    value: emptyConversationState(),
  }))
  const state = scopedState.scope === scope ? scopedState.value : emptyConversationState()
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  const updateState = useCallback(
    (
      activation: number,
      update: (current: BankConversationState) => BankConversationState,
    ) => {
      setScopedState((current) => {
        if (!scope.active || scope.activation !== activation) return current
        const value = current.scope === scope ? current.value : emptyConversationState()
        return { scope, value: update(value) }
      })
    },
    [scope],
  )

  const refresh = useCallback(async () => {
    const activation = scope.activation
    const isCurrent = () => scope.active && scope.activation === activation
    if (!isCurrent()) return
    if (scope.refreshPromise) {
      // Nhiều lý do refresh trong cùng một request chỉ tạo thêm tối đa một lượt kế tiếp.
      scope.refreshQueued = true
      return scope.refreshPromise
    }

    const run = async () => {
      let failed = false
      do {
        scope.refreshQueued = false
        const bufferedEvents: SSEEnvelope[] = []
        scope.bufferedEvents = bufferedEvents
        updateState(activation, (current) => ({
          ...current,
          loading: current.conversation === null,
          error: null,
        }))
        try {
          const full = await client.getConversation(conversationId)
          if (!isCurrent()) return
          if (scope.bufferedEvents === bufferedEvents) scope.bufferedEvents = null
          // Event đã tới trong lúc GET chạy được replay trên snapshot. Nhờ vậy không cần vòng
          // refetch theo version (heartbeat/event dày không thể làm full-state đói mãi).
          updateState(activation, (current) => {
            let next = applyFullState(current, full)
            const replayAssembler = new ChatTurnAssembler()
            for (const event of bufferedEvents) {
              next = applyEnvelope(next, event, replayAssembler)
            }
            return next
          })
        } catch (error) {
          if (scope.bufferedEvents === bufferedEvents) scope.bufferedEvents = null
          if (isCurrent()) {
            updateState(activation, (current) => ({ ...current, loading: false, error }))
          }
          failed = true
        }
      } while (isCurrent() && scope.refreshQueued && !failed)
    }

    let promise: Promise<void>
    promise = run().finally(() => {
      if (scope.refreshPromise === promise) {
        scope.refreshPromise = null
      }
    })
    scope.refreshPromise = promise
    return promise
  }, [client, conversationId, scope, updateState])

  useEffect(() => {
    const activation = scope.activation + 1
    scope.activation = activation
    scope.active = true
    scope.bufferedEvents = null
    scope.refreshQueued = false
    setScopedState({ scope, value: emptyConversationState() })
    const assembler = new ChatTurnAssembler()
    let stream: ConversationStream | null = null
    stream = client.openConversationStream(conversationId, {
      onOpen: () => {
        if (!scope.active || scope.activation !== activation) return
        assembler.clear()
        void refresh()
      },
      onEvent: (event) => {
        if (!scope.active || scope.activation !== activation) return
        if (event.type !== 'ping') scope.bufferedEvents?.push(event)
        updateState(activation, (current) => applyEnvelope(current, event, assembler))
        onEventRef.current?.(event)
        if (event.type === 'conversation.status') {
          const status = (event.data as { status?: string }).status
          if (status === 'done' || status === 'failed') void refresh()
        }
      },
      onError: (error) => {
        if (scope.active && scope.activation === activation) {
          updateState(activation, (current) => ({ ...current, error }))
        }
      },
      onStateChange: ({ state: connection }) => {
        if (scope.active && scope.activation === activation) {
          updateState(activation, (current) => ({ ...current, connection }))
        }
      },
    })
    return () => {
      if (scope.activation === activation) {
        scope.active = false
        scope.activation += 1
        scope.bufferedEvents = null
        scope.refreshPromise = null
        scope.refreshQueued = false
      }
      stream?.close()
    }
  }, [client, conversationId, refresh, scope, updateState])

  const sendMessage = useCallback(
    async (content: string) => {
      const activation = scope.activation
      const isCurrent = () => scope.active && scope.activation === activation
      if (!isCurrent()) throw new Error('Conversation scope không còn hoạt động')
      updateState(activation, (current) => ({ ...current, sending: true, error: null }))
      try {
        await client.sendMessage(conversationId, content)
      } catch (error) {
        if (isCurrent()) updateState(activation, (current) => ({ ...current, error }))
        throw error
      } finally {
        if (isCurrent()) updateState(activation, (current) => ({ ...current, sending: false }))
      }
    },
    [client, conversationId, scope, updateState],
  )

  const clearError = useCallback(() => {
    const activation = scope.activation
    if (scope.active) updateState(activation, (current) => ({ ...current, error: null }))
  }, [scope, updateState])

  const value = useMemo<BankConversationContextValue>(
    () => ({
      state,
      actions: { refresh, sendMessage, clearError },
      meta: { client, conversationId },
    }),
    [state, refresh, sendMessage, clearError, client, conversationId],
  )

  return <ConversationContext value={value}>{children}</ConversationContext>
}
