// CitationChip.tsx — chip nguồn nghiệp vụ. Raw source chỉ dùng làm khóa/callback nội bộ;
// bề mặt RM/khách hàng chỉ hiện nhãn nghiệp vụ (D-75).
import './CitationChip.css';
import { sourceLabel } from './sourceLabels';

interface Props {
  source: string;
  taskId: string | null;
  onCite?: (taskId: string | null, source: string) => void;
}

export function CitationChip({ source, taskId, onCite }: Props) {
  const label = sourceLabel(source);
  return (
    <button
      type="button"
      className="cite-chip"
      title={`Nguồn nghiệp vụ: ${label}`}
      onClick={() => onCite?.(taskId, source)}
      data-testid={`cite-${source}`}
    >
      <span className="cite-chip__icon" aria-hidden="true">⛬</span>
      {label}
    </button>
  );
}
