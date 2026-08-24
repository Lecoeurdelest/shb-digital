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

describe('apiClient S20 contracts', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('builds mismatch query without tenant_id and keeps the opaque cursor encoded', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ items: [], next_cursor: null }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await apiClient.listShadowMismatches({
      from: '2026-08-23T00:00:00+07:00',
      to: '2026-08-24T00:00:00+07:00',
      lane: 'green',
      limit: 25,
      cursor: 'opaque+/=',
    });

    const path = String(fetchMock.mock.calls[0][0]);
    expect(path).toBe('/api/stats/shadow-match/mismatches?from=2026-08-23T00%3A00%3A00%2B07%3A00&to=2026-08-24T00%3A00%3A00%2B07%3A00&lane=green&limit=25&cursor=opaque%2B%2F%3D');
    expect(path).not.toContain('tenant');
  });

  it('form submit sends only card, values and consent_granted=true', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ owner_id: 'C9001', customer_created: true }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await apiClient.submitForm('conv-1', 'card-1', { full_name: 'Nguyễn A' }, true);

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      card_id: 'card-1',
      values: { full_name: 'Nguyễn A' },
      consent_granted: true,
    });
  });
});
