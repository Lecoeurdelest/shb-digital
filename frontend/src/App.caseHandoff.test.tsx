import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { conversationApi } from './api';
import type { CaseSummary, Conversation, ConversationFullState } from './types';

const TARGET_ID = 'conv-shadow-linked-002';
const targetConversation: Conversation = {
  id: TARGET_ID,
  title: 'Phiên xử lý hồ sơ SAHA-RL-002',
  status: 'idle',
  created_at: '2026-08-24T09:31:00+07:00',
};
const otherConversation: Conversation = {
  id: 'conv-other',
  title: 'Phiên xử lý khác',
  status: 'idle',
  created_at: '2026-08-24T09:30:00+07:00',
};
const targetState: ConversationFullState = {
  conversation: targetConversation,
  messages: [],
  tasks: [],
  cards: [],
};
const linkedCase: CaseSummary = {
  id: 'case-linked', source_system: 'saha', external_case_id: 'SAHA-RL-002',
  internal_application_id: null, party_reference: 'CIF-002', product_code: 'RETAIL_MORTGAGE',
  loan_amount_vnd: 1_800_000_000, case_status: 'ready_for_preassessment',
  next_action: 'Mở phiên xử lý để bắt đầu sơ thẩm.', document_count: 7, missing_fields: [],
  source_version: 5, data_as_of: '2026-08-24T09:30:00+07:00',
  synced_at: '2026-08-24T09:31:00+07:00', conversation_id: TARGET_ID,
  assessment: { lane: null, created_at: null },
};

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(null, '', '/');
});

describe('App case conversation handoff (D-77)', () => {
  it('Tower mở đúng existing conversation một lần rồi xóa handoff, không tạo/chạy/quyết định', async () => {
    window.history.replaceState(null, '', '/');
    vi.spyOn(conversationApi, 'me').mockResolvedValue({
      user: { username: 'admin', role: 'admin', owner_id: null },
    });
    vi.spyOn(conversationApi, 'listApprovals').mockResolvedValue([]);
    vi.spyOn(conversationApi, 'listConversations').mockResolvedValue([otherConversation, targetConversation]);
    vi.spyOn(conversationApi, 'getStats').mockResolvedValue({
      window: '24h', approvals: { approved: 0, rejected: 0, pending: 0, auto: 0 },
      assessments: { green: 0, yellow: 0, red: 0 }, conversations: { total: 2, active: 0 },
      delta: { approvals_total: 0, assessments_total: 0 },
    });
    vi.spyOn(conversationApi, 'listCases').mockResolvedValue([linkedCase]);
    const getConversation = vi.spyOn(conversationApi, 'getConversation').mockResolvedValue(targetState);
    vi.spyOn(conversationApi, 'openEventSource').mockImplementation(() => ({
      onopen: null,
      onmessage: null,
      onerror: null,
      close: vi.fn(),
    }));
    const createConversation = vi.spyOn(conversationApi, 'createConversation');
    const sendChat = vi.spyOn(conversationApi, 'sendChat');
    const decideApproval = vi.spyOn(conversationApi, 'decideApproval');

    render(<App />);
    fireEvent.click(await screen.findByTestId('open-tower'));
    fireEvent.click(await screen.findByRole('button', { name: 'Cơ sở sơ thẩm' }));
    const openLinked = await screen.findByRole('button', { name: 'Mở phiên xử lý' });
    expect(document.body).not.toHaveTextContent(TARGET_ID);
    fireEvent.click(openLinked);

    await waitFor(() => expect(getConversation).toHaveBeenCalledWith(TARGET_ID));
    expect(screen.getByText(targetConversation.title, { selector: '.ws__chat-title' })).toBeInTheDocument();
    expect(getConversation).toHaveBeenCalledTimes(1);
    expect(document.body).not.toHaveTextContent(TARGET_ID);
    expect(createConversation).not.toHaveBeenCalled();
    expect(sendChat).not.toHaveBeenCalled();
    expect(decideApproval).not.toHaveBeenCalled();
    expect(window.location.pathname + window.location.search).toBe('/');

    // Remount Workspace qua Tower/back: handoff đã được App xóa nên không fetch target lần hai.
    fireEvent.click(screen.getByTestId('open-tower'));
    fireEvent.click(await screen.findByRole('button', { name: '← Workspace' }));
    await screen.findByTestId('open-tower');
    await waitFor(() => expect(getConversation).toHaveBeenCalledTimes(1));
  });
});
