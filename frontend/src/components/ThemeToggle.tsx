// ThemeToggle.tsx — nút 🌙/☀️ đổi dark/light (T11-6). Đặt ở header 3 mặt (Workspace/Tower/Landing).
import { useTheme } from '../hooks/useTheme';
import './ThemeToggle.css';

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggle } = useTheme();
  const dark = theme === 'dark';
  return (
    <button
      type="button"
      className={`theme-toggle${className ? ` ${className}` : ''}`}
      onClick={toggle}
      aria-label={dark ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'}
      title={dark ? 'Giao diện sáng' : 'Giao diện tối'}
      data-testid="theme-toggle"
    >
      {dark ? '☀️' : '🌙'}
    </button>
  );
}
