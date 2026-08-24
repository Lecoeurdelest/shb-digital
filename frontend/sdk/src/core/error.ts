import type { ApiErrorPayload } from './types'

export class BankDigitalApiError extends Error {
  readonly status: number
  readonly body: ApiErrorPayload | null

  constructor(status: number, body: ApiErrorPayload | null, fallbackMessage?: string) {
    super(body?.message ?? fallbackMessage ?? `HTTP ${status}`)
    this.name = 'BankDigitalApiError'
    this.status = status
    this.body = body
  }
}

export function isApiErrorPayload(value: unknown): value is ApiErrorPayload {
  if (!value || typeof value !== 'object') return false
  const row = value as Record<string, unknown>
  return (
    typeof row.code === 'string' &&
    typeof row.message === 'string' &&
    typeof row.hint === 'string' &&
    typeof row.retryable === 'boolean'
  )
}

export async function errorFromResponse(response: Response): Promise<BankDigitalApiError> {
  let body: ApiErrorPayload | null = null
  try {
    const candidate: unknown = await response.json()
    if (isApiErrorPayload(candidate)) body = candidate
  } catch {
    // Upstream sai contract: vẫn giữ HTTP status, không giả một envelope hợp lệ.
  }
  return new BankDigitalApiError(response.status, body)
}
