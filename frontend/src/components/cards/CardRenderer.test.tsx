// CardRenderer.test.tsx — 7 card type render + citation chip + defensive N3
// (value mixed, pass nullable, field thiếu, type lạ default branch).
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { CardRenderer } from './CardRenderer';
import type { Card } from '../../types';

function card(type: string, extra: Partial<Card> = {}): Card {
  return { id: 'c1', conv_id: 'x', task_id: 't1', type, ts: '2026-01-01', ...extra };
}

describe('CardRenderer — 7 type', () => {
  it('metric: value MIXED (number+string), pass NULLABLE, source→chip', () => {
    const c = card('metric', {
      title: 'Chỉ số', items: [
        { name: 'DSCR', value: 3.709, threshold: '>= 1.2', pass: true, source: 'credit_assess' },
        { name: 'Tổng nợ', value: '300,000,000 VND', threshold: 'N/A', pass: null, source: 'cust_get' },
      ],
    });
    render(<CardRenderer card={c} />);
    expect(screen.getByText('3.709')).toBeInTheDocument();           // number render
    expect(screen.getByText('300,000,000 VND')).toBeInTheDocument(); // string render (không .toFixed vỡ)
    expect(screen.getByText(/✓ Đạt/)).toBeInTheDocument();           // pass=true badge
    // pass=null → KHÔNG badge cho dòng Tổng nợ (chỉ 1 badge Đạt tồn tại)
    expect(screen.queryAllByText(/Đạt|Không đạt/).length).toBe(1);
    expect(screen.getByTestId('cite-credit_assess')).toBeInTheDocument();
  });

  it('checklist: status ok/missing/risk render mark', () => {
    const c = card('checklist', { items: [
      { item: 'Giấy tờ đủ', status: 'ok' },
      { item: 'Thiếu sao kê', status: 'missing', note: 'cần bổ sung' },
    ] });
    render(<CardRenderer card={c} />);
    expect(screen.getByText('Giấy tờ đủ')).toBeInTheDocument();
    expect(screen.getByText('Thiếu sao kê')).toBeInTheDocument();
    expect(screen.getByText('cần bổ sung')).toBeInTheDocument();
  });

  it('options: recommended đóng khung', () => {
    const c = card('options', { recommended: 'Gói A', items: [
      { name: 'Gói A', rate: '9%', tenor: '24 tháng' },
      { name: 'Gói B', rate: '11%' },
    ] });
    render(<CardRenderer card={c} />);
    expect(screen.getByText('Gói A')).toBeInTheDocument();
    expect(screen.getByText('9%')).toBeInTheDocument();
  });

  it('timeline: steps + total_days', () => {
    const c = card('timeline', { total_days: 5, items: [
      { step: 'Thẩm định', owner: 'Credit', eta: '2 ngày' },
      { step: 'Giải ngân', owner: 'Ops' },
    ] });
    render(<CardRenderer card={c} />);
    expect(screen.getByText('Thẩm định')).toBeInTheDocument();
    expect(screen.getByText(/Tổng: 5 ngày/)).toBeInTheDocument();
  });

  it('case_file: items + flags', () => {
    const c = card('case_file', { items: [{ label: 'Khách', value: 'DN X' }], flags: ['Nợ xấu'] });
    render(<CardRenderer card={c} />);
    expect(screen.getByText('DN X')).toBeInTheDocument();
    expect(screen.getByText(/Nợ xấu/)).toBeInTheDocument();
  });

  it('document: sections + sources chip', () => {
    const c = card('document', { items: [{ section: 'Kết luận', content: 'Đồng ý' }], sources: ['credit_assess'] });
    render(<CardRenderer card={c} />);
    expect(screen.getByText('Kết luận')).toBeInTheDocument();
    expect(screen.getByTestId('cite-credit_assess')).toBeInTheDocument();
  });

  it('approval: render ApprovalPanel (T3-3 — chi tiết ở ApprovalPanel.test)', () => {
    render(<CardRenderer card={card('approval', { approval_id: 'a1', status: 'pending', items: [] })} onDecide={() => {}} />);
    expect(screen.getByTestId('card-approval')).toBeInTheDocument();
  });
});

describe('CardRenderer — defensive N3', () => {
  it('type LẠ → default branch render thô, KHÔNG crash', () => {
    const c = card('risk_matrix_v9', { items: [{ foo: 'bar' }] });
    render(<CardRenderer card={c} />);
    expect(screen.getByTestId('card-risk_matrix_v9')).toBeInTheDocument();
    expect(screen.getByText(/foo/)).toBeInTheDocument(); // JSON thô
  });

  it('card thiếu items → render title + empty, không crash', () => {
    render(<CardRenderer card={card('metric', { title: 'Trống' })} />);
    expect(screen.getByText('Trống')).toBeInTheDocument();
    expect(screen.getByText(/chưa có nội dung/)).toBeInTheDocument();
  });

  it('metric thiếu field trong item → render fallback, không crash', () => {
    const c = card('metric', { items: [{ name: 'X' }] }); // thiếu value/pass/source
    render(<CardRenderer card={c} />);
    expect(screen.getByText('X')).toBeInTheDocument();
    expect(screen.queryByText(/Đạt/)).not.toBeInTheDocument(); // pass thiếu → không badge
  });

  it('citation chip bấm → onCite được gọi với (taskId, source)', () => {
    const onCite = vi.fn();
    const c = card('metric', { items: [{ name: 'DSCR', value: 1, source: 'tool_x' }] });
    render(<CardRenderer card={c} onCite={onCite} />);
    fireEvent.click(screen.getByTestId('cite-tool_x'));
    expect(onCite).toHaveBeenCalledWith('t1', 'tool_x');
  });
});
