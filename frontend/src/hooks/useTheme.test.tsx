// useTheme.test.tsx — logic theme (T11-6): default LIGHT, persist localStorage, apply data-theme, toggle.
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { useTheme } from './useTheme';

beforeEach(() => {
  try { localStorage.clear(); } catch { /* ignore */ }
  delete document.documentElement.dataset.theme;
});

describe('useTheme', () => {
  it('default LIGHT khi dataset trống (không theo prefers-color-scheme)', () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('light');
  });

  it('setTheme(dark) → data-theme=dark + persist localStorage', () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setTheme('dark'));
    expect(result.current.theme).toBe('dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(localStorage.getItem('theme')).toBe('dark');
  });

  it('toggle light→dark→light', () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('light');
    act(() => result.current.toggle());
    expect(result.current.theme).toBe('dark');
    act(() => result.current.toggle());
    expect(result.current.theme).toBe('light');
  });

  it('đọc data-theme có sẵn (inline script index.html set trước) → phản ánh', () => {
    document.documentElement.dataset.theme = 'dark';
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('dark');
  });

  it('giá trị lạ trong dataset → coi như light (default an toàn)', () => {
    document.documentElement.dataset.theme = 'weird';
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('light');
  });
});
