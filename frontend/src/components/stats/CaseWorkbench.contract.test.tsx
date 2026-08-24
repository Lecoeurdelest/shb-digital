import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { conversationApi } from '../../api';
import type { CaseSummary } from '../../types';
import { CaseWorkbench } from './CaseWorkbench';

const missingCase: CaseSummary = {
  id: 'case-missing', source_system: 'los', external_case_id: 'LOS-SME-2026-001',
  internal_application_id: 'APP-001', party_reference: 'CIF-01928', product_code: 'SME_SECURED',
  loan_amount_vnd: 3_500_000_000, case_status: 'missing_information',
  next_action: 'Bổ sung báo cáo tài chính năm 2025.', document_count: 4,
  missing_fields: ['financial_statements_2025', 'collateral_valuation', 'core_raw_document_ref'], source_version: 12,
  data_as_of: '2026-08-24T09:30:00+07:00', synced_at: '2026-08-24T09:31:12+07:00',
  conversation_id: null, assessment: { lane: 'yellow', created_at: '2026-08-24T09:31:00+07:00' },
};

const readyCase: CaseSummary = {
  ...missingCase,
  id: 'case-ready', source_system: 'saha', external_case_id: 'SAHA-RL-002',
  internal_application_id: null, product_code: 'RETAIL_MORTGAGE', loan_amount_vnd: 1_800_000_000,
  case_status: 'ready_for_preassessment', next_action: 'Phân công cán bộ thực hiện sơ thẩm.',
  missing_fields: [], conversation_id: 'conv-shadow-linked-002', assessment: { lane: null, created_at: null },
};

beforeEach(() => vi.restoreAllMocks());

describe('CaseWorkbench contract coverage', () => {
  it('first viewport hiển thị blocker bằng nhãn nghiệp vụ và đúng một việc tiếp theo', async () => {
    vi.spyOn(conversationApi, 'listCases').mockResolvedValue([missingCase]);
    render(<CaseWorkbench onOpenCaseConversation={vi.fn()} />);

    const detail = await screen.findByTestId('case-detail');
    expect(within(detail).getByText('LOS-SME-2026-001')).toBeInTheDocument();
    expect(within(detail).getByText('Thiếu thông tin')).toBeInTheDocument();
    expect(within(detail).getByText('SME có tài sản bảo đảm')).toBeInTheDocument();
    expect(within(detail).getByText('3.500.000.000 ₫')).toBeInTheDocument();
    expect(within(detail).getByText('24/08/2026 09:30')).toBeInTheDocument();
    expect(within(detail).getByText('Báo cáo tài chính năm 2025')).toBeInTheDocument();
    expect(within(detail).getByText('Kết quả định giá tài sản')).toBeInTheDocument();
    expect(within(detail).getByText('Thông tin bổ sung từ nguồn')).toBeInTheDocument();
    expect(within(detail).queryByText(/core_raw_document_ref/i)).not.toBeInTheDocument();
    expect(within(detail).getAllByText('Việc tiếp theo')).toHaveLength(1);
    expect(within(within(detail).getByLabelText('Việc tiếp theo')).getByText(missingCase.next_action)).toBeInTheDocument();
    expect(within(detail).queryByRole('button', { name: 'Mở phiên xử lý' })).not.toBeInTheDocument();
  });

  it('chỉ mở đúng phiên đã liên kết và không hiện raw conversation id', async () => {
    const onOpen = vi.fn();
    vi.spyOn(conversationApi, 'listCases').mockResolvedValue([readyCase]);
    render(<CaseWorkbench onOpenCaseConversation={onOpen} />);

    const openButton = await screen.findByRole('button', { name: 'Mở phiên xử lý' });
    expect(document.body).not.toHaveTextContent(readyCase.conversation_id!);
    fireEvent.click(openButton);
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onOpen).toHaveBeenCalledWith(readyCase.conversation_id);
  });

  it.each([
    ['green', 'Cơ sở sơ bộ: Có thể tiếp tục các bước kiểm tra'],
    ['yellow', 'Cơ sở sơ bộ: Cần bổ sung hoặc rà soát'],
    ['red', 'Cơ sở sơ bộ: Cần chuyên gia xem xét'],
  ] as const)('lane %s chỉ là wording cơ sở sơ bộ', async (lane, expectedLabel) => {
    vi.spyOn(conversationApi, 'listCases').mockResolvedValue([
      { ...missingCase, assessment: { lane, created_at: missingCase.assessment.created_at } },
    ]);
    render(<CaseWorkbench />);

    const detail = await screen.findByTestId('case-detail');
    expect(within(detail).getByText(expectedLabel)).toBeInTheDocument();
    expect(within(detail).queryByText(new RegExp(`^${lane}$`, 'i'))).not.toBeInTheDocument();
    expect(within(detail).queryByText(/đạt|từ chối|quyết định cuối/i)).not.toBeInTheDocument();
  });

  it('lọc gọi đúng status/source/limit và dùng filter-empty riêng', async () => {
    const listCases = vi.spyOn(conversationApi, 'listCases')
      .mockResolvedValueOnce([missingCase])
      .mockResolvedValueOnce([]);
    render(<CaseWorkbench />);
    await screen.findByTestId('case-detail');

    fireEvent.change(screen.getByLabelText('Lọc theo trạng thái hồ sơ'), { target: { value: 'needs_specialist' } });
    fireEvent.change(screen.getByLabelText('Lọc theo nguồn hồ sơ'), { target: { value: ' los ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Áp dụng' }));

    await screen.findByText('Không có hồ sơ phù hợp bộ lọc');
    expect(listCases).toHaveBeenLastCalledWith({ status: 'needs_specialist', source: 'los', limit: 50 });
    expect(screen.queryByText('Chưa có hồ sơ nghiệp vụ')).not.toBeInTheDocument();
  });

  it('phân biệt nguồn được lọc chưa có case với toàn hệ chưa có case', async () => {
    const listCases = vi.spyOn(conversationApi, 'listCases')
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([]);
    render(<CaseWorkbench />);
    await screen.findByText('Chưa có hồ sơ nghiệp vụ');

    fireEvent.change(screen.getByLabelText('Lọc theo nguồn hồ sơ'), { target: { value: 'los' } });
    fireEvent.click(screen.getByRole('button', { name: 'Áp dụng' }));
    await screen.findByText('LOS chưa có hồ sơ');
    expect(screen.getByText('Chưa có hồ sơ nào được đồng bộ từ nguồn này.')).toBeInTheDocument();
    expect(listCases).toHaveBeenLastCalledWith({ source: 'los', limit: 50 });
  });

  it('response cũ không ghi đè kết quả của lần tải mới hơn', async () => {
    let resolveFiltered!: (rows: CaseSummary[]) => void;
    const filtered = new Promise<CaseSummary[]>((resolve) => { resolveFiltered = resolve; });
    const listCases = vi.spyOn(conversationApi, 'listCases')
      .mockResolvedValueOnce([missingCase])
      .mockReturnValueOnce(filtered)
      .mockResolvedValueOnce([readyCase]);
    render(<CaseWorkbench />);
    await screen.findByTestId('case-row-case-missing');

    fireEvent.change(screen.getByLabelText('Lọc theo trạng thái hồ sơ'), { target: { value: 'missing_information' } });
    fireEvent.click(screen.getByRole('button', { name: 'Áp dụng' }));
    await waitFor(() => expect(listCases).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole('button', { name: 'Xóa lọc' }));
    expect(await screen.findByTestId('case-row-case-ready')).toBeInTheDocument();

    resolveFiltered([missingCase]);
    await waitFor(() => expect(screen.queryByTestId('case-row-case-missing')).not.toBeInTheDocument());
    expect(screen.getByTestId('case-row-case-ready')).toBeInTheDocument();
  });
});
