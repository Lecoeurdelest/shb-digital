import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiRequestError, apiClient } from './client';

describe('apiClient request timeout', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('rejects a hung REST request so UI loading state can settle', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn((_path: string, init?: RequestInit) => new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
      })),
    );

    const assertion = expect(apiClient.listConversations()).rejects.toMatchObject({
      status: 0,
      body: {
        code: 'request_timeout',
        message: 'Backend phản hồi quá lâu.',
        hint: 'Thử lại sau khi kiểm tra server dev/API (/api/conversations).',
        retryable: true,
      },
    } satisfies Partial<ApiRequestError>);
    await vi.advanceTimersByTimeAsync(20_000);

    await assertion;
  });
});
