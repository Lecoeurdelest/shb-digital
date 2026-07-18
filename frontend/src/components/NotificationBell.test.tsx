// NotificationBell.test.tsx — DF-B-08: dropdown portal ra body, mở/đóng (click-ngoài + Esc),
// click item → onOpenConv. Portal khiến dropdown KHÔNG nằm trong .notif về DOM → test qua screen (body).
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NotificationBell } from './NotificationBell';
import type { NotificationsState } from '../hooks/useNotifications';
import type { NotificationItem } from '../types';

const ITEMS: NotificationItem[] = [
  { type: 'approval_decided', title: 'Khoản vay L001 đã được duyệt', ts: '2026-07-19T10:00:00', conv_id: 'c1' },
  { type: 'disbursed', title: 'Giải ngân 500 triệu', ts: '2026-07-19T11:00:00', conv_id: 'c2' },
];

// mock hook: điều khiển state trả về cho component (không đụng network/poll).
let mockState: NotificationsState;
vi.mock('../hooks/useNotifications', () => ({
  useNotifications: () => mockState,
}));

beforeEach(() => {
  mockState = { items: ITEMS, unseen: 2, available: true, markSeen: vi.fn() };
});

describe('NotificationBell (DF-B-08)', () => {
  it('enabled=false → không render (null)', () => {
    const { container } = render(<NotificationBell enabled={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('available=false (endpoint chưa lên) → không render', () => {
    mockState = { ...mockState, available: false };
    const { container } = render(<NotificationBell enabled={true} />);
    expect(container.firstChild).toBeNull();
  });

  it('badge = unseen; dropdown ẨN mặc định', () => {
    render(<NotificationBell enabled={true} />);
    expect(screen.getByTestId('notif-badge')).toHaveTextContent('2');
    expect(screen.queryByTestId('notif-dropdown')).not.toBeInTheDocument();
  });

  it('click chuông → dropdown MỞ (portal ra body) + markSeen gọi', () => {
    render(<NotificationBell enabled={true} />);
    fireEvent.click(screen.getByTestId('notif-bell'));
    const drop = screen.getByTestId('notif-dropdown');
    expect(drop).toBeInTheDocument();
    // portal: dropdown nằm trên document.body, KHÔNG trong .notif
    expect(drop.closest('.notif')).toBeNull();
    expect(document.body.contains(drop)).toBe(true);
    expect(mockState.markSeen).toHaveBeenCalled();
    // 2 item render
    expect(screen.getAllByTestId('notif-item')).toHaveLength(2);
  });

  it('click item → onOpenConv(conv_id) + đóng dropdown', () => {
    const onOpen = vi.fn();
    render(<NotificationBell enabled={true} onOpenConv={onOpen} />);
    fireEvent.click(screen.getByTestId('notif-bell'));
    fireEvent.click(screen.getAllByTestId('notif-item')[0]);
    expect(onOpen).toHaveBeenCalledWith('c1');
    expect(screen.queryByTestId('notif-dropdown')).not.toBeInTheDocument();
  });

  it('Esc → đóng dropdown', async () => {
    render(<NotificationBell enabled={true} />);
    fireEvent.click(screen.getByTestId('notif-bell'));
    expect(screen.getByTestId('notif-dropdown')).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByTestId('notif-dropdown')).not.toBeInTheDocument());
  });

  it('click NGOÀI (nút + dropdown) → đóng; click TRONG dropdown → KHÔNG đóng', async () => {
    render(<NotificationBell enabled={true} />);
    fireEvent.click(screen.getByTestId('notif-bell'));
    const drop = screen.getByTestId('notif-dropdown');
    // click bên trong dropdown head (không phải item) → vẫn mở (portal dual-ref hoạt động)
    fireEvent.mouseDown(drop.querySelector('.notif__head') as Element);
    expect(screen.getByTestId('notif-dropdown')).toBeInTheDocument();
    // click ra ngoài (body) → đóng
    fireEvent.mouseDown(document.body);
    await waitFor(() => expect(screen.queryByTestId('notif-dropdown')).not.toBeInTheDocument());
  });

  it('items rỗng → "Chưa có thông báo"', () => {
    mockState = { items: [], unseen: 0, available: true, markSeen: vi.fn() };
    render(<NotificationBell enabled={true} />);
    fireEvent.click(screen.getByTestId('notif-bell'));
    expect(screen.getByText(/Chưa có thông báo/)).toBeInTheDocument();
  });
});
