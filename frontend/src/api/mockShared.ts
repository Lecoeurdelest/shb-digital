// api/mockShared.ts — primitive dùng chung giữa mock.ts (MockBackend) và mockData.ts (generator
// stateless). Tách ra để tránh import cycle khi mock.ts <-> mockData.ts cùng cần delay/uid/nowIso.

import type { SSEEnvelope } from '../types';

export const MOCK_LATENCY_MS = 220;

export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function uid(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

export function nowIso(): string {
  return new Date().toISOString();
}

export class ApiErrorLike extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function envelope<T>(convId: string, type: SSEEnvelope['type'], data: T, seq: number | null = null): SSEEnvelope<T> {
  return { type, conversation_id: convId, seq, ts: nowIso(), data };
}
