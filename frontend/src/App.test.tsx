// App.test.tsx — vòng lõi chat qua mock API (VITE_USE_MOCK_API mặc định bật trong test).
// Chứng minh: tạo ca → gõ câu C001 → mock stream chat.delta + task credit → DSCR 3.709 render +
// badge task "xong". Bổ trợ Chrome verify (không thay thế — Gate 2 vẫn đòi browser).
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from './App';

describe('Workspace chat — vòng lõi S1 (mock API)', () => {
  it('tạo ca → gõ câu C001 → hiển thị DSCR 3.709 + badge Tín dụng xong', async () => {
    render(<App />);

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
    render(<App />);
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
});
