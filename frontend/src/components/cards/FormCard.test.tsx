// FormCard.test.tsx — form intake khách (D-57 T9-3): render theo fields, submit, trạng thái submitted,
// validate thiếu field, defensive fields rỗng.
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FormCard } from './FormCard';
import { CardRenderer } from './CardRenderer';
import { ApiRequestError } from '../../api/client';
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
    consent: {
      required: true,
      purpose: 'pre_pilot_shadow_preassessment',
      wording_version: 'v1',
      wording_checksum: 'a'.repeat(64),
      content_markdown: '**Mục đích:** sơ thẩm shadow pre-pilot. Dữ liệu được xử lý theo nội dung này.',
    },
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
    expect(screen.getByTestId('form-submit')).toBeDisabled();
    expect(screen.getByText('Phiên bản v1', { exact: false })).toBeInTheDocument();
  });

  it('thiếu field bắt buộc → không gọi onSubmit, hiện lỗi + highlight', () => {
    const onSubmit = vi.fn();
    render(<FormCard card={formCard()} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByTestId('form-submit'));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(/điền đủ/i);
  });

  it('điền đủ → onSubmit(cardId, values)', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<FormCard card={formCard()} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText('Họ và tên'), { target: { value: 'Nguyễn Văn A' } });
    fireEvent.change(screen.getByLabelText('Thu nhập (VND)'), { target: { value: '15000000' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByTestId('form-submit'));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(
      'card_f1',
      { full_name: 'Nguyễn Văn A', monthly_income: '15000000' },
      true,
    ));
  });

  it('lỗi submit từ server (body 4-field) → hiện message', async () => {
    // client-validate pass (đủ field số hợp lệ) → gọi onSubmit → server reject → hiện message.
    const onSubmit = vi.fn().mockRejectedValue(
      new ApiRequestError(409, {
        code: 'form_already_submitted',
        message: 'Hồ sơ đã được nộp.',
        hint: 'Tải lại phiên xử lý.',
        retryable: false,
      }, 'form_already_submitted'),
    );
    render(<FormCard card={formCard()} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText('Họ và tên'), { target: { value: 'A' } });
    fireEvent.change(screen.getByLabelText('Thu nhập (VND)'), { target: { value: '15000000' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByTestId('form-submit'));
    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Hồ sơ đã được nộp.'));
  });

  it('lỗi runtime khi submit → hiện generic, không lộ chi tiết kỹ thuật', async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error('provider model token stacktrace'));
    render(<FormCard card={formCard()} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText('Họ và tên'), { target: { value: 'A' } });
    fireEvent.change(screen.getByLabelText('Thu nhập (VND)'), { target: { value: '15000000' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByTestId('form-submit'));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Nộp hồ sơ thất bại'));
    expect(screen.queryByText(/provider|model|token|stacktrace/i)).not.toBeInTheDocument();
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

  it('consent server-owned: render markdown an toàn, checkbox mặc định false và chỉ tick mới cho nộp', () => {
    render(<FormCard card={formCard({
      consent: {
        required: true,
        purpose: 'pre_pilot_shadow_preassessment',
        wording_version: 'v2',
        wording_checksum: 'b'.repeat(64),
        content_markdown: '**Phạm vi dữ liệu**\n\n<script>alert("x")</script>',
      },
    })} onSubmit={vi.fn()} />);

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).not.toBeChecked();
    expect(screen.getByTestId('form-submit')).toBeDisabled();
    expect(screen.getByText('Phạm vi dữ liệu')).toBeInTheDocument();
    expect(document.querySelector('script')).toBeNull();
    expect(screen.getByText('Phiên bản v2', { exact: false })).toBeInTheDocument();

    fireEvent.click(checkbox);
    expect(screen.getByTestId('form-submit')).toBeEnabled();
  });

  it('consent snapshot thiếu/hỏng → fail-closed, không có checkbox và nút luôn disabled', () => {
    render(<FormCard card={formCard({ consent: undefined })} onSubmit={vi.fn()} />);
    expect(screen.getByTestId('consent-unavailable')).toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.getByTestId('form-submit')).toBeDisabled();
  });

  it('CardRenderer type=form → render FormCard (WIDE)', () => {
    render(<CardRenderer card={formCard()} onFormSubmit={vi.fn()} />);
    expect(screen.getByTestId('card-form')).toBeInTheDocument();
    expect(screen.getByTestId('form-card')).toBeInTheDocument();
  });

  // DF-A-04: managed values (draftValues + onDraftChange) — gõ → gọi onDraftChange (caller lưu, sống
  // qua đổi tab). Giá trị hiển thị THEO prop (không phải local state) → unmount/remount không mất.
  it('DF-A-04 managed: gõ field → onDraftChange(cardId, values); value hiển thị theo draftValues prop', () => {
    const onDraftChange = vi.fn();
    const { rerender } = render(
      <FormCard card={formCard()} onSubmit={vi.fn()} draftValues={{}} onDraftChange={onDraftChange} />,
    );
    fireEvent.change(screen.getByLabelText('Họ và tên'), { target: { value: 'Trần B' } });
    expect(onDraftChange).toHaveBeenCalledWith('card_f1', { full_name: 'Trần B' });
    // caller cập nhật draftValues → remount (mô phỏng đổi-tab-về) vẫn hiện giá trị (không mất)
    rerender(<FormCard card={formCard()} onSubmit={vi.fn()} draftValues={{ full_name: 'Trần B' }} onDraftChange={onDraftChange} />);
    expect((screen.getByLabelText('Họ và tên') as HTMLInputElement).value).toBe('Trần B');
  });

  it('DF-A-04 submit dùng draftValues managed → onSubmit với values từ prop', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <FormCard card={formCard()} onSubmit={onSubmit}
        draftValues={{ full_name: 'X', monthly_income: '9000000' }} onDraftChange={vi.fn()}
        consentGranted onConsentChange={vi.fn()} />,
    );
    fireEvent.click(screen.getByTestId('form-submit'));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(
      'card_f1',
      { full_name: 'X', monthly_income: '9000000' },
      true,
    ));
  });

  it('managed consent sống qua unmount/remount theo state caller', () => {
    const onConsentChange = vi.fn();
    const { rerender } = render(
      <FormCard card={formCard()} onSubmit={vi.fn()} consentGranted={false} onConsentChange={onConsentChange} />,
    );
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onConsentChange).toHaveBeenCalledWith('card_f1', true);

    rerender(<FormCard card={formCard()} onSubmit={vi.fn()} consentGranted onConsentChange={onConsentChange} />);
    expect(screen.getByRole('checkbox')).toBeChecked();
  });
});
