// Canvas.test.tsx — ranh giới trình bày D-75 cho panel phải của Phiên xử lý.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Canvas } from './Canvas';
import type { Card, OrchTask } from '../types';

const taskWithTelemetry: OrchTask = {
  id: 't1', conv_id: 'c', role: 'credit', title: 'Thẩm định khả năng trả nợ', status: 'done',
  input_tokens: 18_400, output_tokens: 3_200, duration_ms: 8_240,
  model: 'glm-4.6', cost: { cost_usd: 0.42 },
};

const card: Card = {
  id: 'card1', conv_id: 'c', task_id: 't1', type: 'metric', ts: '',
  title: 'Khả năng trả nợ', items: [{ label: 'DSCR', value: '1,40', source: 'Báo cáo tài chính 2025' }],
};

describe('Canvas — bề mặt nghiệp vụ D-75', () => {
  it('mặc định mở Sản phẩm công việc và render card', () => {
    render(<Canvas cards={[card]} tasks={[taskWithTelemetry]} />);

    expect(screen.getByRole('tab', { name: /Sản phẩm công việc/i })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: /Tiến độ xử lý/i })).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByText('Khả năng trả nợ')).toBeInTheDocument();
  });

  it('không render metrics kỹ thuật dù task có telemetry', () => {
    render(<Canvas cards={[]} tasks={[taskWithTelemetry]} />);

    expect(screen.queryByTestId('conv-metrics-panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('conv-total-cost')).not.toBeInTheDocument();
    expect(screen.queryByTestId('tool-rank-bar')).not.toBeInTheDocument();
    expect(screen.queryByText('glm-4.6')).not.toBeInTheDocument();
    expect(screen.queryByText(/token/i)).not.toBeInTheDocument();
  });

  it('Tiến độ xử lý là tab phụ; hàng bước xử lý không phải control mở raw view', () => {
    render(<Canvas cards={[]} tasks={[taskWithTelemetry]} />);
    fireEvent.click(screen.getByRole('tab', { name: /Tiến độ xử lý/i }));

    const row = screen.getByTestId('task-row-t1');
    expect(screen.getByRole('tab', { name: /Tiến độ xử lý/i })).toHaveAttribute('aria-selected', 'true');
    expect(row).not.toHaveAttribute('role', 'button');
    expect(row).not.toHaveAttribute('tabindex');
    expect(screen.getByText(/Tín dụng · ✓ xong/)).toBeInTheDocument();
  });

  it('chỉ bước queued/running có Dừng bước; callback chỉ nhận task id và không lộ raw payload', async () => {
    const onInterruptTask = vi.fn().mockResolvedValue(undefined);
    const running: OrchTask = {
      ...taskWithTelemetry,
      id: 't-running',
      status: 'running',
      input: { tool: 'internal_tool', provider: 'secret-provider' },
      result: { reason: 'Sub dùng model có token và JSON' },
    };
    const queued: OrchTask = { ...taskWithTelemetry, id: 't-queued', status: 'queued' };
    const failed: OrchTask = { ...taskWithTelemetry, id: 't-failed', status: 'failed' };
    render(<Canvas cards={[]} tasks={[running, queued, taskWithTelemetry, failed]} onInterruptTask={onInterruptTask} />);
    fireEvent.click(screen.getByRole('tab', { name: /Tiến độ xử lý/i }));

    expect(screen.getByTestId('task-stop-t-running')).toHaveTextContent('Dừng bước');
    expect(screen.getByTestId('task-stop-t-queued')).toBeInTheDocument();
    expect(screen.queryByTestId('task-stop-t1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('task-stop-t-failed')).not.toBeInTheDocument();
    expect(screen.queryByText(/internal_tool|secret-provider|Sub dùng model|token|JSON/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('task-stop-t-running'));
    await waitFor(() => expect(onInterruptTask).toHaveBeenCalledWith('t-running'));
  });

  it('approval trong Workspace luôn chỉ đọc, không có action quyết phiếu', () => {
    const approval: Card = {
      id: 'approval-card', conv_id: 'c', task_id: null, type: 'approval', ts: '2026-08-24T02:30:00Z',
      title: 'Duyệt: disburse (loan_id=L001)', action: 'disburse', approval_id: 'a1', status: 'pending',
      items: [{ label: 'loan_id', value: 'L001' }],
    };
    render(<Canvas cards={[approval]} tasks={[]} />);

    expect(screen.getByTestId('approval-waiting')).toBeInTheDocument();
    expect(screen.queryByTestId('approval-approve')).not.toBeInTheDocument();
    expect(screen.queryByTestId('approval-reject')).not.toBeInTheDocument();
  });

  it('citation banner chỉ hiện nhãn nghiệp vụ nhưng callback card vẫn giữ source nội bộ', () => {
    render(<Canvas cards={[card]} tasks={[]} />);
    fireEvent.click(screen.getByTestId('cite-Báo cáo tài chính 2025'));

    expect(screen.getByRole('status')).toHaveTextContent('Nguồn nghiệp vụ');
    expect(screen.queryByText('Báo cáo tài chính 2025')).not.toBeInTheDocument();
  });

  it('empty-state mô tả sản phẩm nghiệp vụ, không mô tả đội hay telemetry', () => {
    render(<Canvas cards={[]} tasks={[]} />);

    expect(screen.getByText(/Các chỉ số, điều kiện và tờ trình/i)).toBeInTheDocument();
    expect(screen.queryByText(/Main|SUB|model|provider|token|thinking|LLM|raw JSON/i)).not.toBeInTheDocument();
  });

  it('tiến độ trống nhưng có form pending → nhắc điền hồ sơ trước', () => {
    const form: Card = {
      id: 'form1', conv_id: 'c', task_id: null, type: 'form', ts: '',
      title: 'Hồ sơ vay', status: 'pending', fields: [],
    };
    render(<Canvas cards={[form]} tasks={[]} />);
    fireEvent.click(screen.getByRole('tab', { name: /Tiến độ xử lý/i }));

    expect(screen.getByText('Chưa có bước xử lý nào.')).toBeInTheDocument();
    expect(screen.getByText(/Điền và gửi hồ sơ/i)).toBeInTheDocument();
  });
});
