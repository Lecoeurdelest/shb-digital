// workspaceUtil.ts — helper THUẦN (không state/hook) tách khỏi Workspace.tsx (nợ ghi từ S14 —
// file gốc >400 LOC). upsert/canvas/audit/error-shape dùng chung giữa Workspace + useWorkspaceController.

import { ApiRequestError } from './api/client';
import type { AuditRow, Card, OrchTask, TraceItem } from './types';

// upsert theo id, giữ thứ tự cũ + append cái mới (SSE task.created/status cùng shape GET).
export function upsertById<T extends { id: string }>(list: T[], item: T): T[] {
  const idx = list.findIndex((x) => x.id === item.id);
  if (idx === -1) return [...list, item];
  const next = list.slice();
  next[idx] = item;
  return next;
}

// canvas-present §4: dựng canvas từ full-state cards[] — replace theo (task_id,type) giữ ts mới nhất
// (1 role trình lại cùng loại card → thay bản cũ, không nhân đôi). Sort theo ts để thứ tự ổn định.
export function buildCanvas(cards: Card[]): Card[] {
  const byKey = new Map<string, Card>();
  for (const c of [...cards].sort((a, b) => (a.ts ?? '').localeCompare(b.ts ?? ''))) {
    byKey.set(canvasKey(c), c); // ts sau ghi đè ts trước
  }
  return [...byKey.values()];
}

// upsert 1 card (SSE) vào canvas: cùng id → replace; cùng (task_id,type) khác id → thay bản cũ giữ mới.
export function upsertCardInto(prev: Card[], card: Card): Card[] {
  const key = canvasKey(card);
  const next = prev.filter((c) => c.id !== card.id && canvasKey(c) !== key);
  next.push(card);
  return next.sort((a, b) => (a.ts ?? '').localeCompare(b.ts ?? ''));
}

export function canvasKey(c: Card): string {
  return `${c.task_id ?? 'null'}::${c.type}`;
}

// AuditRow (GET /api/audit) → TraceItem toolcall. id khớp SSE toolcall id (dedup upsert). summary
// từ input (tóm tắt ≤120 char). thinking KHÔNG có trong audit (live-only) — reload chỉ toolcall.
export function auditToTrace(row: AuditRow): TraceItem {
  let summary = '';
  if (row.input) {
    try {
      summary = JSON.stringify(row.input).slice(0, 120);
    } catch {
      summary = '';
    }
  }
  return { kind: 'tool', id: row.id, task_id: row.task_id, tool: row.tool, summary };
}

// Đọc {status, message} an toàn từ lỗi API — hoạt động cho CẢ ApiRequestError (real, có .body.message)
// LẪN ApiErrorLike của mock (extends Error, có .status + .message). Dùng cho 409 CRUD (T15-3) để hiện
// đúng hint 4-field của BE ở cả 2 chế độ.
export function readApiError(err: unknown): { status: number | null; message: string | null } {
  if (err instanceof ApiRequestError) return { status: err.status, message: err.body?.message ?? null };
  if (err && typeof err === 'object' && 'status' in err) {
    const e = err as { status?: unknown; message?: unknown };
    return {
      status: typeof e.status === 'number' ? e.status : null,
      message: typeof e.message === 'string' ? e.message : null,
    };
  }
  return { status: null, message: null };
}

export function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiRequestError) {
    return err.body?.message ?? `${fallback} (HTTP ${err.status})`;
  }
  if (err instanceof Error && err.message) return `${fallback}: ${err.message}`;
  return fallback;
}

// lý do lỗi từ task.result.reason (CONTRACT §4b Gap2 A — result là dict tự do, đọc an toàn).
export function taskReason(task: OrchTask): string | null {
  const reason = task.result?.reason;
  return typeof reason === 'string' && reason.trim() ? reason : null;
}
