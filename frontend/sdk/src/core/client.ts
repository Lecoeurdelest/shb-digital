import { BankDigitalApiError, errorFromResponse } from './error'
import { FetchSseConversationStream } from './fetchSse'
import type {
  BankDigitalClient,
  BankDigitalClientOptions,
  Conversation,
  ConversationFullState,
  ConversationStream,
  ConversationStreamHandlers,
  CreateConversationInput,
  CurrentUser,
  HeaderProvider,
} from './types'

function normalizeApiBaseUrl(value: string | undefined): string {
  return (value ?? '').trim().replace(/\/+$/, '')
}

function endpoint(base: string, path: string): string {
  return `${base}${path}`
}

async function resolveHeaders(provider: HeaderProvider | undefined): Promise<Record<string, string>> {
  if (!provider) return {}
  return typeof provider === 'function' ? provider() : provider
}

function parseJson<T>(text: string): T {
  return JSON.parse(text) as T
}

function parseCurrentUser(payload: unknown): CurrentUser {
  if (!payload || typeof payload !== 'object') {
    throw new TypeError('Response /api/me không đúng contract')
  }
  const row = payload as Record<string, unknown>
  const nested = row.user && typeof row.user === 'object'
    ? row.user as Record<string, unknown>
    : {}
  const username = row.username ?? nested.username
  const role = row.role ?? nested.role
  const ownerId = row.owner_id ?? nested.owner_id ?? null
  if (
    typeof username !== 'string' ||
    username.trim() === '' ||
    (role !== 'customer' && role !== 'user' && role !== 'admin') ||
    (ownerId !== null && typeof ownerId !== 'string')
  ) {
    // Identity là ranh authz của host; payload 200 méo không được biến thành RM hợp lệ giả.
    throw new TypeError('Response /api/me không đúng contract')
  }
  return { username, role, owner_id: ownerId }
}

class DefaultBankDigitalClient implements BankDigitalClient {
  private readonly apiBaseUrl: string
  private readonly credentials: RequestCredentials
  private readonly fetchImpl: typeof globalThis.fetch
  private readonly getAccessToken?: BankDigitalClientOptions['getAccessToken']
  private readonly headerProvider?: HeaderProvider

  constructor(options: BankDigitalClientOptions = {}) {
    this.apiBaseUrl = normalizeApiBaseUrl(options.apiBaseUrl)
    this.credentials = options.credentials ?? 'include'
    const globalFetch = globalThis.fetch
    if (!options.fetch && typeof globalFetch !== 'function') {
      throw new Error('Fetch API không tồn tại; hãy inject options.fetch')
    }
    this.fetchImpl = options.fetch ?? globalFetch.bind(globalThis)
    this.getAccessToken = options.getAccessToken
    this.headerProvider = options.headers
  }

  async me(): Promise<CurrentUser> {
    return parseCurrentUser(await this.request<unknown>('/api/me'))
  }

  listConversations(): Promise<Conversation[]> {
    return this.request<Conversation[]>('/api/conversations')
  }

  createConversation(input: CreateConversationInput): Promise<Conversation> {
    return this.request<Conversation>('/api/conversations', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }

  async getConversation(id: string): Promise<ConversationFullState> {
    const state = await this.request<ConversationFullState>(
      `/api/conversations/${encodeURIComponent(id)}`,
    )
    return { ...state, cards: state.cards ?? [] }
  }

  async sendMessage(id: string, content: string): Promise<{ queued: boolean }> {
    const clean = content.trim()
    if (!clean) throw new TypeError('Nội dung chat không được rỗng')
    const payload = await this.request<{ queued?: boolean }>(
      `/api/conversations/${encodeURIComponent(id)}/chat`,
      { method: 'POST', body: JSON.stringify({ content: clean }) },
    )
    return { queued: payload?.queued ?? true }
  }

  openConversationStream(id: string, handlers: ConversationStreamHandlers): ConversationStream {
    const path = `/api/conversations/${encodeURIComponent(id)}/sse`
    return new FetchSseConversationStream({
      handlers,
      open: (signal) =>
        this.fetchRaw(path, {
          method: 'GET',
          signal,
          headers: { Accept: 'text/event-stream' },
        }),
    })
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await this.fetchRaw(path, init)
    if (!response.ok) throw await errorFromResponse(response)
    if (response.status === 204) return undefined as T
    const text = await response.text()
    return text ? parseJson<T>(text) : (undefined as T)
  }

  private async fetchRaw(path: string, init: RequestInit): Promise<Response> {
    const headers = new Headers(await resolveHeaders(this.headerProvider))
    new Headers(init.headers).forEach((value, key) => headers.set(key, value))
    if (init.body !== undefined && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    const token = await this.getAccessToken?.()
    if (token) headers.set('Authorization', `Bearer ${token}`)
    try {
      return await this.fetchImpl(endpoint(this.apiBaseUrl, path), {
        ...init,
        credentials: this.credentials,
        headers,
      })
    } catch (error) {
      if (error instanceof BankDigitalApiError) throw error
      throw error
    }
  }
}

export function createBankDigitalClient(options: BankDigitalClientOptions = {}): BankDigitalClient {
  return new DefaultBankDigitalClient(options)
}
