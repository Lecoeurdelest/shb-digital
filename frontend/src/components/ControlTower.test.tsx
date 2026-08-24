// ControlTower.test.tsx — admin tách nghiệp vụ, kiểm soát, kỹ thuật và phòng thử nghiệm.
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ControlTower } from './ControlTower';
import { conversationApi } from '../api';
import type { ApprovalRow, AuditRow, Conversation } from '../types';

const appr: ApprovalRow[] = [
  { id: 'a1', conv_id: 'c1conv', task_id: null, action: 'disburse', payload: { items: [{ label: 'L001' }] }, status: 'pending' },
];
const approvedAppr: ApprovalRow = { ...appr[0], status: 'approved', decided_by: 'admin' };
const rejectedAppr: ApprovalRow = { ...appr[0], status: 'rejected', decided_by: 'admin' };
const audit: AuditRow[] = [
  {
    id: 'au1',
    task_id: 'task-1234567890',
    conv_id: 'c1',
    ts: '2026-01-01T10:00:00',
    actor: 'credit',
    tool: 'credit_assess',
    input: { owner_id: 'C001', amount_vnd: 500_000_000 },
    output: { item: { lane: 'green', assessment_id: 'asmt-1234567890' } },
    cost: { duration_ms: 830, total_tokens: 1200 },
  },
];
const convs: Conversation[] = [
  { id: 'c1', title: 'x', status: 'running', created_at: '' },
  { id: 'c2', title: 'y', status: 'done', created_at: '' },
];

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue(appr);
  vi.spyOn(conversationApi, 'auditFiltered').mockResolvedValue(audit);
  vi.spyOn(conversationApi, 'listConversations').mockResolvedValue(convs);
  // T13: tab Tổng quan là default → mock stats/assessments (tránh poll thật lỗi trong test)
  vi.spyOn(conversationApi, 'getStats').mockResolvedValue({
    window: 'today', approvals: { approved: 12, rejected: 3, pending: 5, auto: 7 },
    assessments: { green: 9, yellow: 6, red: 2 }, conversations: { total: 20, active: 3 },
    delta: { approvals_total: 4, assessments_total: 2 },
  });
  vi.spyOn(conversationApi, 'listAssessments').mockResolvedValue([]);
  vi.spyOn(conversationApi, 'listCases').mockResolvedValue([]);
});

describe('ControlTower', () => {
  it('tab Cơ sở sơ thẩm dùng case read-model, không mount AssessmentsView legacy', async () => {
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Cơ sở sơ thẩm'));

    await screen.findByText('Hồ sơ chờ sơ thẩm (0)');
    expect(conversationApi.listCases).toHaveBeenCalledWith({ limit: 50 });
    expect(conversationApi.listAssessments).not.toHaveBeenCalled();
  });

  it('Tổng quan mặc định chỉ tải KPI; tab kỹ thuật mới tải cost/trend', async () => {
    const getCost = vi.spyOn(conversationApi, 'getCost').mockResolvedValue({
      window: '24h', total_cost_usd: 1, cost_estimated: true,
      breakdown: { input_tokens: 1, output_tokens: 1, cache_read_tokens: 0, cache_create_tokens: 0 },
      by_model: [], by_role: [], anomalies: [], delta: { total_cost_pct: 0 },
    });
    const getCostTrend = vi.spyOn(conversationApi, 'getCostTrend').mockResolvedValue({ buckets: [] });
    render(<ControlTower onBack={vi.fn()} />);

    await screen.findByTestId('kpi-Phiếu đã duyệt');
    expect(getCost).not.toHaveBeenCalled();
    expect(getCostTrend).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText('Vận hành kỹ thuật'));
    await waitFor(() => expect(getCost).toHaveBeenCalledWith('24h'));
    expect(getCostTrend).toHaveBeenCalledWith('24h', 'hour', 'role');
  });

  it('admin mở Cấu hình agent, sửa prompt và kích hoạt version mới', async () => {
    const config = {
      environment: 'default', providers: [], prompts: [{
        key: 'main.system', scope: 'main', description: 'Điều phối chính', variables: [],
        active: { version: 3, content: 'Bản đang chạy', activated_by: 'admin', activated_at: '' },
      }],
    };
    vi.spyOn(conversationApi, 'getAgentConfig').mockResolvedValue(config);
    const save = vi.spyOn(conversationApi, 'saveAgentPrompt').mockResolvedValue({
      ...config,
      prompts: [{ ...config.prompts[0], active: { ...config.prompts[0].active!, version: 4, content: 'Bản mới' } }],
    });
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Cấu hình agent'));

    await screen.findByDisplayValue('Bản đang chạy');
    fireEvent.change(screen.getByLabelText('Nội dung prompt'), { target: { value: 'Bản mới' } });
    fireEvent.click(screen.getByRole('button', { name: 'Kích hoạt phiên bản mới' }));

    await waitFor(() => expect(save).toHaveBeenCalledWith('main.system', 'Bản mới'));
    expect(screen.getByText('Đang chạy: v4')).toBeInTheDocument();
  });

  it('tab Hàng chờ: list phiếu pending + nút Duyệt/Từ chối', async () => {
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Hàng chờ duyệt')); // default giờ là Tổng quan (T13-2)
    await waitFor(() => expect(screen.getByText(/disburse/)).toBeInTheDocument());
    expect(screen.getByTestId('queue-row-a1')).toBeInTheDocument();
    expect(screen.getByText(/Hàng chờ phê duyệt \(1\)/)).toBeInTheDocument();
  });

  it('duyệt từ queue → decideApproval + rời hàng chờ', async () => {
    const spy = vi.spyOn(conversationApi, 'decideApproval').mockResolvedValue(approvedAppr);
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Hàng chờ duyệt'));
    await waitFor(() => expect(screen.getByTestId('queue-row-a1')).toBeInTheDocument());
    fireEvent.click(screen.getAllByText(/✓ Duyệt/)[0]);
    expect(spy).toHaveBeenCalledWith('a1', 'approved', '');
    await waitFor(() => expect(screen.queryByTestId('queue-row-a1')).not.toBeInTheDocument());
  });

  // DF-B-07: từ chối 2 bước — bấm "✗ Từ chối" → expand ô lý do; lý do bắt buộc; xác nhận gửi reason.
  it('DF-B-07: Từ chối → expand ô lý do (bắt buộc); điền → xác nhận gửi reason', async () => {
    const spy = vi.spyOn(conversationApi, 'decideApproval').mockResolvedValue(rejectedAppr);
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Hàng chờ duyệt'));
    await waitFor(() => expect(screen.getByTestId('queue-row-a1')).toBeInTheDocument());
    // bấm "✗ Từ chối" → CHƯA gửi, mở ô lý do
    fireEvent.click(screen.getByTestId('reject-open-a1'));
    expect(screen.getByTestId('reject-panel-a1')).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled(); // chưa gửi
    // xác nhận disabled khi lý do rỗng
    expect(screen.getByTestId('reject-confirm-a1')).toBeDisabled();
    // điền lý do → xác nhận gửi decideApproval(id,'rejected',reason)
    fireEvent.change(screen.getByLabelText('Lý do từ chối'), { target: { value: 'Hồ sơ chưa đủ pháp lý' } });
    fireEvent.click(screen.getByTestId('reject-confirm-a1'));
    expect(spy).toHaveBeenCalledWith('a1', 'rejected', 'Hồ sơ chưa đủ pháp lý');
  });

  it('DF-B-07: Huỷ → đóng ô lý do, không gửi', async () => {
    const spy = vi.spyOn(conversationApi, 'decideApproval').mockResolvedValue(rejectedAppr);
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Hàng chờ duyệt'));
    await waitFor(() => expect(screen.getByTestId('queue-row-a1')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('reject-open-a1'));
    fireEvent.click(screen.getByText('Huỷ'));
    expect(screen.queryByTestId('reject-panel-a1')).not.toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it('tab Nhật ký kiểm soát: hiển thị sự kiện nghiệp vụ, không phơi tool/input JSON', async () => {
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Nhật ký kiểm soát'));
    await waitFor(() => expect(screen.getByText('Tín dụng · Đánh giá tín dụng')).toBeInTheDocument());
    expect(screen.getByLabelText('Lọc theo mã phiên')).toBeInTheDocument();
    expect(screen.getByLabelText('Lọc theo loại hoạt động')).toBeInTheDocument();
    expect(screen.getByText(/Khách C001/)).toBeInTheDocument();
    expect(screen.getByText('Đầu vào')).toBeInTheDocument();
    expect(screen.getAllByText(/500\.000\.000 ₫/).length).toBeGreaterThan(0);
    expect(screen.getByText('Kết quả')).toBeInTheDocument();
    expect(screen.getByText(/lane GREEN/)).toBeInTheDocument();
    expect(screen.getByText('Chi phí')).toBeInTheDocument();
    expect(screen.getByText(/1\.200 token/)).toBeInTheDocument();
    expect(screen.getByText(/Bước task-1234/)).toBeInTheDocument();
    expect(screen.queryByText('Tool')).not.toBeInTheDocument();
    expect(screen.queryByText('Input')).not.toBeInTheDocument();
    expect(screen.queryByText('credit_assess')).not.toBeInTheDocument();
    expect(screen.queryByText(/owner_id/)).not.toBeInTheDocument();
  });

  it('tab Tiến độ xử lý: đếm phiên theo status, không trộn cost', async () => {
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Tiến độ xử lý'));
    await waitFor(() => expect(screen.getByText(/Tiến độ xử lý — 2 phiên xử lý/)).toBeInTheDocument());
    expect(screen.queryByText(/Chi phí:/)).not.toBeInTheDocument();
  });

  // DF-B-03: "1 Lỗi" drill-down — phiên status='failed' hiện danh sách (tiêu đề + mã phiên).
  it('DF-B-03: tab Trạng thái có phiên lỗi → list phiên lỗi (tiêu đề + mã phiên)', async () => {
    vi.spyOn(conversationApi, 'listConversations').mockResolvedValue([
      { id: 'cok', title: 'Phiên đang chạy', status: 'running', created_at: '' },
      { id: 'cfailabcdef123456', title: 'Phiên xử lý C019 lỗi', status: 'failed', created_at: '' },
    ]);
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Tiến độ xử lý'));
    await waitFor(() => expect(screen.getByTestId('failed-list')).toBeInTheDocument());
    expect(screen.getByText(/Phiên xử lý đang lỗi \(1\)/)).toBeInTheDocument();
    expect(screen.getByTestId('failed-row-cfailabcdef123456')).toBeInTheDocument();
    expect(screen.getByText('Phiên xử lý C019 lỗi')).toBeInTheDocument();
  });

  it('DF-B-03: không có phiên lỗi → KHÔNG render list lỗi', async () => {
    // beforeEach mock: convs chỉ running/done → không failed
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Tiến độ xử lý'));
    await waitFor(() => expect(screen.getByText(/Tiến độ xử lý — 2 phiên xử lý/)).toBeInTheDocument());
    expect(screen.queryByTestId('failed-list')).not.toBeInTheDocument();
  });

  it('nút ← Workspace → onBack', () => {
    const onBack = vi.fn();
    render(<ControlTower onBack={onBack} />);
    fireEvent.click(screen.getByText(/Workspace/));
    expect(onBack).toHaveBeenCalled();
  });

  it('Phòng thử nghiệm: chạy compare → 2 cột single + multi + metrics', async () => {
    vi.spyOn(conversationApi, 'runCompare').mockResolvedValue({
      single: { text: 'trả lời đơn', duration_s: 4, tool_calls: 0 },
      multi: { text: 'đội thẩm định có nguồn', duration_s: 38, tool_calls: 4, cards: 2, conv_id: 'cX' },
    });
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Phòng thử nghiệm'));
    fireEvent.click(screen.getByTestId('compare-run'));
    await waitFor(() => expect(screen.getByText('trả lời đơn')).toBeInTheDocument());
    expect(screen.getByText('đội thẩm định có nguồn')).toBeInTheDocument();
    expect(screen.getByText(/4 bước xử lý/)).toBeInTheDocument();
    expect(screen.getByText(/Phiên xử lý:/)).toBeInTheDocument();
  });

  it('compare partial (multi null) → cột single + note partial', async () => {
    vi.spyOn(conversationApi, 'runCompare').mockResolvedValue({
      single: { text: 'chỉ single', duration_s: 4 },
      multi: null,
    });
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Phòng thử nghiệm'));
    fireEvent.click(screen.getByTestId('compare-run'));
    await waitFor(() => expect(screen.getByText('chỉ single')).toBeInTheDocument());
    expect(screen.getByText(/partial/)).toBeInTheDocument();
  });

  // DF-B-01: queue render display (tên khách/tiền/loan/lane) thay UUID+JSON thô.
  it('DF-B-01: row có display → tên khách + tiền VNĐ + loan + lane-chip', async () => {
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([
      { id: 'a1', conv_id: 'c1conv', task_id: null, action: 'disburse', payload: { x: 1 }, status: 'pending',
        display: { customer_name: 'Hộ KD Tân Phú', owner_id: 'C019', loan_id: 'L108', amount_vnd: 594_000_000, lane: 'yellow' } },
    ]);
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Hàng chờ duyệt'));
    await waitFor(() => expect(screen.getByText('Hộ KD Tân Phú')).toBeInTheDocument()); // tên khách, không UUID
    expect(screen.getByText('594.000.000 ₫')).toBeInTheDocument(); // tiền format VN
    expect(screen.getByText('L108')).toBeInTheDocument();
    expect(screen.getByText('YELLOW')).toBeInTheDocument(); // lane chip
  });

  it('DF-B-01 backward: display VẮNG (BE chưa deploy) → fallback shortId + JSON như cũ, không vỡ', async () => {
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([
      { id: 'a2', conv_id: 'abcdefghijklmnopqrst', task_id: null, action: 'disburse', payload: { loan: 'L001' }, status: 'pending' },
    ]);
    render(<ControlTower onBack={vi.fn()} />);
    fireEvent.click(screen.getByText('Hàng chờ duyệt'));
    await waitFor(() => expect(screen.getByTestId('queue-row-a2')).toBeInTheDocument());
    // fallback shortId conv (không có display) + JSON payload hiện
    expect(screen.getByText(/abcdefghij…/)).toBeInTheDocument();
    expect(screen.getByText(/L001/)).toBeInTheDocument();
  });
});
