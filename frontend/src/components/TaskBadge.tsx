// components/TaskBadge.tsx — badge task running/done ăn từ SSE task.status (SPEC §9).
import type { OrchTask } from '../types';
import { roleLabel } from '../roles';
import './TaskBadge.css';

const STATUS_TONE: Record<OrchTask['status'], { cls: string; label: string }> = {
  queued: { cls: 'task-badge--idle', label: 'chờ' },
  running: { cls: 'task-badge--run', label: 'đang làm…' },
  done: { cls: 'task-badge--pass', label: '✓ xong' },
  failed: { cls: 'task-badge--fail', label: '✗ lỗi' },
};

export function TaskBadge({ task }: { task: OrchTask }) {
  const tone = STATUS_TONE[task.status] ?? STATUS_TONE.queued;
  const roleName = roleLabel(task.role);
  return (
    <span className={`task-badge ${tone.cls}`} data-testid={`task-badge-${task.id}`}>
      {task.status === 'running' && <span className="task-badge__dot deg-pulse" />}
      {roleName} · {tone.label}
    </span>
  );
}
