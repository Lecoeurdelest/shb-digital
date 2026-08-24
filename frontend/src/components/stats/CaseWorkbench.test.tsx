import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { conversationApi } from '../../api';
import { ApiRequestError } from '../../api/client';
import type { CaseSummary } from '../../types';
import { CaseWorkbench } from './CaseWorkbench';

const row: CaseSummary = {
  id: 'case-1',
  source_system: 'los',
  external_case_id: 'LOS-001',
  internal_application_id: null,
  party_reference: 'CIF-009',
  product_code: 'SME_SECURED',
  loan_amount_vnd: 500_000_000,
  case_status: 'ready_for_preassessment',
  next_action: 'Bắt đầu sơ thẩm',
  document_count: 2,
  missing_fields: [],
  source_version: 3,
  data_as_of: '2026-08-24T10:00:00Z',
  synced_at: '2026-08-24T10:01:00Z',
  conversation_id: null,
  assessment: { lane: null, created_at: null },
};

beforeEach(() => vi.restoreAllMocks());

describe('CaseWorkbench D-77', () => {
  it('shows source/as-of/next action without approval, disbursement, or raw payload controls', async () => {
    vi.spyOn(conversationApi, 'listCases').mockResolvedValue([row]);
    render(<CaseWorkbench />);

    const detail = await screen.findByTestId('case-detail');
    expect(within(detail).getByText('LOS-001')).toBeInTheDocument();
    expect(within(detail).getByText('24/08/2026 10:00')).toBeInTheDocument();
    expect(within(detail).getByText('Bắt đầu sơ thẩm')).toBeInTheDocument();
    expect(within(detail).getByText(/không phải quyết định tín dụng hoặc phê duyệt/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /duyệt|giải ngân|từ chối/i })).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/document_refs|raw payload|conversation_id/i);
  });

  it('distinguishes a successful empty source from a disconnected source', async () => {
    const list = vi.spyOn(conversationApi, 'listCases').mockResolvedValue([]);
    render(<CaseWorkbench />);
    await screen.findByText('Chưa có hồ sơ nghiệp vụ');
    expect(screen.queryByText(/chưa được kết nối hoặc đang tắt/i)).not.toBeInTheDocument();

    list.mockRejectedValueOnce(new ApiRequestError(403, {
      code: 'source_disabled',
      message: 'Nguồn tắt.',
      hint: 'Kiểm tra cấu hình.',
      retryable: false,
    }, 'source disabled'));
    fireEvent.click(screen.getByRole('button', { name: 'Áp dụng' }));
    await waitFor(() => expect(screen.getByText(/chưa được kết nối hoặc đang tắt/i)).toBeInTheDocument());
  });
});
