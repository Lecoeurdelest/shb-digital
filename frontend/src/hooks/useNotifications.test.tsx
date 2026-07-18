// useNotifications.test.tsx — bell khách (D-57 T9-3): poll, unseen theo last-seen, 404 ẩn, enabled gate.
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { conversationApi } from '../api';
import { ApiRequestError } from '../api/client';
import type { NotificationItem } from '../types';

const NOTIFS: NotificationItem[] = [
  { type: 'approval_decided', title: 'Duyệt L001', ts: '2026-07-18T10:00:00', conv_id: 'c1' },
  { type: 'disbursed', title: 'Giải ngân', ts: '2026-07-18T11:00:00', conv_id: 'c1' },
];

beforeEach(() => {
  vi.restoreAllMocks();
  try { localStorage.clear(); } catch { /* ignore */ }
});
afterEach(() => vi.useRealTimers());

import { useNotifications } from './useNotifications';

describe('useNotifications', () => {
  it('enabled=false → không poll, items rỗng', () => {
    const spy = vi.spyOn(conversationApi, 'getNotifications').mockResolvedValue([]);
    const { result } = renderHook(() => useNotifications(false));
    expect(result.current.items).toEqual([]);
    expect(spy).not.toHaveBeenCalled();
  });

  it('enabled → poll → items + unseen = số item mới (chưa từng xem)', async () => {
    vi.spyOn(conversationApi, 'getNotifications').mockResolvedValue(NOTIFS);
    const { result } = renderHook(() => useNotifications(true));
    await waitFor(() => expect(result.current.items).toHaveLength(2));
    expect(result.current.unseen).toBe(2); // last-seen rỗng → cả 2 mới
    expect(result.current.available).toBe(true);
  });

  it('markSeen → unseen về 0 (lưu last-seen)', async () => {
    vi.spyOn(conversationApi, 'getNotifications').mockResolvedValue(NOTIFS);
    const { result } = renderHook(() => useNotifications(true));
    await waitFor(() => expect(result.current.unseen).toBe(2));
    act(() => result.current.markSeen());
    await waitFor(() => expect(result.current.unseen).toBe(0));
  });

  it('404 (endpoint T9-2 chưa lên) → available=false (bell ẩn), tắt poll', async () => {
    vi.useFakeTimers();
    const spy = vi.spyOn(conversationApi, 'getNotifications')
      .mockRejectedValue(new ApiRequestError(404, { code: 'not_found', message: 'x', hint: '', retryable: false }, 'not_found'));
    const { result } = renderHook(() => useNotifications(true));
    await act(async () => { await Promise.resolve(); });
    expect(result.current.available).toBe(false);
    // advance — không poll lại (stopped)
    await act(async () => { vi.advanceTimersByTime(30000); await Promise.resolve(); });
    expect(spy).toHaveBeenCalledTimes(1);
  });
});
