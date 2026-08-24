import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type {
  BankDigitalClient,
  ConversationFullState,
  ConversationStreamHandlers,
} from '../core/types'
import { BankDigitalApiError } from '../core/error'
import { CustomerAssistant, RmCopilot } from './variants'

const FULL_STATE: ConversationFullState = {
  conversation: {
    id: 'conv-1',
    title: 'Hồ sơ SME',
    status: 'idle',
    created_at: '2026-08-24T00:00:00Z',
  },
  messages: [
    {
      id: 'm1',
      conv_id: 'conv-1',
      ts: '2026-08-24T00:00:00Z',
      sender: 'assistant',
      content: 'Tờ trình đã sẵn sàng.',
    },
  ],
  tasks: [],
  cards: [
    {
      id: 'card-1',
      conv_id: 'conv-1',
      task_id: 'credit',
      type: 'document',
      ts: '2026-08-24T00:00:00Z',
      title: 'Tờ trình sơ thẩm',
      items: ['DSCR có nguồn'],
      sources: ['credit_assess'],
    },
  ],
}

function fakeClient(fullState: ConversationFullState = FULL_STATE): BankDigitalClient & {
  handlers: ConversationStreamHandlers | null
  close: ReturnType<typeof vi.fn>
  sendMessage: ReturnType<typeof vi.fn>
} {
  const close = vi.fn()
  const sendMessage = vi.fn().mockResolvedValue({ queued: true })
  const client = {
    handlers: null as ConversationStreamHandlers | null,
    close,
    sendMessage,
    me: vi.fn(),
    listConversations: vi.fn(),
    createConversation: vi.fn(),
    getConversation: vi.fn().mockResolvedValue(fullState),
    openConversationStream(_id: string, handlers: ConversationStreamHandlers) {
      client.handlers = handlers
      queueMicrotask(() => handlers.onOpen?.())
      return { close }
    },
  }
  return client
}

describe('embed variants', () => {
  it('renders the RM chat + canvas without importing approval controls', async () => {
    const client = fakeClient()
    const view = render(<RmCopilot client={client} conversationId="conv-1" />)
    expect(screen.getByText('Hỗ trợ sơ thẩm')).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('Kết quả sơ thẩm không phải phê duyệt')
    expect(screen.getByRole('note')).toHaveTextContent('Quyết định cuối cùng thuộc người có thẩm quyền')
    expect(await screen.findByText('Tờ trình đã sẵn sàng.')).toBeInTheDocument()
    expect(screen.getByText('Tờ trình sơ thẩm')).toBeInTheDocument()
    expect(screen.getByText('Tài liệu nghiệp vụ')).toBeInTheDocument()
    expect(screen.getByText(/Nguồn: Tín dụng/)).toBeInTheDocument()
    expect(screen.queryByText('document')).not.toBeInTheDocument()
    expect(screen.queryByText('credit_assess')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /duyệt|từ chối/i })).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Nội dung yêu cầu'), {
      target: { value: 'Kiểm tra lại nguồn' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Gửi' }))
    await waitFor(() => expect(client.sendMessage).toHaveBeenCalledWith('conv-1', 'Kiểm tra lại nguồn'))
    view.unmount()
    expect(client.close).toHaveBeenCalledOnce()
  })

  it('keeps the customer variant chat-only', async () => {
    const client = fakeClient()
    render(<CustomerAssistant client={client} conversationId="conv-1" />)
    expect(screen.getByText('Hỗ trợ hoàn thiện hồ sơ')).toBeInTheDocument()
    expect(await screen.findByText('Tờ trình đã sẵn sàng.')).toBeInTheDocument()
    expect(screen.queryByLabelText('Sản phẩm công việc')).not.toBeInTheDocument()
  })

  it('passes a host CSP nonce to the injected widget stylesheet', async () => {
    const client = fakeClient()
    const { container } = render(
      <RmCopilot client={client} conversationId="conv-1" styleNonce="bank-nonce" />,
    )
    await screen.findByText('Tờ trình đã sẵn sàng.')
    expect(container.querySelector('style')).toHaveAttribute('nonce', 'bank-nonce')
  })

  it('maps connection state to business copy without exposing transport literals', async () => {
    const client = fakeClient()
    render(<RmCopilot client={client} conversationId="conv-1" />)
    expect(await screen.findByText('Sẵn sàng · Đang kết nối')).toBeInTheDocument()

    act(() => client.handlers?.onStateChange?.({ state: 'reconnecting' }))
    expect(screen.getByText('Sẵn sàng · Đang đồng bộ lại')).toBeInTheDocument()
    expect(screen.queryByText(/reconnecting|open|closed/i)).not.toBeInTheDocument()
  })

  it('renders an unknown card safely without raw type, payload or JSON', async () => {
    const client = fakeClient({
      ...FULL_STATE,
      cards: [{
        id: 'card-unknown',
        conv_id: 'conv-1',
        task_id: null,
        type: 'raw_tool_payload',
        ts: '2026-08-24T00:00:00Z',
        title: 'raw tool details',
        items: [{ provider: 'secret-provider', nested: { token: 123 } }],
        sources: ['secret_internal_tool'],
      }],
    })
    render(<RmCopilot client={client} conversationId="conv-1" />)

    expect(await screen.findByText('Nội dung chưa hỗ trợ')).toBeInTheDocument()
    expect(screen.getByText(/mở hồ sơ trên hệ thống ngân hàng/)).toBeInTheDocument()
    expect(screen.queryByText(/raw_tool_payload|raw tool details|secret-provider|secret_internal_tool|"nested"/)).not.toBeInTheDocument()
  })

  it('preserves representative business fields for known cards with a safe structured fallback', async () => {
    const base = { conv_id: 'conv-1', task_id: null, ts: '2026-08-24T00:00:00Z' }
    const client = fakeClient({
      ...FULL_STATE,
      cards: [
        { ...base, id: 'metric', type: 'metric', items: [{ name: 'Biên giá', rate: '8,2%/năm', tenor: '12 tháng', fee: '0,5%', threshold: '≤ 9%', pass: true }] },
        { ...base, id: 'checklist', type: 'checklist', items: [{ item: 'Giấy phép kinh doanh', checked: true, note: 'Còn hiệu lực' }] },
        { ...base, id: 'options', type: 'options', items: [{ label: 'Phương án A', rate: '8,5%', tenor: '24 tháng', fee: 'Miễn phí' }] },
        { ...base, id: 'timeline', type: 'timeline', items: [{ step: 'Kiểm tra pháp lý', owner: 'Phòng Pháp chế', eta: '25/08/2026' }] },
        { ...base, id: 'document', type: 'document', items: [{ section: 'Đề xuất', content: 'Bổ sung tài sản bảo đảm', source: 'legal_check_docs' }] },
        { ...base, id: 'structured-document', type: 'document', items: [{ section: 'Kết quả', content: '{"approved_by":"auto-rule","tool":"ops_disburse"}' }] },
        { ...base, id: 'fallback', type: 'case_file', items: [{ internal_payload: { secret: 'không lộ' } }] },
      ],
    })
    render(<RmCopilot client={client} conversationId="conv-1" />)

    expect(await screen.findByText(/Lãi suất: 8,2%\/năm/)).toBeInTheDocument()
    expect(screen.getByText(/Kỳ hạn: 12 tháng/)).toBeInTheDocument()
    expect(screen.getByText(/Giấy phép kinh doanh.*Ghi chú: Còn hiệu lực.*Hoàn tất: Có/)).toBeInTheDocument()
    expect(screen.getByText(/Phương án A.*Phí: Miễn phí/)).toBeInTheDocument()
    expect(screen.getByText(/Bước: Kiểm tra pháp lý.*Phụ trách: Phòng Pháp chế.*Dự kiến: 25\/08\/2026/)).toBeInTheDocument()
    expect(screen.getByText(/Mục: Đề xuất.*Bổ sung tài sản bảo đảm.*Nguồn: Pháp lý/)).toBeInTheDocument()
    expect(screen.getByText(/Mục: Kết quả.*Chi tiết nghiệp vụ/)).toBeInTheDocument()
    expect(screen.getByText('Chi tiết nghiệp vụ')).toBeInTheDocument()
    expect(screen.queryByText(/internal_payload|secret|legal_check_docs|approved_by|auto-rule|ops_disburse|\{"/)).not.toBeInTheDocument()
  })

  it('fails closed for unknown source text, including whitespace and non-ASCII', async () => {
    const client = fakeClient({
      ...FULL_STATE,
      cards: [{
        id: 'source-card', conv_id: 'conv-1', task_id: null, type: 'document',
        ts: '2026-08-24T00:00:00Z',
        items: [
          { content: 'Căn cứ đã kiểm tra', source: 'provider secret' },
          { content: 'Nguồn thứ hai', source: 'nguồn bí mật' },
        ],
        sources: ['provider secret', 'nguồn bí mật'],
      }],
    })
    render(<RmCopilot client={client} conversationId="conv-1" />)

    expect((await screen.findAllByText(/Nguồn nghiệp vụ/)).length).toBeGreaterThan(0)
    expect(screen.queryByText(/provider secret|nguồn bí mật/i)).not.toBeInTheDocument()
  })

  it('sanitizes the exact manual approval shape without exposing gated identifiers', async () => {
    const client = fakeClient({
      ...FULL_STATE,
      cards: [{
        id: 'approval-card', conv_id: 'conv-1', task_id: null, type: 'approval',
        ts: '2026-08-24T00:00:00Z',
        title: 'Duyệt: disburse (loan_id=L001)',
        action: 'disburse',
        items: [
          { label: 'loan_id', value: 'L001' },
          { label: 'loan_amount_vnd', value: 500_000_000 },
          { label: 'action', value: 'disburse' },
          { action: 'ops_disburse', loan_id: 'L002', loan_amount_vnd: 700_000_000 },
        ],
      }],
    })
    render(<RmCopilot client={client} conversationId="conv-1" />)

    expect(await screen.findByRole('heading', { name: 'Trạng thái phê duyệt' })).toBeInTheDocument()
    expect(screen.getByText('Khoản vay: L001')).toBeInTheDocument()
    expect(screen.getByText('Số tiền: 500.000.000 ₫')).toBeInTheDocument()
    expect(screen.getByText('Hành động: Giải ngân')).toBeInTheDocument()
    expect(screen.getByText(/Hành động: Giải ngân.*Khoản vay: L002.*Số tiền: 700\.000\.000 ₫/)).toBeInTheDocument()
    expect(screen.queryByText(/disburse|loan_id|loan_amount_vnd/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /duyệt|từ chối/i })).not.toBeInTheDocument()
  })

  it('renders a deterministic card timestamp only when the ISO timestamp is valid', async () => {
    const valid = render(<RmCopilot client={fakeClient()} conversationId="conv-1" />)
    await screen.findByText('Tờ trình sơ thẩm')
    expect(valid.container.querySelector('time')).toHaveAttribute('datetime', '2026-08-24T00:00:00Z')
    expect(valid.container.querySelector('time')).toHaveTextContent('Cập nhật 2026-08-24 00:00')
    valid.unmount()

    const invalidClient = fakeClient({
      ...FULL_STATE,
      cards: [{ ...FULL_STATE.cards[0], ts: '2026-99-99T99:99:00Z' }],
    })
    const invalid = render(<RmCopilot client={invalidClient} conversationId="conv-1" />)
    await screen.findByText('Tờ trình sơ thẩm')
    expect(invalid.container.querySelector('time')).toBeNull()
  })

  it('keeps technical API errors out of the embedded notice', async () => {
    const client = fakeClient()
    client.getConversation = vi.fn().mockRejectedValue(
      new BankDigitalApiError(500, {
        code: 'provider_down',
        message: 'provider model token stacktrace',
        hint: 'Kiểm tra OPENAI_API_KEY và server log.',
        retryable: true,
      }),
    )
    render(<RmCopilot client={client} conversationId="conv-1" />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Không thể đồng bộ hồ sơ lúc này')
    expect(screen.queryByText(/provider|model|token|OPENAI_API_KEY|stacktrace/i)).not.toBeInTheDocument()
  })
})
