// cardUtil.ts — helper đọc field card AN TOÀN (N3 vỏ-mù: agent bơm items tự do, không ép shape).
// Mọi component card đọc field qua đây → field thiếu/kiểu lạ KHÔNG crash.
import type { Card } from '../../types';

// đọc mảng items (nếu thiếu/không phải mảng → [])
export function cardItems(card: Card): Record<string, unknown>[] {
  return Array.isArray(card.items) ? (card.items as Record<string, unknown>[]) : [];
}

// đọc field top-level tuỳ type (flags, recommended, total_days…) an toàn
export function cardField<T = unknown>(card: Card, key: string): T | undefined {
  const v = (card as Record<string, unknown>)[key];
  return v as T | undefined;
}

// đọc field 1 item (object bất kỳ) an toàn
export function itemField<T = unknown>(item: Record<string, unknown>, key: string): T | undefined {
  return item?.[key] as T | undefined;
}

// render 1 value MIXED (number | string | bool | khác) → string hiển thị (không .toFixed mù).
export function renderValue(v: unknown): string {
  if (v == null) return '—';
  if (typeof v === 'number') return String(v);
  if (typeof v === 'string') return v;
  if (typeof v === 'boolean') return v ? '✓' : '✗';
  return JSON.stringify(v);
}

// gom source từ item.source + card.sources (dedupe, giữ thứ tự) → list tên tool cho citation chip.
export function collectSources(card: Card): string[] {
  const out: string[] = [];
  const push = (s: unknown) => {
    if (typeof s === 'string' && s.trim() && !out.includes(s)) out.push(s);
  };
  cardItems(card).forEach((it) => push(it.source));
  const cardSources = card.sources;
  if (Array.isArray(cardSources)) cardSources.forEach(push);
  return out;
}
