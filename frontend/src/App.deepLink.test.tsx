import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { conversationApi } from './api';
import { ApiRequestError } from './api/client';
import { mockBackend } from './api/mock';
import type { ApprovalRow, AuthUser } from './types';

const APPROVAL_ID = '0198a4e1-7b6c-7abc-0012-1234567890ab';
const OTHER_ID = '11111111-2222-3333-4444-555555555555';
const DEEP_LINK = `/?tab=approvals&approval=${APPROVAL_ID}`;

const focusedPending: ApprovalRow = {
  id: APPROVAL_ID,
  conv_id: 'focused-conversation',
  task_id: null,
  action: 'disburse',
  payload: { loan_id: 'L108' },
  status: 'pending',
  display: { customer_name: 'Hộ KD Tân Phú', loan_id: 'L108', amount_vnd: 594_000_000, lane: 'yellow' },
};

const otherPending: ApprovalRow = {
  id: OTHER_ID,
  conv_id: 'other-conversation',
  task_id: null,
  action: 'disburse',
  payload: {},
  status: 'pending',
};

afterEach(() => {
  vi.restoreAllMocks();
  mockBackend.reset();
  window.history.replaceState(null, '', '/');
});

function setLocation(path: string) {
  window.history.replaceState(null, '', path);
}

function mockAdminBoot() {
  return vi.spyOn(conversationApi, 'me').mockResolvedValue({
    user: { username: 'admin', role: 'admin', owner_id: null },
  });
}

describe('App approval deep-link auth handoff', () => {
  it('admin boot opens the queue and highlights the exact pending ticket', async () => {
    setLocation(DEEP_LINK);
    mockAdminBoot();
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([focusedPending]);
    const exactSpy = vi.spyOn(conversationApi, 'getApproval').mockResolvedValue(focusedPending);

    render(<App />);

    const row = await screen.findByTestId(`queue-row-${APPROVAL_ID}`);
    expect(row).toHaveClass('ct__appr-wrap--focused');
    expect(screen.getByText('Hàng chờ phê duyệt (1)')).toBeInTheDocument();
    expect(exactSpy).toHaveBeenCalledTimes(1);
    expect(exactSpy).toHaveBeenCalledWith(APPROVAL_ID);
  });

  it('anonymous deep-link auto-opens Login and password login resumes the exact decided ticket', async () => {
    setLocation(DEEP_LINK);
    vi.spyOn(conversationApi, 'me').mockRejectedValue(new Error('401'));
    vi.spyOn(conversationApi, 'getAuthProviders').mockResolvedValue({ password: true, google: false });
    vi.spyOn(conversationApi, 'login').mockResolvedValue({
      token: 'token',
      user: { username: 'admin', role: 'admin', owner_id: null },
    });
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([otherPending]);
    vi.spyOn(conversationApi, 'getApproval').mockResolvedValue({
      ...focusedPending,
      status: 'rejected',
      reason: 'Thiếu hồ sơ pháp lý',
    });

    render(<App />);

    const modal = within(await screen.findByTestId('landing-authmodal'));
    expect(window.location.pathname + window.location.search).toBe(DEEP_LINK);
    fireEvent.change(modal.getByLabelText('Tên đăng nhập'), { target: { value: 'admin' } });
    fireEvent.change(modal.getByLabelText('Mật khẩu'), { target: { value: 'admin' } });
    fireEvent.click(modal.getByRole('button', { name: /^Đăng nhập$/ }));

    const row = await screen.findByTestId(`queue-row-${APPROVAL_ID}`);
    expect(row).toHaveClass('ct__appr-wrap--focused');
    expect(within(row).getByText('Đã từ chối')).toBeInTheDocument();
    expect(within(row).queryByRole('button', { name: /Duyệt|Từ chối/ })).not.toBeInTheDocument();
    expect(window.location.pathname + window.location.search).toBe(DEEP_LINK);
  });

  it.each([
    { username: 'c001', role: 'customer', owner_id: 'C001' },
    { username: 'user', role: 'user', owner_id: null },
  ] satisfies AuthUser[])('$role session never mounts Tower or calls approval APIs', async (user) => {
    setLocation(DEEP_LINK);
    vi.spyOn(conversationApi, 'me').mockResolvedValue({ user });
    const listSpy = vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([]);
    const exactSpy = vi.spyOn(conversationApi, 'getApproval').mockResolvedValue(focusedPending);
    const decideSpy = vi.spyOn(conversationApi, 'decideApproval').mockResolvedValue({
      ...focusedPending,
      status: 'approved',
    });

    render(<App />);

    await screen.findByRole('button', { name: /Phiên xử lý/i });
    expect(screen.queryByTestId(`queue-row-${APPROVAL_ID}`)).not.toBeInTheDocument();
    expect(screen.queryByTestId('open-tower')).not.toBeInTheDocument();
    expect(listSpy).not.toHaveBeenCalled();
    expect(exactSpy).not.toHaveBeenCalled();
    expect(decideSpy).not.toHaveBeenCalled();
  });

  it.each([
    '/?tab=approvals&approval=not-a-uuid',
    `/?tab=queue&approval=${APPROVAL_ID}`,
    `/?tab=approvals&approval=${APPROVAL_ID}&approval=${OTHER_ID}`,
    `/?tab=approvals&approval=${APPROVAL_ID}&extra=1`,
  ])('malformed/non-exact URL %s stays in admin Workspace without exact fetch', async (path) => {
    setLocation(path);
    mockAdminBoot();
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([]);
    const exactSpy = vi.spyOn(conversationApi, 'getApproval').mockResolvedValue(focusedPending);

    render(<App />);

    await screen.findByTestId('open-tower');
    expect(screen.queryByRole('button', { name: '← Workspace' })).not.toBeInTheDocument();
    expect(exactSpy).not.toHaveBeenCalled();
  });

  it('exact 404 leaves the independently loaded pending queue usable', async () => {
    setLocation(DEEP_LINK);
    mockAdminBoot();
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([otherPending]);
    vi.spyOn(conversationApi, 'getApproval').mockRejectedValue(
      new ApiRequestError(
        404,
        { code: 'not_found', message: 'Không có phiếu.', hint: 'Kiểm lại liên kết.', retryable: false },
        'not_found',
      ),
    );

    render(<App />);

    expect(await screen.findByTestId(`queue-row-${OTHER_ID}`)).toBeInTheDocument();
    expect(await screen.findByTestId('focused-approval-error')).toBeInTheDocument();
    expect(screen.getByText('Hàng chờ phê duyệt (1)')).toBeInTheDocument();
  });

  it('ordinary anonymous URL still shows Landing with the Login modal closed', async () => {
    vi.spyOn(conversationApi, 'me').mockRejectedValue(new Error('401'));
    vi.spyOn(conversationApi, 'getAuthProviders').mockResolvedValue({ password: true, google: false });
    const listSpy = vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([]);
    const exactSpy = vi.spyOn(conversationApi, 'getApproval').mockResolvedValue(focusedPending);

    render(<App />);

    await screen.findByTestId('landing-login');
    expect(screen.queryByTestId('landing-authmodal')).not.toBeInTheDocument();
    expect(listSpy).not.toHaveBeenCalled();
    expect(exactSpy).not.toHaveBeenCalled();
  });
});
