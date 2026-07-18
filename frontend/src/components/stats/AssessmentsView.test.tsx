// AssessmentsView.test.tsx — tab Hồ sơ + lý do AI (T13-3): list + panel criteria 3 trụ + basis + defensive.
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AssessmentsView } from './AssessmentsView';
import { conversationApi } from '../../api';
import type { Assessment } from '../../types';

const rows: Assessment[] = [
  {
    id: 'a1', owner_id: 'C001', loan_type: 'Thế chấp', loan_amount_vnd: 5_000_000_000, lane: 'green',
    basis: 'lane_policy: green — DSCR ≥ 1.2.', created_at: '2026-07-19T09:12:00',
    criteria: [
      { key: 'DSCR', level: 'pass', detail: 'DSCR 1.501 ≥ 1.2.' },
      { key: 'LTV', level: 'pass', detail: 'LTV 62%.' },
      { key: 'CIC', level: 'pass', detail: 'Nhóm 1.' },
    ],
  },
  {
    id: 'a2', owner_id: 'DN2024001', loan_type: 'Thế chấp DN', loan_amount_vnd: 12_000_000_000, lane: 'red',
    basis: 'lane_policy: red — DSCR < 1.0.', created_at: '2026-07-19T07:55:00',
    criteria: [{ key: 'DSCR', level: 'red', detail: 'DSCR 0.62 < 1.0.' }],
  },
];

beforeEach(() => vi.restoreAllMocks());

describe('AssessmentsView (T13-3)', () => {
  it('list hồ sơ + lane chip + chọn sẵn hồ sơ đầu → panel criteria 3 trụ', async () => {
    vi.spyOn(conversationApi, 'listAssessments').mockResolvedValue(rows);
    render(<AssessmentsView />);
    await waitFor(() => expect(screen.getByTestId('asmt-row-a1')).toBeInTheDocument());
    expect(screen.getByTestId('asmt-row-a2')).toBeInTheDocument();
    // panel hồ sơ đầu (a1 green) chọn sẵn → 3 tiêu chí
    const detail = screen.getByTestId('asmt-detail');
    expect(within(detail).getByText('DSCR')).toBeInTheDocument();
    expect(within(detail).getByText('LTV')).toBeInTheDocument();
    expect(within(detail).getByText('CIC')).toBeInTheDocument();
    expect(within(detail).getByText(/GREEN/)).toBeInTheDocument();
  });

  it('click hồ sơ khác → panel đổi (a2 red, criteria + basis lý do AI)', async () => {
    vi.spyOn(conversationApi, 'listAssessments').mockResolvedValue(rows);
    render(<AssessmentsView />);
    await waitFor(() => expect(screen.getByTestId('asmt-row-a2')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('asmt-row-a2'));
    const detail = screen.getByTestId('asmt-detail');
    expect(within(detail).getByText(/RED/)).toBeInTheDocument();
    expect(within(detail).getByText(/DSCR 0.62/)).toBeInTheDocument();
    // DF-B-02: basis = policy snapshot (nhãn "Chính sách áp dụng") + chú thích dẫn về 3 trụ
    expect(within(detail).getByText(/Chính sách áp dụng/)).toBeInTheDocument();
    expect(within(detail).getByText(/Lý do riêng của hồ sơ nằm ở tiêu chí 3 trụ/)).toBeInTheDocument();
    expect(within(detail).getByText(/DSCR < 1.0/)).toBeInTheDocument();
  });

  it('criteria level → mark đúng (pass ✓ / red ✗)', async () => {
    vi.spyOn(conversationApi, 'listAssessments').mockResolvedValue([rows[1]]); // chỉ red
    render(<AssessmentsView />);
    await waitFor(() => expect(screen.getByTestId('asmt-detail')).toBeInTheDocument());
    // criterion DSCR level red → class crit--red
    const crit = screen.getByText('DSCR').closest('.asmt__crit');
    expect(crit).toHaveClass('asmt__crit--red');
  });

  it('defensive: criteria rỗng → "không có chi tiết", không crash', async () => {
    vi.spyOn(conversationApi, 'listAssessments').mockResolvedValue([
      { id: 'x', owner_id: 'C9', lane: 'yellow', criteria: [], basis: 'x' },
    ]);
    render(<AssessmentsView />);
    await waitFor(() => expect(screen.getByText(/Không có chi tiết tiêu chí/)).toBeInTheDocument());
  });

  // DF-B-02 (gộp): criteria key tiếng Anh → nhãn Việt; DSCR/LTV (không map) pass-through; CIC giữ.
  it('DF-B-02: criteria key EN → nhãn Việt (identity→Định danh), key lạ pass-through', async () => {
    vi.spyOn(conversationApi, 'listAssessments').mockResolvedValue([
      {
        id: 'a9', owner_id: 'C009', lane: 'yellow', basis: 'x',
        criteria: [
          { key: 'identity', level: 'pass', detail: 'CMND khớp.' },
          { key: 'criminal', level: 'pass', detail: 'Không tiền án.' },
          { key: 'cic', level: 'yellow', detail: 'Nhóm 2.' },
          { key: 'DSCR', level: 'pass', detail: '1.4.' }, // không map → giữ nguyên
        ],
      },
    ]);
    render(<AssessmentsView />);
    await waitFor(() => expect(screen.getByTestId('asmt-detail')).toBeInTheDocument());
    const detail = screen.getByTestId('asmt-detail');
    expect(within(detail).getByText('Định danh')).toBeInTheDocument();
    expect(within(detail).getByText('Án tích')).toBeInTheDocument();
    expect(within(detail).getByText('CIC')).toBeInTheDocument(); // tên riêng giữ
    expect(within(detail).getByText('DSCR')).toBeInTheDocument(); // pass-through
    // nhãn EN gốc "identity"/"criminal" KHÔNG còn hiện
    expect(within(detail).queryByText('identity')).not.toBeInTheDocument();
    expect(within(detail).queryByText('criminal')).not.toBeInTheDocument();
  });

  it('rỗng list → "chưa có hồ sơ"', async () => {
    vi.spyOn(conversationApi, 'listAssessments').mockResolvedValue([]);
    render(<AssessmentsView />);
    await waitFor(() => expect(screen.getByText(/Chưa có hồ sơ/)).toBeInTheDocument());
  });
});
