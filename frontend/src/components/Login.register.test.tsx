// Login.register.test.tsx — tab đăng ký khách mới (D-57 T9-3): switch tab, register success/lỗi 409.
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { Login } from './Login';
import { conversationApi } from '../api';
import { ApiRequestError } from '../api/client';

afterEach(() => vi.restoreAllMocks());

describe('Login — đăng ký khách mới (D-57)', () => {
  it('mặc định tab Đăng nhập; bấm tab → hiện field Email (register)', () => {
    render(<Login onSuccess={vi.fn()} />);
    expect(screen.queryByLabelText('Email')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('tab-register'));
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
  });

  it('đăng ký thành công → onSuccess(user role customer)', async () => {
    const onSuccess = vi.fn();
    const spy = vi.spyOn(conversationApi, 'register').mockResolvedValue({
      token: 't', user: { username: 'newcust', role: 'customer', owner_id: null },
    });
    render(<Login onSuccess={onSuccess} />);
    fireEvent.click(screen.getByTestId('tab-register'));
    fireEvent.change(screen.getByLabelText('Tên đăng nhập'), { target: { value: 'newcust' } });
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'pass1234' } });
    fireEvent.click(screen.getByRole('button', { name: /Đăng ký & vào/ }));
    await waitFor(() => expect(spy).toHaveBeenCalledWith('newcust', 'pass1234', undefined));
    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith({ username: 'newcust', role: 'customer', owner_id: null }));
  });

  it('register 409 username_taken → hiện message body 4-field', async () => {
    vi.spyOn(conversationApi, 'register').mockRejectedValue(
      new ApiRequestError(409, { code: 'username_taken', message: 'Tên đăng nhập đã được dùng.', hint: 'Chọn tên khác.', retryable: false }, 'username_taken'),
    );
    render(<Login onSuccess={vi.fn()} />);
    fireEvent.click(screen.getByTestId('tab-register'));
    fireEvent.change(screen.getByLabelText('Tên đăng nhập'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'pass1234' } });
    fireEvent.click(screen.getByRole('button', { name: /Đăng ký & vào/ }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Tên đăng nhập đã được dùng.'));
  });

  it('email tuỳ chọn có điền → truyền vào register', async () => {
    const spy = vi.spyOn(conversationApi, 'register').mockResolvedValue({ token: 't', user: { username: 'x', role: 'customer', owner_id: null } });
    render(<Login onSuccess={vi.fn()} />);
    fireEvent.click(screen.getByTestId('tab-register'));
    fireEvent.change(screen.getByLabelText('Tên đăng nhập'), { target: { value: 'newcust' } });
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'pass1234' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'a@b.com' } });
    fireEvent.click(screen.getByRole('button', { name: /Đăng ký & vào/ }));
    await waitFor(() => expect(spy).toHaveBeenCalledWith('newcust', 'pass1234', 'a@b.com'));
  });

  // T11-4: google ẩn TRỌN khi providers.google=false (finding tester #6 — không sót text/nút Google)
  it('providers.google=false → KHÔNG có nút/chuỗi "Google" nào trong DOM login', async () => {
    vi.spyOn(conversationApi, 'getAuthProviders').mockResolvedValue({ password: true, google: false });
    const { container } = render(<Login onSuccess={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole('button', { name: /^Đăng nhập$/ })).toBeInTheDocument());
    expect(screen.queryByTestId('login-google')).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Google/i);
  });

  it('providers.google=true → nút Google hiện', async () => {
    vi.spyOn(conversationApi, 'getAuthProviders').mockResolvedValue({ password: true, google: true });
    render(<Login onSuccess={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('login-google')).toBeInTheDocument());
  });
});
