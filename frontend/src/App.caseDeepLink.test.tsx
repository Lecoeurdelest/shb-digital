import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { conversationApi } from './api';
import type { AuthUser, CaseSummary } from './types';

const CASE_ID = '0198a4e1-7b6c-7abc-0012-1234567890ab';
const OTHER_ID = '11111111-2222-3333-4444-555555555555';
const DEEP_LINK = `/?tab=cases&case=${CASE_ID}`;

const focusedCase: CaseSummary = {
  id: CASE_ID,
  source_system: 'los',
  external_case_id: 'LOS-OUTSIDE-050',
  internal_application_id: null,
  party_reference: 'CIF-050',
  product_code: 'SME_SECURED',
  loan_amount_vnd: 500_000_000,
  case_status: 'ready_for_preassessment',
  next_action: 'Bắt đầu sơ thẩm.',
  document_count: 3,
  missing_fields: [],
  source_version: 5,
  data_as_of: '2026-08-24T10:00:00Z',
  synced_at: '2026-08-24T10:01:00Z',
  conversation_id: null,
  assessment: { lane: null, created_at: null },
};

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(null, '', '/');
});

function setLocation(path: string) {
  window.history.replaceState(null, '', path);
}

function mockTowerData() {
  vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([]);
  vi.spyOn(conversationApi, 'listCases').mockResolvedValue([]);
}

describe('App exact-case deep-link auth handoff (D-83)', () => {
  it('admin boot opens assessments and exact-fetches/highlights a case outside page 50', async () => {
    setLocation(DEEP_LINK);
    vi.spyOn(conversationApi, 'me').mockResolvedValue({
      user: { username: 'admin', role: 'admin', owner_id: null },
    });
    mockTowerData();
    const exact = vi.spyOn(conversationApi, 'getCase').mockResolvedValue(focusedCase);

    render(<App />);

    const target = await screen.findByTestId(`case-row-${CASE_ID}`);
    expect(target).toHaveClass('casewb__row--focused', 'casewb__row--active');
    expect(exact).toHaveBeenCalledTimes(1);
    expect(exact).toHaveBeenCalledWith(CASE_ID);
    expect(screen.getByText('Cơ sở sơ thẩm')).toHaveClass('ct__tab--active');
  });

  it('anonymous exact URL stays intact through password login and resumes the target', async () => {
    setLocation(DEEP_LINK);
    vi.spyOn(conversationApi, 'me').mockRejectedValue(new Error('401'));
    vi.spyOn(conversationApi, 'getAuthProviders').mockResolvedValue({ password: true, google: false });
    vi.spyOn(conversationApi, 'login').mockResolvedValue({
      token: 'token', user: { username: 'admin', role: 'admin', owner_id: null },
    });
    mockTowerData();
    const exact = vi.spyOn(conversationApi, 'getCase').mockResolvedValue(focusedCase);

    render(<App />);

    const modal = within(await screen.findByTestId('landing-authmodal'));
    expect(window.location.pathname + window.location.search).toBe(DEEP_LINK);
    fireEvent.change(modal.getByLabelText('Tên đăng nhập'), { target: { value: 'admin' } });
    fireEvent.change(modal.getByLabelText('Mật khẩu'), { target: { value: 'admin' } });
    fireEvent.click(modal.getByRole('button', { name: /^Đăng nhập$/ }));

    expect(await screen.findByTestId(`case-row-${CASE_ID}`)).toHaveClass('casewb__row--focused');
    expect(exact).toHaveBeenCalledWith(CASE_ID);
    expect(window.location.pathname + window.location.search).toBe(DEEP_LINK);
  });

  it.each([
    { username: 'c001', role: 'customer', owner_id: 'C001' },
    { username: 'user', role: 'user', owner_id: null },
  ] satisfies AuthUser[])('$role never mounts Tower or fetches case resources', async (user) => {
    setLocation(DEEP_LINK);
    vi.spyOn(conversationApi, 'me').mockResolvedValue({ user });
    const list = vi.spyOn(conversationApi, 'listCases').mockResolvedValue([]);
    const exact = vi.spyOn(conversationApi, 'getCase').mockResolvedValue(focusedCase);

    render(<App />);

    await screen.findByRole('button', { name: /Phiên xử lý/i });
    expect(screen.queryByRole('button', { name: '← Workspace' })).not.toBeInTheDocument();
    expect(list).not.toHaveBeenCalled();
    expect(exact).not.toHaveBeenCalled();
  });

  it.each([
    '/?tab=cases&case=not-a-uuid',
    `/?tab=case&case=${CASE_ID}`,
    `/?tab=cases&case=${CASE_ID}&case=${OTHER_ID}`,
    `/?tab=cases&case=${CASE_ID}&extra=1`,
    `/?tab=cases&case=${CASE_ID}#detail`,
  ])('malformed/non-exact URL %s stays in Workspace with zero exact fetch', async (path) => {
    setLocation(path);
    vi.spyOn(conversationApi, 'me').mockResolvedValue({
      user: { username: 'admin', role: 'admin', owner_id: null },
    });
    const exact = vi.spyOn(conversationApi, 'getCase').mockResolvedValue(focusedCase);

    render(<App />);

    await screen.findByTestId('open-tower');
    expect(screen.queryByRole('button', { name: '← Workspace' })).not.toBeInTheDocument();
    expect(exact).not.toHaveBeenCalled();
  });
});
