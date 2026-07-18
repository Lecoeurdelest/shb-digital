// useTheme.ts — dark/light toàn app (T11-6, default LIGHT). Nguồn sự thật = documentElement.dataset.theme
// (set trước first-paint bởi inline script index.html — chống FOUC). Hook đọc/ghi + persist localStorage.
// KHÔNG theo prefers-color-scheme (user chốt default light tường minh).
import { useCallback, useSyncExternalStore } from 'react';

export type Theme = 'light' | 'dark';
const KEY = 'theme';

function current(): Theme {
  const t = document.documentElement.dataset.theme;
  return t === 'dark' ? 'dark' : 'light'; // default LIGHT (bất kỳ giá trị lạ → light)
}

// subscribe re-render khi theme đổi (custom event 'themechange' phát khi set).
function subscribe(cb: () => void): () => void {
  window.addEventListener('themechange', cb);
  return () => window.removeEventListener('themechange', cb);
}

function apply(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem(KEY, theme); } catch { /* private mode → chỉ đổi runtime */ }
  window.dispatchEvent(new Event('themechange'));
}

export function useTheme(): { theme: Theme; toggle: () => void; setTheme: (t: Theme) => void } {
  const theme = useSyncExternalStore(subscribe, current, () => 'light' as Theme);
  const setTheme = useCallback((t: Theme) => apply(t), []);
  const toggle = useCallback(() => apply(current() === 'dark' ? 'light' : 'dark'), []);
  return { theme, toggle, setTheme };
}
