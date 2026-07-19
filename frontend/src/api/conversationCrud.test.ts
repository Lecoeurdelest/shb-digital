// conversationCrud.test.ts — S15 T15-2/3: mock updateConversation (rename + per-turn model) +
// deleteConversation với 409 hai loại (running / phiếu pending). Xác nhận error shape đọc được
// (status + message) — đường 409-hint FE (readApiError) dựa vào đây.
import { describe, it, expect } from 'vitest';
import { mockBackend } from './mock';

describe('mock conversation CRUD (T15-2/3)', () => {
  it('updateConversation: rename title', () => {
    const c = mockBackend.createConversation('Ca gốc');
    const updated = mockBackend.updateConversation(c.id, { title: 'Ca đổi tên' });
    expect(updated.title).toBe('Ca đổi tên');
    expect(mockBackend.getFullState(c.id).conversation.title).toBe('Ca đổi tên');
  });

  it('updateConversation: đổi provider+model (per-turn) khi idle → lưu', () => {
    const c = mockBackend.createConversation('Ca', 'claude-cli', 'haiku');
    const updated = mockBackend.updateConversation(c.id, { provider: 'zai', model: 'glm-4.6' });
    expect(updated.provider).toBe('zai');
    expect(updated.model).toBe('glm-4.6');
  });

  it('updateConversation model khi RUNNING → 409 (không đổi giữa lượt)', () => {
    const c = mockBackend.createConversation('Ca chạy');
    mockBackend.getFullState(c.id).conversation.status = 'running';
    try {
      mockBackend.updateConversation(c.id, { provider: 'zai', model: 'glm-4.6' });
      expect.unreachable('phải ném 409');
    } catch (e) {
      const err = e as { status?: number; message?: string };
      expect(err.status).toBe(409);
      expect(typeof err.message).toBe('string'); // FE readApiError đọc .message làm hint
    }
  });

  it('deleteConversation idle → xoá; getFullState sau đó 404', () => {
    const c = mockBackend.createConversation('Ca xoá');
    mockBackend.deleteConversation(c.id);
    expect(() => mockBackend.getFullState(c.id)).toThrow();
  });

  it('deleteConversation khi RUNNING → 409 hint (không xoá)', () => {
    const c = mockBackend.createConversation('Ca chạy');
    mockBackend.getFullState(c.id).conversation.status = 'running';
    try {
      mockBackend.deleteConversation(c.id);
      expect.unreachable('phải ném 409');
    } catch (e) {
      const err = e as { status?: number; message?: string };
      expect(err.status).toBe(409);
      expect(err.message).toMatch(/đang chạy/);
    }
    // vẫn còn (không xoá)
    expect(mockBackend.getFullState(c.id).conversation.id).toBe(c.id);
  });
});
