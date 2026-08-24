import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';

afterEach(() => vi.unstubAllGlobals());

describe('apiClient.listCases', () => {
  it('gửi đúng query contract và đọc raw array resource', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiClient.listCases({ status: 'needs_specialist', source: ' los ', limit: 25 })).resolves.toEqual([]);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/cases?status=needs_specialist&source=los&limit=25',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('GET exact case encodes only the path id and reads a raw CaseSummary', async () => {
    const row = { id: '0198a4e1-7b6c-7abc-0012-1234567890ab' };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => row,
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiClient.getCase(row.id)).resolves.toEqual(row);
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/cases/${row.id}`,
      expect.objectContaining({ credentials: 'include' }),
    );
  });
});
