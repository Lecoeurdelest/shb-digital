import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react';
import { conversationApi } from '../../api';
import type { CaseSummary } from '../../types';

export function useExactCaseFocus(
  focusedCaseId: string | undefined,
  setRows: Dispatch<SetStateAction<CaseSummary[]>>,
  setSelectedId: Dispatch<SetStateAction<string | null>>,
) {
  const [focusIssue, setFocusIssue] = useState<string | null>(null);
  const focusedRow = useRef<CaseSummary | null>(null);

  const mergeFocused = useCallback((list: CaseSummary[]) => {
    const exact = focusedRow.current;
    if (!exact) return list;
    const index = list.findIndex((item) => item.id === exact.id);
    if (index < 0) return [exact, ...list];
    return list.map((item, rowIndex) => rowIndex === index ? exact : item);
  }, []);

  useEffect(() => {
    let alive = true;
    focusedRow.current = null;
    setFocusIssue(null);
    if (!focusedCaseId) return () => { alive = false; };
    conversationApi
      .getCase(focusedCaseId)
      .then((item) => {
        if (!alive) return;
        focusedRow.current = item;
        setRows((current) => mergeFocused(current));
        setSelectedId(item.id);
      })
      .catch(() => {
        if (alive) setFocusIssue('Không mở được hồ sơ từ liên kết. Danh sách bên dưới vẫn dùng được.');
      });
    return () => { alive = false; };
  }, [focusedCaseId, mergeFocused, setRows, setSelectedId]);

  return { focusIssue, mergeFocused };
}
