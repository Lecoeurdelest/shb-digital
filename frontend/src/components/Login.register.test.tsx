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

  // T11-4: googleEnabled do CALLER truyền (Login KHÔNG tự fetch — chống flaky). Prop điều khiển khối Google.
  it('googleEnabled=false → KHÔNG có nút/chuỗi "Google", KHÔNG skeleton (ẩn trọn)', () => {
    const { container } = render(<Login onSuccess={vi.fn()} googleEnabled={false} />);
    expect(screen.queryByTestId('login-google')).not.toBeInTheDocument();
    expect(screen.queryByTestId('login-google-reserve')).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Google/i);
  });

  it('googleEnabled=true → nút Google hiện (cả tab đăng nhập lẫn đăng ký)', () => {
    render(<Login onSuccess={vi.fn()} googleEnabled={true} />);
    expect(screen.getByTestId('login-google')).toHaveTextContent(/Đăng nhập với Google/);
    // đổi sang tab đăng ký → nút vẫn hiện (text đổi)
    fireEvent.click(screen.getByTestId('tab-register'));
    expect(screen.getByTestId('login-google')).toHaveTextContent(/Đăng ký với Google/);
  });

  it('googleEnabled=undefined (đang tải providers) → RESERVE skeleton, CHƯA nút thật (chống layout-shift)', () => {
    render(<Login onSuccess={vi.fn()} googleEnabled={undefined} />);
    expect(screen.getByTestId('login-google-reserve')).toBeInTheDocument();
    expect(screen.queryByTestId('login-google')).not.toBeInTheDocument();
  });

  it('Login KHÔNG tự gọi getAuthProviders (caller prefetch + truyền prop — chống double-fetch/flaky)', () => {
    const spy = vi.spyOn(conversationApi, 'getAuthProviders');
    render(<Login onSuccess={vi.fn()} googleEnabled={true} />);
    expect(spy).not.toHaveBeenCalled();
  });

  // DF-A-01 (D-64): hint demo bề mặt public CHỈ gợi ý c001 (khách) — KHÔNG lộ admin/RM.
  it('DF-A-01: hint demo chỉ c001, KHÔNG có admin/user-RM', () => {
    render(<Login onSuccess={vi.fn()} />);
    const hint = screen.getByText(/Demo:/);
    expect(hint).toHaveTextContent(/c001 \/ c001/);
    expect(hint).not.toHaveTextContent(/admin \/ admin/);
    expect(hint).not.toHaveTextContent(/user \/ user/);
  });

  // DF-A-03: message lỗi đăng ký ĐÚNG nguyên nhân (email sai ≠ thiếu user/pass).
  it('DF-A-03: register email SAI định dạng → message "Email không hợp lệ" (không phải thiếu user/pass)', async () => {
    const spy = vi.spyOn(conversationApi, 'register');
    render(<Login onSuccess={vi.fn()} />);
    fireEvent.click(screen.getByTestId('tab-register'));
    fireEvent.change(screen.getByLabelText('Tên đăng nhập'), { target: { value: 'dogfood-a1' } });
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'dogfood123' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'khong-phai-email' } });
    fireEvent.click(screen.getByRole('button', { name: /Đăng ký & vào/ }));
    expect(screen.getByRole('alert')).toHaveTextContent(/Email không hợp lệ/);
    expect(spy).not.toHaveBeenCalled(); // không gửi request khi email sai
  });

  it('DF-A-03: register email RỖNG (tuỳ chọn) → hợp lệ, gọi register (email undefined)', async () => {
    const spy = vi.spyOn(conversationApi, 'register').mockResolvedValue({ token: 't', user: { username: 'a', role: 'customer', owner_id: null } });
    render(<Login onSuccess={vi.fn()} />);
    fireEvent.click(screen.getByTestId('tab-register'));
    fireEvent.change(screen.getByLabelText('Tên đăng nhập'), { target: { value: 'dogfood-a2' } });
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'dogfood123' } });
    // email để rỗng
    fireEvent.click(screen.getByRole('button', { name: /Đăng ký & vào/ }));
    await waitFor(() => expect(spy).toHaveBeenCalledWith('dogfood-a2', 'dogfood123', undefined));
  });

  it('DF-A-03: thiếu user/pass → vẫn message "Nhập đủ tên đăng nhập và mật khẩu"', () => {
    render(<Login onSuccess={vi.fn()} />);
    fireEvent.click(screen.getByTestId('tab-register'));
    fireEvent.change(screen.getByLabelText('Tên đăng nhập'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: /Đăng ký & vào/ }));
    expect(screen.getByRole('alert')).toHaveTextContent(/Nhập đủ tên đăng nhập và mật khẩu/);
  });
});
