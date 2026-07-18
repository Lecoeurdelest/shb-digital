// useApprovalBadge.test.tsx — badge phiếu-bay (D-56): poll count, enabled gate, 403 tắt, count đổi.
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { conversationApi } from '../api';
import { ApiRequestError } from '../api/client';
import type { ApprovalRow } from '../types';

function rows(n: number): ApprovalRow[] {
  return Array.from({ length: n }, (_, i) => ({
    id: `a${i}`, conv_id: 'c1', task_id: null, action: 'disburse', payload: {}, status: 'pending',
  }));
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.useRealTimers());

import { useApprovalBadge } from './useApprovalBadge';

describe('useApprovalBadge', () => {
  it('enabled=false → count 0, KHÔNG gọi listApprovals', () => {
    const spy = vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([]);
    const { result } = renderHook(() => useApprovalBadge(false));
    expect(result.current).toBe(0);
    expect(spy).not.toHaveBeenCalled();
  });

  it('enabled=true → poll → count = số phiếu pending', async () => {
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue(rows(3));
    const { result } = renderHook(() => useApprovalBadge(true));
    await waitFor(() => expect(result.current).toBe(3));
  });

  it('count đổi giữa các nhịp → cập nhật (poll interval)', async () => {
    vi.useFakeTimers();
    const spy = vi.spyOn(conversationApi, 'listApprovals')
      .mockResolvedValueOnce(rows(1))
      .mockResolvedValueOnce(rows(4));
    const { result } = renderHook(() => useApprovalBadge(true));
    // nhịp 1 (tick ngay) → 1
    await act(async () => { await Promise.resolve(); });
    expect(result.current).toBe(1);
    // nhịp 2 sau 5s → 4
    await act(async () => { vi.advanceTimersByTime(5000); await Promise.resolve(); });
    expect(result.current).toBe(4);
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it('403 (role đổi/token hết) → tắt poll im lặng, count 0, KHÔNG lặp lỗi', async () => {
    vi.useFakeTimers();
    const spy = vi.spyOn(conversationApi, 'listApprovals')
      .mockRejectedValue(new ApiRequestError(403, { code: 'forbidden', message: 'x', hint: '', retryable: false }, 'forbidden'));
    const { result } = renderHook(() => useApprovalBadge(true));
    await act(async () => { await Promise.resolve(); });
    expect(result.current).toBe(0);
    // advance nhiều nhịp — KHÔNG gọi lại (stopped)
    await act(async () => { vi.advanceTimersByTime(20000); await Promise.resolve(); });
    expect(spy).toHaveBeenCalledTimes(1); // chỉ lần đầu, sau đó ngừng hẳn
  });

  it('enabled false→true→false → count reset 0 khi tắt', async () => {
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue(rows(2));
    const { result, rerender } = renderHook(({ on }) => useApprovalBadge(on), { initialProps: { on: true } });
    await waitFor(() => expect(result.current).toBe(2));
    rerender({ on: false });
    expect(result.current).toBe(0);
  });

  // DF-B-06: tick ĐẦU fetch VÔ ĐIỀU KIỆN dù tab hidden (badge nổi ngay + automation verify được);
  // tick 2+ giữ skip-khi-hidden (đỡ spam server).
  it('DF-B-06: mount khi tab HIDDEN → vẫn fetch 1 lần + set count (không skip tick đầu)', async () => {
    const orig = Object.getOwnPropertyDescriptor(Document.prototype, 'visibilityState');
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
    const spy = vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue(rows(4));
    const { result } = renderHook(() => useApprovalBadge(true));
    await waitFor(() => expect(result.current).toBe(4)); // fetch dù hidden
    expect(spy).toHaveBeenCalledTimes(1);
    if (orig) Object.defineProperty(document, 'visibilityState', orig);
  });

  it('DF-B-06: tick 2+ khi hidden → SKIP (giữ hành vi cũ, không spam server)', async () => {
    vi.useFakeTimers();
    const orig = Object.getOwnPropertyDescriptor(Document.prototype, 'visibilityState');
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
    const spy = vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue(rows(1));
    renderHook(() => useApprovalBadge(true));
    await act(async () => { await Promise.resolve(); }); // tick đầu (initial) fetch
    expect(spy).toHaveBeenCalledTimes(1);
    // nhịp sau (5s) — hidden → skip, KHÔNG gọi thêm
    await act(async () => { vi.advanceTimersByTime(6000); await Promise.resolve(); });
    expect(spy).toHaveBeenCalledTimes(1); // vẫn 1 (tick 2 skip vì hidden)
    if (orig) Object.defineProperty(document, 'visibilityState', orig);
  });
});
