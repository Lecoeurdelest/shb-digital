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

const RECEIPT_FALLBACK = 'Đã thực hiện; biên nhận lưu trong nhật ký.';

function isStructuredJson(value: string): boolean {
  const text = value.trim();
  if (!(text.startsWith('{') || text.startsWith('['))) return false;
  try {
    const parsed: unknown = JSON.parse(text);
    return parsed !== null && typeof parsed === 'object';
  } catch {
    return false;
  }
}

// Mapping chỉ ở tầng trình bày: wrapper phanh vẫn lưu action/field/receipt nguyên bản để audit.
// Thứ tự từ identifier dài đến ngắn để không tạo nhãn lai như "loan_Số tiền".
function sanitizeBusinessString(value: string): string {
  if (isStructuredJson(value)) return RECEIPT_FALLBACK;
  return value
    .replace(/\b(?:loan_amount_vnd|amount_vnd)\b/gi, 'Số tiền')
    .replace(/\b(?:loan_id|application_id)\b/gi, 'Khoản vay')
    .replace(/\bamount\b/gi, 'Số tiền')
    .replace(/\b(?:ops_disbursed?|disbursed?|ops_disburse|disburse)\b/gi, 'Giải ngân')
    .replace(/\bauto[-_ ]rule\b/gi, 'quy tắc phê duyệt')
    .replace(/provider/gi, 'cấu hình vận hành')
    .replace(/tokens?/gi, 'định mức xử lý')
    .replace(/tool/gi, 'nguồn nghiệp vụ')
    .replace(/\bmain\b/gi, 'hệ thống')
    .replace(/\bsub\b/gi, 'bước xử lý')
    .replace(/\bllm\b/gi, 'hệ thống')
    .replace(/\bjson\b/gi, 'dữ liệu có cấu trúc');
}

// Chỉ render primitive. Object/array là payload có cấu trúc: không stringify vì có thể chứa dữ
// liệu nội bộ ngoài contract trình bày. Chuỗi receipt JSON và identifier kỹ thuật cũng được đổi
// thành copy nghiệp vụ, không làm thay đổi resource/callback gốc (D-75).
export function renderValue(v: unknown): string {
  if (v == null) return '—';
  if (typeof v === 'number') return String(v);
  if (typeof v === 'string') return sanitizeBusinessString(v);
  if (typeof v === 'boolean') return v ? '✓' : '✗';
  return '—';
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
