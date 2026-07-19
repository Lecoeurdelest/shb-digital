// TaskMetricsChips.tsx — S16 T16-4: chip metrics per task (model · duration · cost ước tính · tokens
// tổng). null → không render (backward mọi ca cũ — task chưa có metrics từ T16-1). Dùng trong
// SubAgentView + bảng việc. cost = "ước tính" (provider ngoài không tin — cùng nhãn T16-3).
import { taskBreakdown, taskCostUsd, hasTaskMetrics, fmtDuration } from './traceMetrics';
import { fmtUsd, fmtTokens } from './costTransforms';
import type { OrchTask } from '../../types';
import './TaskMetricsChips.css';

export function TaskMetricsChips({ task }: { task: OrchTask }) {
  if (!hasTaskMetrics(task)) return null; // task cũ → không hiện gì

  const bd = taskBreakdown(task);
  const totalTokens = bd.input_tokens + bd.output_tokens + bd.cache_read_tokens + bd.cache_create_tokens;
  const cost = taskCostUsd(task);

  return (
    <div className="tmc" data-testid={`task-metrics-${task.id}`}>
      {task.model && <span className="tmc__chip tmc__chip--model" data-testid="tmc-model">⚙ {task.model}</span>}
      {task.duration_ms != null && <span className="tmc__chip" data-testid="tmc-duration">⏱ {fmtDuration(task.duration_ms)}</span>}
      {cost != null && <span className="tmc__chip tmc__chip--cost" data-testid="tmc-cost">💰 {fmtUsd(cost)} <em>ước tính</em></span>}
      {totalTokens > 0 && <span className="tmc__chip" data-testid="tmc-tokens">🔢 {fmtTokens(totalTokens)} token</span>}
    </div>
  );
}
