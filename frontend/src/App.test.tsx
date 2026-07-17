// App.test.tsx — vòng lõi chat qua mock API (VITE_USE_MOCK_API mặc định bật trong test).
// Chứng minh: tạo ca → gõ câu C001 → mock stream chat.delta + task credit → DSCR 3.709 render +
// badge task "xong". Bổ trợ Chrome verify (không thay thế — Gate 2 vẫn đòi browser).
// Test Workspace TRỰC TIẾP (auth gate ở App = test riêng App.gate.test.tsx) — inject user giả.
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Workspace } from './Workspace';
import type { AuthUser } from './types';

const USER: AuthUser = { username: 'user', role: 'user' };
const noop = vi.fn();

describe('Workspace chat — vòng lõi S1 (mock API)', () => {
  it('tạo ca → gõ câu C001 → hiển thị DSCR 3.709 + badge Tín dụng xong', async () => {
    render(<Workspace user={USER} onAuthExpired={noop} />);

    // ban đầu: empty state
    expect(screen.getByText(/Chưa mở ca nào/i)).toBeInTheDocument();

    // tạo ca mới
    fireEvent.click(screen.getByRole('button', { name: /Ca mới/i }));

    // ô nhập xuất hiện
    const input = await screen.findByLabelText('Ô nhập câu hỏi');
    fireEvent.change(input, { target: { value: 'Khách C001 xin vay 5 tỷ — DSCR bao nhiêu?' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    // user message hiện ngay (optimistic)
    expect(screen.getByText(/Khách C001 xin vay 5 tỷ/)).toBeInTheDocument();

    // chờ tới khi stream chạy XONG câu trả lời (credit_assess đứng sau DSCR trong answer —
    // chờ nó đảm bảo cả DSCR 3.709 + nguồn đều đã render). Số kèm nguồn — SPEC §6.
    await waitFor(
      () => expect(screen.getAllByText(/credit_assess/).length).toBeGreaterThan(0),
      { timeout: 5000 },
    );
    expect(screen.getAllByText(/DSCR = 3\.709/).length).toBeGreaterThan(0);

    // badge task credit chuyển "xong"
    const tasksPanel = screen.getByLabelText('Đội đang làm việc');
    await waitFor(() =>
      expect(within(tasksPanel).getByText(/Tín dụng · ✓ xong/)).toBeInTheDocument(),
    );
  });

  it('câu không liên quan tín dụng → vẫn stream trả lời, không tạo task credit', async () => {
    render(<Workspace user={USER} onAuthExpired={noop} />);
    fireEvent.click(screen.getByRole('button', { name: /Ca mới/i }));
    const input = await screen.findByLabelText('Ô nhập câu hỏi');
    fireEvent.change(input, { target: { value: 'Xin chào' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(
      () => expect(screen.getByText(/mock không nhận diện/i)).toBeInTheDocument(),
      { timeout: 5000 },
    );
    // không có bảng task
    expect(screen.queryByLabelText('Đội đang làm việc')).not.toBeInTheDocument();
  });

  it('SUB fail (§4b Gap2 A) → badge failed + render task.result.reason + badge ca "Lỗi"', async () => {
    render(<Workspace user={USER} onAuthExpired={noop} />);
    fireEvent.click(screen.getByRole('button', { name: /Ca mới/i }));
    const input = await screen.findByLabelText('Ô nhập câu hỏi');
    fireEvent.change(input, { target: { value: 'C001 vay — credit fail đi' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    // reason từ task.result.reason hiển thị (không phải chỉ badge)
    await waitFor(
      () => expect(screen.getByText(/timeout sau 120s/i)).toBeInTheDocument(),
      { timeout: 5000 },
    );
    // badge task đỏ
    const tasksPanel = screen.getByLabelText('Đội đang làm việc');
    expect(within(tasksPanel).getByText(/Tín dụng · ✗ lỗi/)).toBeInTheDocument();
    // badge trạng thái ca = Lỗi
    await waitFor(() => expect(screen.getAllByText(/^Lỗi$/).length).toBeGreaterThan(0));
  });

  it('MAIN fail (§4b Gap2 B) → system message lỗi + badge ca "Lỗi", KHÔNG treo bubble streaming', async () => {
    render(<Workspace user={USER} onAuthExpired={noop} />);
    fireEvent.click(screen.getByRole('button', { name: /Ca mới/i }));
    const input = await screen.findByLabelText('Ô nhập câu hỏi');
    fireEvent.change(input, { target: { value: 'lỗi main mô phỏng quá tải' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    // nội dung lỗi hiển thị (đến qua chat.delta done full_text — §4b Gap2 B)
    await waitFor(
      () => expect(screen.getByText(/MAIN hết trần retry/i)).toBeInTheDocument(),
      { timeout: 5000 },
    );
    // bubble streaming đã đóng (done kết lượt — không treo)
    await waitFor(() => expect(screen.queryByTestId('streaming-bubble')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getAllByText(/^Lỗi$/).length).toBeGreaterThan(0));
  });
});
