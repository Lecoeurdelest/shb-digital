// NotificationBell.tsx — bell thông báo khách (D-57 T9-3) trên header Workspace (role=customer).
// Badge số sự kiện chưa xem; click → dropdown danh sách (title + thời gian); click item → mở ca.
// Ẩn hoàn toàn khi endpoint chưa lên (available=false — server T9-2 chưa có → 404).
//
// DF-B-08 (🔴 demo-killer): dropdown TRƯỚC đây position:absolute trong .notif nằm trong header
// .ws__topbar có overflow:hidden (cần cho máy chiếu 1366 — KHÔNG bỏ) → dropdown bị clip 87%,
// elementFromPoint trả .canvas__lobby → khách bấm chuông không thấy gì. FIX: PORTAL dropdown ra
// document.body + position:fixed theo bounding-rect nút chuông (thoát mọi ancestor overflow).
// Position recompute on open + resize/scroll. Click-ngoài dùng 2 ref (nút + dropdown — portal
// khiến dropdown KHÔNG còn trong .notif về DOM thật). Esc đóng.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNotifications } from '../hooks/useNotifications';
import type { NotificationItem } from '../types';
import './NotificationBell.css';

function fmtTs(ts: string): string {
  // ts iso → "HH:MM DD/MM" gọn; lỗi parse → cắt thô.
  if (!ts) return '';
  const s = ts.slice(0, 16).replace('T', ' ');
  return s;
}

const DROPDOWN_W = 300; // khớp width CSS — canh mép phải dropdown thẳng mép phải nút

export function NotificationBell({ enabled, onOpenConv }: { enabled: boolean; onOpenConv?: (convId: string) => void }) {
  const { items, unseen, available, markSeen } = useNotifications(enabled);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const dropRef = useRef<HTMLDivElement | null>(null);

  // Vị trí dropdown (fixed) tính từ rect nút chuông: mép PHẢI dropdown thẳng mép phải nút, dưới 6px.
  // Kẹp left ≥ 8 để không tràn trái ở viewport hẹp.
  const computePos = useCallback(() => {
    const b = btnRef.current?.getBoundingClientRect();
    if (!b) return;
    const left = Math.max(8, b.right - DROPDOWN_W);
    setPos({ top: b.bottom + 6, left });
  }, []);

  // đo NGAY khi mở (layout-effect: trước paint, tránh nháy vị trí) + theo resize/scroll khi đang mở.
  useLayoutEffect(() => {
    if (!open) return;
    computePos();
    const onReflow = () => computePos();
    window.addEventListener('resize', onReflow);
    window.addEventListener('scroll', onReflow, true); // capture: bắt scroll ở mọi ancestor
    return () => {
      window.removeEventListener('resize', onReflow);
      window.removeEventListener('scroll', onReflow, true);
    };
  }, [open, computePos]);

  // click NGOÀI cả nút LẪN dropdown → đóng (portal: dropdown không nằm trong .notif về DOM thật,
  // nên phải kiểm cả 2 ref, nếu không dropdown tự đóng khi bấm vào chính nó) + Esc đóng.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (btnRef.current?.contains(t) || dropRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
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
    <div className="notif">
      <button ref={btnRef} type="button" className="notif__btn" onClick={toggle} aria-label="Thông báo" data-testid="notif-bell">
        🔔
        {unseen > 0 && <span className="notif__badge" data-testid="notif-badge">{unseen}</span>}
      </button>
      {open && pos && createPortal(
        <div
          className="notif__dropdown"
          role="menu"
          data-testid="notif-dropdown"
          ref={dropRef}
          style={{ top: pos.top, left: pos.left }}
        >
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
        </div>,
        document.body,
      )}
    </div>
  );
}
