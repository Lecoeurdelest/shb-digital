// CitationChip.tsx — chip nguồn (tên tool) trên card. S2: hiện tên + tooltip + bấm được
// (onCite gọi lại với taskId+source). Trace view đầy đủ = S4. "Mọi con số có nguồn" — điểm
// demo bank (canvas-present §3). DRY: dùng chung mọi card type.
import './CitationChip.css';

interface Props {
  source: string;
  taskId: string | null;
  onCite?: (taskId: string | null, source: string) => void;
}

export function CitationChip({ source, taskId, onCite }: Props) {
  return (
    <button
      type="button"
      className="cite-chip"
      title={`Nguồn: ${source}${taskId ? ` (trace task ${taskId.slice(0, 8)}…)` : ''} — bấm để soi tool-call`}
      onClick={() => onCite?.(taskId, source)}
      data-testid={`cite-${source}`}
    >
      <span className="cite-chip__icon" aria-hidden="true">⛬</span>
      {source}
    </button>
  );
}
