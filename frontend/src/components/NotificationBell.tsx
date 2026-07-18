// NotificationBell.tsx — bell thông báo khách (D-57 T9-3) trên header Workspace (role=customer).
// Badge số sự kiện chưa xem; click → dropdown danh sách (title + thời gian); click item → mở ca.
// Ẩn hoàn toàn khi endpoint chưa lên (available=false — server T9-2 chưa có → 404).
import { useEffect, useRef, useState } from 'react';
import { useNotifications } from '../hooks/useNotifications';
import type { NotificationItem } from '../types';
import './NotificationBell.css';

function fmtTs(ts: string): string {
  // ts iso → "HH:MM DD/MM" gọn; lỗi parse → cắt thô.
  if (!ts) return '';
  const s = ts.slice(0, 16).replace('T', ' ');
  return s;
}

export function NotificationBell({ enabled, onOpenConv }: { enabled: boolean; onOpenConv?: (convId: string) => void }) {
  const { items, unseen, available, markSeen } = useNotifications(enabled);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  // click ngoài → đóng dropdown
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  if (!enabled || !available) return null; // khách + endpoint có mới hiện

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) markSeen(); // mở dropdown = đã xem → unseen về 0
  };

  const clickItem = (n: NotificationItem) => {
    setOpen(false);
    if (n.conv_id && onOpenConv) onOpenConv(n.conv_id);
  };

  return (
    <div className="notif" ref={ref}>
      <button type="button" className="notif__btn" onClick={toggle} aria-label="Thông báo" data-testid="notif-bell">
        🔔
        {unseen > 0 && <span className="notif__badge" data-testid="notif-badge">{unseen}</span>}
      </button>
      {open && (
        <div className="notif__dropdown" role="menu" data-testid="notif-dropdown">
          <div className="notif__head">Thông báo</div>
          {items.length === 0 ? (
            <div className="notif__empty">Chưa có thông báo nào.</div>
          ) : (
            items.map((n, i) => (
              <button
                key={`${n.ts}-${i}`}
                type="button"
                className="notif__item"
                onClick={() => clickItem(n)}
                data-testid="notif-item"
              >
                <span className={`notif__dot notif__dot--${n.type === 'disbursed' ? 'pass' : 'run'}`} />
                <span className="notif__item-body">
                  <span className="notif__item-title">{n.title}</span>
                  <span className="notif__item-ts">{fmtTs(n.ts)}</span>
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
