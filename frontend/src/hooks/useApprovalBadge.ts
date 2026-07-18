// useApprovalBadge.ts — badge phiếu-bay cho NGÂN HÀNG (admin, D-56). Poll GET /api/approvals?status=pending
// mỗi 5s KHI enabled (role=admin) → trả count phiếu chờ. KHÔNG mở SSE global (không thêm primitive
// — SPEC §2). Dừng poll khi tab ẩn (visibilityState) để đỡ spam server. 403 (token hết/role đổi) →
// tắt poll im lặng, không error-loop. count=0 → badge tắt (Tower nút + tab queue đọc count này).
import { useEffect, useState } from 'react';
import { conversationApi } from '../api';
import { ApiRequestError } from '../api/client';

const POLL_MS = 5000;

export function useApprovalBadge(enabled: boolean): number {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!enabled) {
      setCount(0);
      return;
    }
    let alive = true;
    let timer = 0;
    let stopped = false; // 403 → ngừng hẳn (không error-loop)

    const tick = () => {
      // tab ẩn → bỏ nhịp này (không gọi server), lịch lại nhịp sau
      if (document.visibilityState === 'hidden') {
        schedule();
        return;
      }
      conversationApi
        .listApprovals('pending')
        .then((rows) => {
          if (!alive) return;
          setCount(Array.isArray(rows) ? rows.length : 0);
          schedule();
        })
        .catch((e: unknown) => {
          if (!alive) return;
          // 403 (role không phải admin / token hết) → tắt im lặng, KHÔNG lặp lỗi
          if (e instanceof ApiRequestError && e.status === 403) {
            stopped = true;
            setCount(0);
            return;
          }
          schedule(); // lỗi mạng tạm → thử lại nhịp sau (không tắt)
        });
    };

    const schedule = () => {
      if (stopped || !alive) return;
      timer = window.setTimeout(tick, POLL_MS);
    };

    // poll ngay lần đầu (không đợi 5s) để badge nổi sớm
    tick();
    // tab hiện lại → poll ngay (bắt phiếu tích luỹ lúc ẩn) thay vì đợi hết nhịp
    const onVisible = () => {
      if (document.visibilityState === 'visible' && !stopped && alive) {
        window.clearTimeout(timer);
        tick();
      }
    };
    document.addEventListener('visibilitychange', onVisible);

    return () => {
      alive = false;
      window.clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [enabled]);

  return count;
}
