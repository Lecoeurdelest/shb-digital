// useNotifications.ts — bell thông báo khách (D-57 T9-3). Poll GET /api/notifications 10s KHI enabled
// (role=customer). Trả {items, unseen}: unseen = số sự kiện MỚI hơn last-seen ts (localStorage) —
// click bell → đánh dấu đã xem (unseen=0). Dừng poll tab ẩn (visibilityState). 401/403/404 → tắt im
// (server T9-2 chưa lên → 404 → bell ẩn). KHÔNG SSE global (không thêm primitive — SPEC §2).
import { useCallback, useEffect, useState } from 'react';
import { conversationApi } from '../api';
import { ApiRequestError } from '../api/client';
import type { NotificationItem } from '../types';

const POLL_MS = 10000;
const LAST_SEEN_KEY = 'deg_notif_last_seen';

function readLastSeen(): string {
  try { return localStorage.getItem(LAST_SEEN_KEY) ?? ''; } catch { return ''; }
}
function writeLastSeen(ts: string): void {
  try { localStorage.setItem(LAST_SEEN_KEY, ts); } catch { /* ignore (private mode) */ }
}

export interface NotificationsState {
  items: NotificationItem[];
  unseen: number;
  available: boolean; // false = server chưa có endpoint (404) → ẩn bell
  markSeen: () => void;
}

export function useNotifications(enabled: boolean): NotificationsState {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [available, setAvailable] = useState(true);
  const [lastSeen, setLastSeen] = useState<string>(() => readLastSeen());

  useEffect(() => {
    if (!enabled) { setItems([]); return; }
    let alive = true;
    let timer = 0;
    let stopped = false;

    const tick = () => {
      if (document.visibilityState === 'hidden') { schedule(); return; }
      conversationApi
        .getNotifications()
        .then((rows) => {
          if (!alive) return;
          setItems(Array.isArray(rows) ? rows : []);
          setAvailable(true);
          schedule();
        })
        .catch((e: unknown) => {
          if (!alive) return;
          // 404 = endpoint chưa lên (T9-2 chưa) → ẩn bell im. 401/403 = mất quyền → tắt.
          if (e instanceof ApiRequestError && (e.status === 404 || e.status === 401 || e.status === 403)) {
            stopped = true;
            setAvailable(false);
            setItems([]);
            return;
          }
          schedule(); // lỗi mạng tạm → thử lại
        });
    };
    const schedule = () => { if (!stopped && alive) timer = window.setTimeout(tick, POLL_MS); };

    tick();
    const onVisible = () => {
      if (document.visibilityState === 'visible' && !stopped && alive) { window.clearTimeout(timer); tick(); }
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      alive = false;
      window.clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [enabled]);

  // unseen = số item có ts > lastSeen. markSeen → lưu ts mới nhất, unseen về 0.
  const unseen = items.filter((n) => n.ts > lastSeen).length;
  const markSeen = useCallback(() => {
    const newest = items.reduce((mx, n) => (n.ts > mx ? n.ts : mx), lastSeen);
    if (newest !== lastSeen) { writeLastSeen(newest); setLastSeen(newest); }
    else if (items.length > 0) { setLastSeen(newest); } // đảm bảo unseen về 0 ngay cả khi ts bằng
  }, [items, lastSeen]);

  return { items, unseen, available, markSeen };
}
