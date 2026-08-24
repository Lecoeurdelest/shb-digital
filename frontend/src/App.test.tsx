// App.test.tsx — vòng lõi Phiên xử lý qua mock API + ranh giới trình bày D-75.
// Test Workspace TRỰC TIẾP (auth gate ở App = test riêng App.gate.test.tsx) — inject user giả.
import { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { Workspace } from './Workspace';
import { mockBackend } from './api/mock';
import { conversationApi } from './api';
import type { AuthUser, Conversation, OrchTask } from './types';

const USER: AuthUser = { username: 'user', role: 'user' };
const ADMIN: AuthUser = { username: 'admin', role: 'admin' };
const noop = vi.fn();

function seedTask(status: OrchTask['status'] = 'running') {
  const conv = mockBackend.createConversation('Phiên đang xử lý');
  mockBackend.getFullState(conv.id).tasks.push({
    id: 'task-running', conv_id: conv.id, role: 'credit', title: 'Đối chiếu khả năng trả nợ', status,
    input: { tool: 'credit_assess', provider: 'secret-provider' },
    result: { reason: 'Sub model token JSON' },
  });
  return conv;
}

// mockBackend singleton → reset giữa test để rooms/tasks không leak; restore toàn bộ network spies.
afterEach(() => {
  vi.restoreAllMocks();
  mockBackend.reset();
});

describe('Workspace chat — vòng lõi S1 (mock API)', () => {
  it('tạo phiên bằng mặc định server → xử lý C001 → hiển thị kết quả + tiến độ Tín dụng', async () => {
    const createSpy = vi.spyOn(conversationApi, 'createConversation');
    render(<Workspace user={USER} onAuthExpired={noop} />);

    // ban đầu: empty state
    expect(screen.getByText(/Chưa mở phiên xử lý nào/i)).toBeInTheDocument();

    // "+ Phiên xử lý" → khung soạn, chưa tạo resource (lazy — D-45b).
    fireEvent.click(screen.getByRole('button', { name: /Phiên xử lý/i }));

    // ô nhập xuất hiện (draft mode)
    const input = await screen.findByLabelText('Ô nhập câu hỏi');
    fireEvent.change(input, { target: { value: 'Khách C001 xin vay 5 tỷ — DSCR bao nhiêu?' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    // gửi yêu cầu đầu → phiên tạo lazy bằng mặc định server.
    await waitFor(() => expect(createSpy).toHaveBeenCalledTimes(1));
    expect(createSpy.mock.calls[0]).toEqual(['Phiên xử lý mới']);

    // Cụm kết luận nằm cuối answer → chứng minh stream đã hoàn tất.
    await waitFor(
      () => expect(screen.getByText(/Cần đối chiếu thêm CIC/i)).toBeInTheDocument(),
      { timeout: 5000 },
    );
    expect(screen.getAllByText(/DSCR = 3\.709/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/credit_assess/i)).not.toBeInTheDocument();

    // Sản phẩm công việc là tab mặc định; tiến độ là tab phụ và không mở raw task.
    expect(screen.getByRole('tab', { name: /Sản phẩm công việc/i })).toHaveAttribute('aria-selected', 'true');
    fireEvent.click(screen.getByRole('tab', { name: /Tiến độ xử lý/i }));
    const tasksPanel = screen.getByLabelText('Tiến độ xử lý');
    await waitFor(() =>
      expect(within(tasksPanel).getByText(/Tín dụng · ✓ xong/)).toBeInTheDocument(),
    );
  });

  it('câu không liên quan tín dụng → vẫn stream trả lời, không tạo task credit', async () => {
    render(<Workspace user={USER} onAuthExpired={noop} />);
    fireEvent.click(screen.getByRole('button', { name: /Phiên xử lý/i }));
    const input = await screen.findByLabelText('Ô nhập câu hỏi');
    fireEvent.change(input, { target: { value: 'Xin chào' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(
      () => expect(screen.getByText(/mock không nhận diện/i)).toBeInTheDocument(),
      { timeout: 5000 },
    );
    fireEvent.click(screen.getByRole('tab', { name: /Tiến độ xử lý/i }));
    expect(screen.getByText(/Chưa có bước xử lý nào/i)).toBeInTheDocument();
  });

  it('Workspace không gọi endpoint kỹ thuật và không render telemetry', async () => {
    mockBackend.createConversation('Phiên có sẵn');
    const auditSpy = vi.spyOn(conversationApi, 'auditByConv');
    const modelsSpy = vi.spyOn(conversationApi, 'getModels');
    const costSpy = vi.spyOn(conversationApi, 'getCost');
    const { container } = render(<Workspace user={USER} onAuthExpired={noop} />);
    await waitFor(() => expect(container.querySelector('.conv-sidebar__title')).toBeInTheDocument());
    fireEvent.click(container.querySelector('.conv-sidebar__title')!);
    await waitFor(() => expect(screen.getAllByText('Phiên có sẵn').length).toBeGreaterThan(0));

    expect(auditSpy).not.toHaveBeenCalled();
    expect(modelsSpy).not.toHaveBeenCalled();
    expect(costSpy).not.toHaveBeenCalled();
    expect(screen.queryByTestId('model-select')).not.toBeInTheDocument();
    expect(screen.queryByTestId('main-metrics')).not.toBeInTheDocument();
    expect(screen.queryByTestId('conv-metrics-panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('trace-block')).not.toBeInTheDocument();
  });

  it('Dừng bước gọi đúng conversation/task rồi refetch, không mở raw task view', async () => {
    const conv = seedTask();
    const interruptSpy = vi.spyOn(conversationApi, 'interruptTask').mockResolvedValue({ cancelled: true });
    render(<Workspace user={USER} onAuthExpired={noop} />);

    await waitFor(() => expect(screen.getAllByText('Phiên đang xử lý').length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole('tab', { name: /Tiến độ xử lý/i }));
    fireEvent.click(await screen.findByTestId('task-stop-task-running'));

    await waitFor(() => expect(interruptSpy).toHaveBeenCalledWith(conv.id, 'task-running'));
    expect(screen.queryByText(/credit_assess|secret-provider|Sub model token JSON/i)).not.toBeInTheDocument();
  });

  it('interrupt lỗi chỉ hiện thông báo nghiệp vụ generic, không lộ lỗi runtime', async () => {
    seedTask();
    vi.spyOn(conversationApi, 'interruptTask').mockRejectedValue(
      new Error('Sub internal_tool provider model token JSON timeout'),
    );
    render(<Workspace user={USER} onAuthExpired={noop} />);

    await waitFor(() => expect(screen.getAllByText('Phiên đang xử lý').length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole('tab', { name: /Tiến độ xử lý/i }));
    fireEvent.click(await screen.findByTestId('task-stop-task-running'));

    expect(await screen.findByText(/Không thể dừng bước xử lý/i)).toBeInTheDocument();
    expect(screen.queryByText(/internal_tool|provider|model|token|JSON|timeout/i)).not.toBeInTheDocument();
  });

  it('admin Workspace chỉ đọc phiếu chờ; quyết định cuối chỉ ở Control Tower', async () => {
    const conv = mockBackend.createConversation('Phiên chờ phê duyệt');
    const state = mockBackend.getFullState(conv.id);
    state.cards ??= [];
    state.cards.push({
      id: 'approval-card', conv_id: conv.id, task_id: null, type: 'approval', ts: '2026-08-24T09:30:00Z',
      title: 'Duyệt: disburse (loan_id=L001)', action: 'disburse', approval_id: 'approval-1', status: 'pending',
      items: [{ label: 'loan_id', value: 'L001' }],
    });
    const decideSpy = vi.spyOn(conversationApi, 'decideApproval');
    render(<Workspace user={ADMIN} onAuthExpired={noop} />);

    expect(await screen.findByTestId('approval-waiting')).toBeInTheDocument();
    expect(screen.queryByTestId('approval-approve')).not.toBeInTheDocument();
    expect(screen.queryByTestId('approval-reject')).not.toBeInTheDocument();
    expect(decideSpy).not.toHaveBeenCalled();
    expect(screen.getByText(/Sơ thẩm — quyết định cuối thuộc người có thẩm quyền/i)).toBeInTheDocument();
  });

  it('bước nghiệp vụ fail → cảnh báo an toàn + tiến độ lỗi, không lộ raw task output', async () => {
    render(<Workspace user={USER} onAuthExpired={noop} />);
    fireEvent.click(screen.getByRole('button', { name: /Phiên xử lý/i }));
    const input = await screen.findByLabelText('Ô nhập câu hỏi');
    fireEvent.change(input, { target: { value: 'C001 vay — credit fail đi' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    // Raw reason có timeout/runtime không được đẩy lên bề mặt nghiệp vụ.
    await waitFor(
      () => expect(screen.getByText(/Không hoàn tất bước xử lý/i)).toBeInTheDocument(),
      { timeout: 5000 },
    );
    expect(screen.queryByText(/timeout sau 120s|Sub|tool|model|token|JSON/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: /Tiến độ xử lý/i }));
    const tasksPanel = screen.getByLabelText('Tiến độ xử lý');
    expect(within(tasksPanel).getByText(/Tín dụng · ✗ lỗi/)).toBeInTheDocument();
    // badge trạng thái ca = Lỗi
    await waitFor(() => expect(screen.getAllByText(/^Lỗi$/).length).toBeGreaterThan(0));
  });

  it('bước tổng hợp fail → lỗi nghiệp vụ + trạng thái "Lỗi", không lộ lỗi runtime', async () => {
    render(<Workspace user={USER} onAuthExpired={noop} />);
    fireEvent.click(screen.getByRole('button', { name: /Phiên xử lý/i }));
    const input = await screen.findByLabelText('Ô nhập câu hỏi');
    fireEvent.change(input, { target: { value: 'lỗi main mô phỏng quá tải' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    // lỗi kỹ thuật được chuyển thành thông báo nghiệp vụ.
    await waitFor(
      () => expect(screen.getByText(/Không thể hoàn tất bước xử lý/i)).toBeInTheDocument(),
      { timeout: 5000 },
    );
    expect(screen.queryByText(/MAIN hết trần retry/i)).not.toBeInTheDocument();
    // bubble streaming đã đóng (done kết lượt — không treo)
    await waitFor(() => expect(screen.queryByTestId('streaming-bubble')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getAllByText(/^Lỗi$/).length).toBeGreaterThan(0));
  });

  // DF-A-07: mở draft trước khi list resolve không bị auto-select đè.
  it('DF-A-07: "+ Phiên xử lý" trước khi list resolve → giữ nháp', async () => {
    // listConversations DEFERRED — kiểm soát thời điểm resolve (mô phỏng mạng chậm ở prod).
    let resolveList!: (v: Conversation[]) => void;
    const deferred = new Promise<Conversation[]>((res) => { resolveList = res; });
    vi.spyOn(conversationApi, 'listConversations').mockReturnValue(deferred);

    render(<Workspace user={USER} onAuthExpired={noop} />);
    fireEvent.click(screen.getByRole('button', { name: /Phiên xử lý/i }));
    expect(await screen.findByLabelText('Ô nhập câu hỏi')).toHaveAttribute('placeholder', expect.stringMatching(/yêu cầu nghiệp vụ đầu tiên/i));

    // GIỜ list resolve (muộn) với 1 ca cũ — KHÔNG được đè activeId (draft giữ nguyên).
    await act(async () => {
      resolveList([{ id: 'old1', title: 'Phiên cũ', status: 'idle', created_at: '2026-07-18T10:00:00' }]);
      await Promise.resolve();
    });

    // BẰNG CHỨNG bug: gửi tin đầu → PHẢI tạo ca MỚI (createConversation), KHÔNG gửi vào ca cũ old1.
    // Nếu race đè activeId=old1 → sendChat(old1) chạy (bug), createConversation KHÔNG gọi.
    const createSpy = vi.spyOn(conversationApi, 'createConversation').mockResolvedValue(
      { id: 'new1', title: 'Phiên xử lý mới', status: 'idle', created_at: '2026-07-19T00:00:00' },
    );
    const sendSpy = vi.spyOn(conversationApi, 'sendChat').mockResolvedValue(undefined);
    const input = screen.getByLabelText('Ô nhập câu hỏi');
    fireEvent.change(input, { target: { value: 'Tôi muốn hỏi vay mua xe' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => expect(createSpy).toHaveBeenCalled()); // tạo ca MỚI (không nuốt vào ca cũ)
    expect(createSpy.mock.calls[0]).toEqual(['Phiên xử lý mới']);
    // KHÔNG gửi thẳng vào ca cũ old1 (bug DF-A-07)
    expect(sendSpy).not.toHaveBeenCalledWith('old1', expect.anything());
  });
});
