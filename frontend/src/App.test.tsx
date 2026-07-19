// App.test.tsx — vòng lõi chat qua mock API (VITE_USE_MOCK_API mặc định bật trong test).
// Chứng minh: tạo ca → gõ câu C001 → mock stream chat.delta + task credit → DSCR 3.709 render +
// badge task "xong". Bổ trợ Chrome verify (không thay thế — Gate 2 vẫn đòi browser).
// Test Workspace TRỰC TIẾP (auth gate ở App = test riêng App.gate.test.tsx) — inject user giả.
import { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { Workspace } from './Workspace';
import { mockBackend } from './api/mock';
import { conversationApi } from './api';
import type { AuthUser, Conversation } from './types';

const USER: AuthUser = { username: 'user', role: 'user' };
const noop = vi.fn();

// mockBackend singleton → reset giữa test để rooms/tasks không leak (ca cũ auto-select lúc mount).
afterEach(() => mockBackend.reset());

describe('Workspace chat — vòng lõi S1 (mock API)', () => {
  it('tạo ca → gõ câu C001 → hiển thị DSCR 3.709 + badge Tín dụng xong', async () => {
    render(<Workspace user={USER} onAuthExpired={noop} />);

    // ban đầu: empty state
    expect(screen.getByText(/Chưa mở ca nào/i)).toBeInTheDocument();

    // "+ Ca mới" → khung soạn (draft): composer + picker hiện, ca CHƯA tạo (lazy — D-45b)
    fireEvent.click(screen.getByRole('button', { name: /Ca mới/i }));

    // ô nhập xuất hiện (draft mode)
    const input = await screen.findByLabelText('Ô nhập câu hỏi');
    fireEvent.change(input, { target: { value: 'Khách C001 xin vay 5 tỷ — DSCR bao nhiêu?' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    // gửi câu đầu → ca tạo lazy → user message hiện (optimistic, sau POST create — dùng findBy async)
    expect(await screen.findByText(/Khách C001 xin vay 5 tỷ/)).toBeInTheDocument();

    // chờ tới khi stream chạy XONG câu trả lời — chờ TRỰC TIẾP "DSCR = 3.709" (tín hiệu answer done).
    // (Sửa 2026-07-19 T16-4: trước chờ /credit_assess/ nhưng ToolRankBar giờ render tool-name
    // "credit_assess" NGAY khi trace có → điều kiện chờ khớp SỚM, DSCR chưa done. Chờ chính DSCR
    // là tín hiệu answer-render đúng, không ambiguous. Số kèm nguồn — SPEC §6.)
    await waitFor(
      () => expect(screen.getAllByText(/DSCR = 3\.709/).length).toBeGreaterThan(0),
      { timeout: 5000 },
    );
    // nguồn credit_assess cũng render (trace toolcall + answer text) — số kèm nguồn
    expect(screen.getAllByText(/credit_assess/).length).toBeGreaterThan(0);

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

  it('mở ca CÓ SẴN → hydrate trace toolcall từ GET /api/audit (reload-safe T4-2 fix)', async () => {
    // seed 1 ca sẵn trong mock → mở lại ca đó (click sidebar) → auditByConv hydrate trace.
    // (flow lazy-create D-45b: "+ Ca mới" chỉ mở draft, KHÔNG open ca — hydrate test qua MỞ ca có sẵn.)
    const seeded = mockBackend.createConversation('Ca có sẵn');
    const { conversationApi } = await import('./api');
    vi.spyOn(conversationApi, 'auditByConv').mockResolvedValue([
      { id: 'au_reload', task_id: 't1', conv_id: seeded.id, ts: '', actor: 'credit', tool: 'credit_assess', input: { owner_id: 'C001' }, output: {} },
    ]);
    const { container } = render(<Workspace user={USER} onAuthExpired={noop} />);
    // click ca có sẵn trong SIDEBAR (title xuất hiện cả ở chat-head khi active) → openConversation
    // → auditByConv → setTrace → TraceBlock hiện
    await waitFor(() => expect(container.querySelector('.conv-sidebar__title')).toBeInTheDocument());
    fireEvent.click(container.querySelector('.conv-sidebar__title')!);
    await waitFor(() => expect(screen.getByTestId('trace-block')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { expanded: false }));
    expect(screen.getByText('credit_assess')).toBeInTheDocument();
    vi.restoreAllMocks();
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

  // DF-A-07 regression: fresh load, user bấm "+ Ca mới" TRƯỚC khi listConversations resolve → mount
  // auto-select KHÔNG được đè draft về ca cũ (race). Guard draftingRef.
  it('DF-A-07: "+ Ca mới" trước khi list ca resolve → giữ NHÁP, không đè về ca cũ', async () => {
    // listConversations DEFERRED — kiểm soát thời điểm resolve (mô phỏng mạng chậm ở prod).
    let resolveList!: (v: Conversation[]) => void;
    const deferred = new Promise<Conversation[]>((res) => { resolveList = res; });
    vi.spyOn(conversationApi, 'listConversations').mockReturnValue(deferred);

    render(<Workspace user={USER} onAuthExpired={noop} />);
    // list CHƯA resolve → chưa có ca active. User bấm "+ Ca mới" NGAY (vào draft).
    fireEvent.click(screen.getByRole('button', { name: /Ca mới/i }));
    expect(await screen.findByLabelText('Ô nhập câu hỏi')).toHaveAttribute('placeholder', expect.stringMatching(/Gõ câu hỏi đầu tiên/));

    // GIỜ list resolve (muộn) với 1 ca cũ — KHÔNG được đè activeId (draft giữ nguyên).
    await act(async () => {
      resolveList([{ id: 'old1', title: 'Ca cũ', status: 'idle', created_at: '2026-07-18T10:00:00' }]);
      await Promise.resolve();
    });

    // BẰNG CHỨNG bug: gửi tin đầu → PHẢI tạo ca MỚI (createConversation), KHÔNG gửi vào ca cũ old1.
    // Nếu race đè activeId=old1 → sendChat(old1) chạy (bug), createConversation KHÔNG gọi.
    const createSpy = vi.spyOn(conversationApi, 'createConversation').mockResolvedValue(
      { id: 'new1', title: 'Ca mới', status: 'idle', created_at: '2026-07-19T00:00:00' },
    );
    const sendSpy = vi.spyOn(conversationApi, 'sendChat').mockResolvedValue(undefined);
    const input = screen.getByLabelText('Ô nhập câu hỏi');
    fireEvent.change(input, { target: { value: 'Tôi muốn hỏi vay mua xe' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => expect(createSpy).toHaveBeenCalled()); // tạo ca MỚI (không nuốt vào ca cũ)
    // KHÔNG gửi thẳng vào ca cũ old1 (bug DF-A-07)
    expect(sendSpy).not.toHaveBeenCalledWith('old1', expect.anything());
    vi.restoreAllMocks();
  });
});
