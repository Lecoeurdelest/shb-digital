// App.gate.test.tsx — auth gate (App) + Login (mock API luôn cho login OK).
// Chưa login → Login; login → Workspace. CONTRACT §1.
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from './App';

describe('Auth gate (App)', () => {
  it('mặc định hiện màn Login (chưa có user)', () => {
    render(<App />);
    expect(screen.getByRole('button', { name: /Đăng nhập/i })).toBeInTheDocument();
    // chưa vào Workspace
    expect(screen.queryByRole('button', { name: /Ca mới/i })).not.toBeInTheDocument();
  });

  it('login (mock chấp nhận mọi cred) → vào Workspace, hiện user badge', async () => {
    render(<App />);
    fireEvent.change(screen.getByLabelText('Tên đăng nhập'), { target: { value: 'user' } });
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'user' } });
    fireEvent.click(screen.getByRole('button', { name: /Đăng nhập/i }));

    // vào Workspace: nút "+ Ca mới" + badge user
    await waitFor(() => expect(screen.getByRole('button', { name: /Ca mới/i })).toBeInTheDocument());
    expect(screen.getByText(/user · RM/)).toBeInTheDocument();
  });

  it('đăng xuất → quay lại Login', async () => {
    render(<App />);
    fireEvent.change(screen.getByLabelText('Tên đăng nhập'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'admin' } });
    fireEvent.click(screen.getByRole('button', { name: /Đăng nhập/i }));
    await waitFor(() => expect(screen.getByText(/admin · Quản lý/)).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /Đăng xuất/i }));
    expect(screen.getByRole('button', { name: /Đăng nhập/i })).toBeInTheDocument();
  });
});
