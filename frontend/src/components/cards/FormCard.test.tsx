// FormCard.test.tsx — form intake khách (D-57 T9-3): render theo fields, submit, trạng thái submitted,
// validate thiếu field, defensive fields rỗng.
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FormCard } from './FormCard';
import { CardRenderer } from './CardRenderer';
import type { Card } from '../../types';

function formCard(over: Partial<Card> = {}): Card {
  return {
    id: 'card_f1', conv_id: 'c1', task_id: null, type: 'form', ts: '',
    title: 'Hồ sơ vay', status: 'pending',
    fields: [
      { name: 'full_name', label: 'Họ và tên', type: 'text', required: true },
      { name: 'monthly_income', label: 'Thu nhập (VND)', type: 'number', required: true },
      { name: 'note', label: 'Ghi chú', type: 'text', required: false },
    ],
    ...over,
  };
}

describe('FormCard', () => {
  it('render input theo fields (số → type number) + nút Nộp', () => {
    render(<FormCard card={formCard()} onSubmit={vi.fn()} />);
    expect(screen.getByLabelText('Họ và tên')).toHaveAttribute('type', 'text');
    expect(screen.getByLabelText('Thu nhập (VND)')).toHaveAttribute('type', 'number');
    expect(screen.getByLabelText('Ghi chú')).toBeInTheDocument();
    expect(screen.getByTestId('form-submit')).toBeInTheDocument();
  });

  it('thiếu field bắt buộc → không gọi onSubmit, hiện lỗi + highlight', () => {
    const onSubmit = vi.fn();
    render(<FormCard card={formCard()} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByTestId('form-submit'));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(/điền đủ/i);
  });

  it('điền đủ → onSubmit(cardId, values)', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<FormCard card={formCard()} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText('Họ và tên'), { target: { value: 'Nguyễn Văn A' } });
    fireEvent.change(screen.getByLabelText('Thu nhập (VND)'), { target: { value: '15000000' } });
    fireEvent.click(screen.getByTestId('form-submit'));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith('card_f1', { full_name: 'Nguyễn Văn A', monthly_income: '15000000' }));
  });

  it('lỗi submit từ server (body 4-field) → hiện message', async () => {
    // client-validate pass (đủ field số hợp lệ) → gọi onSubmit → server reject → hiện message.
    const onSubmit = vi.fn().mockRejectedValue(new Error('Hồ sơ đã được nộp.'));
    render(<FormCard card={formCard()} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText('Họ và tên'), { target: { value: 'A' } });
    fireEvent.change(screen.getByLabelText('Thu nhập (VND)'), { target: { value: '15000000' } });
    fireEvent.click(screen.getByTestId('form-submit'));
    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Hồ sơ đã được nộp.'));
  });

  it('status=submitted → read-only "đã nộp", KHÔNG input/nút', () => {
    render(<FormCard card={formCard({ status: 'submitted' })} onSubmit={vi.fn()} />);
    expect(screen.getByTestId('form-submitted')).toHaveTextContent(/Đã nộp/);
    expect(screen.queryByTestId('form-submit')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Họ và tên')).not.toBeInTheDocument();
  });

  it('fields rỗng/thiếu → fallback "không hợp lệ", không crash (defensive)', () => {
    render(<FormCard card={formCard({ fields: [] })} onSubmit={vi.fn()} />);
    expect(screen.getByTestId('form-invalid')).toBeInTheDocument();
  });

  it('CardRenderer type=form → render FormCard (WIDE)', () => {
    render(<CardRenderer card={formCard()} onFormSubmit={vi.fn()} />);
    expect(screen.getByTestId('card-form')).toBeInTheDocument();
    expect(screen.getByTestId('form-card')).toBeInTheDocument();
  });
});
