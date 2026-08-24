import { BankDigitalApiError, errorFromResponse } from './error'
import { SseDataParser } from './sseParser'
import type { ConversationStream, ConversationStreamHandlers, SSEEnvelope } from './types'

interface FetchSseOptions {
  open: (signal: AbortSignal) => Promise<Response>
  handlers: ConversationStreamHandlers
  watchdogMs?: number
  initialRetryMs?: number
  maxRetryMs?: number
}

function shouldRetry(error: unknown): boolean {
  if (!(error instanceof BankDigitalApiError)) return true
  return error.body?.retryable === true || error.status === 429 || error.status >= 500
}

export class FetchSseConversationStream implements ConversationStream {
  private readonly options: Required<Omit<FetchSseOptions, 'open' | 'handlers'>> &
    Pick<FetchSseOptions, 'open' | 'handlers'>
  private controller: AbortController | null = null
  private retryTimer: ReturnType<typeof setTimeout> | null = null
  private watchdogTimer: ReturnType<typeof setTimeout> | null = null
  private stopped = false
  private retryCount = 0
  private watchdogExpired = false

  constructor(options: FetchSseOptions) {
    this.options = {
      ...options,
      watchdogMs: options.watchdogMs ?? 25_000,
      initialRetryMs: options.initialRetryMs ?? 1_000,
      maxRetryMs: options.maxRetryMs ?? 30_000,
    }
    this.emitState('connecting')
    void this.connect()
  }

  close(): void {
    if (this.stopped) return
    this.stopped = true
    this.controller?.abort()
    this.controller = null
    if (this.retryTimer) clearTimeout(this.retryTimer)
    if (this.watchdogTimer) clearTimeout(this.watchdogTimer)
    this.retryTimer = null
    this.watchdogTimer = null
    this.emitState('closed')
  }

  private async connect(): Promise<void> {
    if (this.stopped) return
    this.controller = new AbortController()
    this.watchdogExpired = false
    try {
      const response = await this.options.open(this.controller.signal)
      if (this.stopped) {
        await this.cancelBody(response.body)
        return
      }
      if (!response.ok) throw await errorFromResponse(response)
      if (!response.body) throw new Error('SSE response không có body stream')
      this.emitState('open')
      if (this.stopped) {
        await this.cancelBody(response.body)
        return
      }
      this.safeCall(this.options.handlers.onOpen)
      if (this.stopped) {
        await this.cancelBody(response.body)
        return
      }
      this.armWatchdog()
      await this.readBody(response.body)
      if (!this.stopped) throw new Error('SSE stream kết thúc ngoài dự kiến')
    } catch (error) {
      this.clearWatchdog()
      if (this.stopped) return
      if (!this.watchdogExpired && error instanceof DOMException && error.name === 'AbortError') return
      this.safeCall(this.options.handlers.onError, error)
      if (!shouldRetry(error)) {
        this.stopped = true
        this.emitState('closed')
        return
      }
      this.scheduleReconnect()
    }
  }

  private async readBody(body: ReadableStream<Uint8Array>): Promise<void> {
    const reader = body.getReader()
    const decoder = new TextDecoder()
    const parser = new SseDataParser()
    try {
      while (!this.stopped) {
        const result = await reader.read()
        if (result.done) break
        if (this.stopped) break
        const payloads = parser.push(decoder.decode(result.value, { stream: true }))
        for (const payload of payloads) {
          if (this.stopped) break
          this.handlePayload(payload)
        }
      }
      if (!this.stopped) {
        for (const payload of parser.push(decoder.decode())) {
          if (this.stopped) break
          this.handlePayload(payload)
        }
      }
      if (!this.stopped) {
        for (const payload of parser.finish()) {
          if (this.stopped) break
          this.handlePayload(payload)
        }
      }
    } finally {
      reader.releaseLock()
    }
  }

  private handlePayload(payload: string): void {
    if (this.stopped) return
    this.armWatchdog()
    this.retryCount = 0
    let event: SSEEnvelope
    try {
      event = JSON.parse(payload) as SSEEnvelope
    } catch {
      return
    }
    if (!event || typeof event !== 'object' || typeof event.type !== 'string') return
    this.safeCall(this.options.handlers.onEvent, event)
  }

  private async cancelBody(body: ReadableStream<Uint8Array> | null): Promise<void> {
    if (!body) return
    try {
      await body.cancel()
    } catch {
      // close() là ranh giới lifecycle; lỗi dọn body không được phát callback mới cho host.
    }
  }

  private scheduleReconnect(): void {
    const delay = Math.min(
      this.options.initialRetryMs * 2 ** this.retryCount,
      this.options.maxRetryMs,
    )
    this.retryCount += 1
    this.emitState('reconnecting', delay)
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null
      void this.connect()
    }, delay)
  }

  private armWatchdog(): void {
    this.clearWatchdog()
    this.watchdogTimer = setTimeout(() => {
      this.watchdogExpired = true
      this.controller?.abort()
    }, this.options.watchdogMs)
  }

  private clearWatchdog(): void {
    if (this.watchdogTimer) clearTimeout(this.watchdogTimer)
    this.watchdogTimer = null
  }

  private emitState(state: 'connecting' | 'open' | 'reconnecting' | 'closed', retryInMs?: number): void {
    this.safeCall(this.options.handlers.onStateChange, { state, ...(retryInMs === undefined ? {} : { retryInMs }) })
  }

  private safeCall<T>(callback: ((value: T) => void) | undefined, value: T): void
  private safeCall(callback: (() => void) | undefined): void
  private safeCall<T>(callback: ((value?: T) => void) | undefined, value?: T): void {
    try {
      callback?.(value)
    } catch (error) {
      if (callback !== this.options.handlers.onError) {
        try {
          this.options.handlers.onError?.(error)
        } catch {
          // Lỗi callback của host không được làm chết transport hoặc tạo vòng lỗi.
        }
      }
    }
  }
}
