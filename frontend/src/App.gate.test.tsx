// App.gate.test.tsx — auth gate + boot-check /me (D-39). Mock me() mặc định ném 401 (mock mode) →
// App qua phase checking → LANDING (mặt tiền); Login thật nằm trong modal (nav "Đăng nhập").
// Test skip-auth: spyOn me() trả 200 admin → vào thẳng Workspace.
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import App from './App';
import { conversationApi } from './api';

afterEach(() => vi.restoreAllMocks());

// mở modal auth từ Landing rồi trả scope modal (Login thật nằm trong)
async function openAuthModal() {
  await screen.findByTestId('landing-login');
  fireEvent.click(screen.getByTestId('landing-login'));
  return within(screen.getByTestId('landing-authmodal'));
}

describe('Auth gate (App) — boot-check /me', () => {
  it('/me 401 (mock) → sau checking hiện Landing (chưa vào Workspace)', async () => {
    render(<App />);
    // boot-check chạy → Landing xuất hiện (async), có nút Đăng nhập trên nav
    await waitFor(() => expect(screen.getByTestId('landing-login')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /Ca mới/i })).not.toBeInTheDocument();
  });

  it('login qua modal (mock chấp nhận mọi cred) → vào Workspace, hiện user badge', async () => {
    render(<App />);
    const modal = await openAuthModal();
    fireEvent.change(modal.getByLabelText('Tên đăng nhập'), { target: { value: 'user' } });
    fireEvent.change(modal.getByLabelText('Mật khẩu'), { target: { value: 'user' } });
    fireEvent.click(modal.getByRole('button', { name: /Đăng nhập/i }));

    await waitFor(() => expect(screen.getByRole('button', { name: /Ca mới/i })).toBeInTheDocument());
    expect(screen.getByText(/user · RM/)).toBeInTheDocument();
  });

  it('đăng xuất → quay lại Landing', async () => {
    render(<App />);
    const modal = await openAuthModal();
    fireEvent.change(modal.getByLabelText('Tên đăng nhập'), { target: { value: 'admin' } });
    fireEvent.change(modal.getByLabelText('Mật khẩu'), { target: { value: 'admin' } });
    fireEvent.click(modal.getByRole('button', { name: /Đăng nhập/i }));
    await waitFor(() => expect(screen.getByText(/admin · Quản lý/)).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /Đăng xuất/i }));
    expect(screen.getByTestId('landing-login')).toBeInTheDocument();
  });

  it('boot-check /me 200 admin (DEV_SKIP_AUTH) → SKIP Login vào thẳng Workspace admin', async () => {
    vi.spyOn(conversationApi, 'me').mockResolvedValue({ user: { username: 'admin', role: 'admin' } });
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([]);
    render(<App />);
    // KHÔNG qua Login — vào thẳng Workspace, badge admin
    await waitFor(() => expect(screen.getByRole('button', { name: /Ca mới/i })).toBeInTheDocument());
    expect(screen.getByText(/admin · Quản lý/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Đăng nhập/i })).not.toBeInTheDocument();
  });

  // ── D-56 gate theo role (customer vs admin) ──
  it('customer (role=customer) → KHÔNG có nút Control Tower, vào thẳng Workspace khách', async () => {
    vi.spyOn(conversationApi, 'me').mockResolvedValue({ user: { username: 'c001', role: 'customer', owner_id: 'C001' } });
    render(<App />);
    await waitFor(() => expect(screen.getByRole('button', { name: /Ca mới/i })).toBeInTheDocument());
    expect(screen.getByText(/c001 · Khách hàng/)).toBeInTheDocument();
    // nút Tower ẩn với khách
    expect(screen.queryByTestId('open-tower')).not.toBeInTheDocument();
  });

  it('admin → CÓ nút Control Tower', async () => {
    vi.spyOn(conversationApi, 'me').mockResolvedValue({ user: { username: 'admin', role: 'admin', owner_id: null } });
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([]);
    render(<App />);
    await waitFor(() => expect(screen.getByTestId('open-tower')).toBeInTheDocument());
  });

  it('admin + có phiếu pending → badge phiếu-bay nổi trên nút Tower', async () => {
    vi.spyOn(conversationApi, 'me').mockResolvedValue({ user: { username: 'admin', role: 'admin', owner_id: null } });
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([
      { id: 'a1', conv_id: 'c1', task_id: null, action: 'disburse', payload: {}, status: 'pending' },
      { id: 'a2', conv_id: 'c2', task_id: null, action: 'disburse', payload: {}, status: 'pending' },
    ]);
    render(<App />);
    await waitFor(() => expect(screen.getByTestId('tower-badge')).toHaveTextContent('2'));
  });
});
