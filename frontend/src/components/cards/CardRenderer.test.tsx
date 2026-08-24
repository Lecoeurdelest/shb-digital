// CardRenderer.test.tsx — card nghiệp vụ + ranh giới không lộ raw type/source/payload D-75.
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
    expect(screen.getByTestId('cite-credit_assess')).toHaveTextContent('Tín dụng');
    expect(screen.getByTestId('cite-cust_get')).toHaveTextContent('Dữ liệu khách hàng');
    expect(screen.queryByText('credit_assess')).not.toBeInTheDocument();
    expect(screen.queryByText('cust_get')).not.toBeInTheDocument();
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
    expect(screen.getByTestId('cite-credit_assess')).toHaveTextContent('Tín dụng');
  });

  it('approval: render ApprovalPanel (T3-3 — chi tiết ở ApprovalPanel.test)', () => {
    render(<CardRenderer card={card('approval', { approval_id: 'a1', status: 'pending', items: [] })} onDecide={() => {}} />);
    expect(screen.getByTestId('card-approval')).toBeInTheDocument();
  });
});

describe('CardRenderer — defensive N3', () => {
  it('type LẠ → fail-safe, không render raw type/title/payload/JSON', () => {
    const c = card('raw_tool_payload', {
      title: 'raw tool details',
      items: [{ provider: 'secret-provider', nested: { token: 123 }, foo: 'bar' }],
    });
    const { container } = render(<CardRenderer card={c} />);
    expect(screen.getByTestId('card-raw_tool_payload')).toBeInTheDocument();
    expect(screen.getByText('Nội dung chưa hỗ trợ')).toBeInTheDocument();
    expect(screen.getByText(/mở nội dung này trên hệ thống ngân hàng/i)).toBeInTheDocument();
    expect(screen.queryByText(/raw_tool_payload|raw tool details|secret-provider|token|foo|bar/i)).not.toBeInTheDocument();
    expect(container.querySelector('pre')).not.toBeInTheDocument();
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

  it('type đã biết có value lồng nhau → fallback an toàn, không stringify payload', () => {
    const c = card('metric', {
      title: 'Chỉ số an toàn',
      items: [{ name: 'Kết quả', value: { provider: 'secret-provider', token: 123, tool: 'internal_tool' } }],
    });
    const { container } = render(<CardRenderer card={c} />);
    expect(screen.getAllByText('Kết quả').length).toBeGreaterThan(0);
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.queryByText(/secret-provider|token|internal_tool|provider/i)).not.toBeInTheDocument();
    expect(container.querySelector('pre')).not.toBeInTheDocument();
  });

  it('citation chip bấm → onCite được gọi với (taskId, source)', () => {
    const onCite = vi.fn();
    const c = card('metric', { items: [{ name: 'DSCR', value: 1, source: 'tool_x' }] });
    render(<CardRenderer card={c} onCite={onCite} />);
    fireEvent.click(screen.getByTestId('cite-tool_x'));
    expect(onCite).toHaveBeenCalledWith('t1', 'tool_x');
    expect(screen.getByTestId('cite-tool_x')).toHaveTextContent('Nguồn nghiệp vụ');
    expect(screen.getByTestId('cite-tool_x')).toHaveAttribute('title', 'Nguồn nghiệp vụ: Nguồn nghiệp vụ');
    expect(screen.queryByText('tool_x')).not.toBeInTheDocument();
  });

  // DF-A-05-FE (spec mới, evidence prod): render tolerant shape tự do {name,detail,status,assignee}.
  it('DF-A-05: shape chuẩn {step,owner,eta} → hiện step + meta (không regression card C019)', () => {
    const c = card('timeline', { items: [{ step: 'Thẩm định tín dụng', owner: 'Tín dụng', eta: '2 ngày' }] });
    render(<CardRenderer card={c} />);
    expect(screen.getByText('Thẩm định tín dụng')).toBeInTheDocument();
    expect(screen.getByText('Tín dụng')).toBeInTheDocument();
    expect(screen.getByText('2 ngày')).toBeInTheDocument();
  });

  it('DF-A-05: shape PROD {name,detail,status,assignee} → title + mô tả detail + meta chips (KHÔNG trống)', () => {
    const c = card('timeline', { items: [
      { name: 'Bước 1', detail: 'Thu thập CCCD/CMTND bản gốc (bắt buộc)', status: 'pending', assignee: 'Điều phối viên/Khách hàng' },
    ] });
    render(<CardRenderer card={c} />);
    expect(screen.getByText('Bước 1')).toBeInTheDocument();
    expect(screen.getByText(/Thu thập CCCD\/CMTND bản gốc/)).toBeInTheDocument(); // detail KHÔNG bị vứt
    expect(screen.getByText('pending')).toBeInTheDocument(); // status chip
    expect(screen.getByText('Điều phối viên/Khách hàng')).toBeInTheDocument(); // assignee chip
  });

  it('DF-A-05/D-75: item chỉ detail làm title; field lạ không được đưa lên bề mặt', () => {
    const c = card('timeline', {
      items: [{ detail: 'Xác nhận cư trú', foo: 'công an', provider: 'secret', token: 99, tool: 'credit_assess' }],
    });
    render(<CardRenderer card={c} />);
    expect(screen.getByText('Xác nhận cư trú')).toBeInTheDocument();
    expect(screen.queryByText(/công an|secret|99|credit_assess|provider|token|tool/i)).not.toBeInTheDocument();
  });

  it('DF-A-05: item RỖNG hẳn → "(chưa có mô tả)", không trống', () => {
    const c = card('timeline', { items: [{}] });
    render(<CardRenderer card={c} />);
    expect(screen.getByText('(chưa có mô tả)')).toBeInTheDocument();
  });

  // DF-A-06: metric header cột (Thực tế/Ngưỡng) + label-map dịch thuật ngữ.
  it('DF-A-06: metric có threshold → header cột Thực tế + Ngưỡng phân tách', () => {
    const c = card('metric', { items: [{ name: 'DSCR', value: '1.5', threshold: '≥ 1.2', pass: true }] });
    render(<CardRenderer card={c} />);
    expect(screen.getByText('Thực tế')).toBeInTheDocument();
    expect(screen.getByText('Ngưỡng')).toBeInTheDocument();
  });

  it('DF-A-06: label-map dịch thuật ngữ trong ngoặc (Identity→Định danh); tên lạ pass-through', () => {
    const c = card('metric', { items: [
      { name: 'Nhân thân (Identity)', value: 'YELLOW', pass: false },
      { name: 'Chỉ số lạ XYZ', value: '1', pass: true },
    ] });
    render(<CardRenderer card={c} />);
    expect(screen.getByText('Nhân thân (Định danh)')).toBeInTheDocument(); // dịch
    expect(screen.getByText('Chỉ số lạ XYZ')).toBeInTheDocument(); // giữ nguyên
  });

  it('gated approval shape thật → nhãn nghiệp vụ, không lộ action/identifier kỹ thuật', () => {
    const c = card('approval', {
      title: 'Duyệt: disburse (loan_id=L001, loan_amount_vnd=500000000)',
      action: 'disburse', approval_id: 'appr-1', status: 'pending',
      items: [
        { label: 'loan_id', value: 'L001' },
        { label: 'loan_amount_vnd', value: 500_000_000 },
      ],
    });
    const { container } = render(<CardRenderer card={c} canDecide={false} />);

    expect(screen.getByText('Phê duyệt giải ngân')).toBeInTheDocument();
    expect(screen.getByText('Giải ngân')).toBeInTheDocument();
    expect(screen.getByText('Khoản vay')).toBeInTheDocument();
    expect(screen.getByText('Số tiền')).toBeInTheDocument();
    expect(screen.getByTestId('approval-waiting')).toBeInTheDocument();
    expect(container).not.toHaveTextContent(/disburse|loan_id|loan_amount_vnd|\{"|auto-rule|tool/i);
  });

  it('gated auto document shape thật → receipt generic, title và nguồn không lộ kỹ thuật', () => {
    const c = card('document', {
      title: '✅ Tự động duyệt & thực thi: disburse (loan_id=L001, loan_amount_vnd=500000000)',
      items: [
        { section: 'Cơ chế', content: 'auto-rule nhận lệnh từ internal_tool' },
        {
          section: 'Kết quả',
          content: '{"disbursed":true,"loan_id":"L001","loan_amount_vnd":500000000,"approved_by":"auto-rule","tool":"ops_disburse"}',
        },
      ],
      sources: ['phanh phân tầng — auto-rule'],
    });
    const { container } = render(<CardRenderer card={c} />);

    expect(screen.getByText('Kết quả thực hiện')).toBeInTheDocument();
    expect(screen.getByText('Đã thực hiện; biên nhận lưu trong nhật ký.')).toBeInTheDocument();
    expect(screen.getByTestId('cite-phanh phân tầng — auto-rule')).toHaveTextContent('Nguồn nghiệp vụ');
    expect(container).not.toHaveTextContent(/disburse|loan_id|loan_amount_vnd|\{"|auto-rule|tool/i);
  });

  it('hiện as-of deterministic khi ts hợp lệ; bỏ qua ts thiếu hoặc invalid', () => {
    const { rerender } = render(<CardRenderer card={card('checklist', {
      ts: '2026-08-24T09:30:45Z', items: [{ item: 'Đã đối chiếu', status: 'ok' }],
    })} />);
    const timestamp = screen.getByText('Cập nhật 2026-08-24 09:30');
    expect(timestamp).toHaveAttribute('datetime', '2026-08-24T09:30:45Z');

    rerender(<CardRenderer card={card('checklist', {
      ts: 'không-hợp-lệ', items: [{ item: 'Đã đối chiếu', status: 'ok' }],
    })} />);
    expect(screen.queryByText(/Cập nhật/)).not.toBeInTheDocument();
  });
});
