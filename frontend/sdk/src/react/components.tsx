import { useState, type FormEvent, type ReactNode } from 'react'
import { BankDigitalApiError } from '../core/error'
import type { Card } from '../core/types'
import { useBankConversation } from './ConversationContext'
import { bankDigitalStyles } from './styles'

const STATUS_LABELS = {
  idle: 'Sẵn sàng',
  running: 'Đang xử lý',
  waiting_approval: 'Chờ phê duyệt',
  done: 'Hoàn tất',
  failed: 'Lỗi',
} as const

const CONNECTION_LABELS = {
  connecting: 'Đang kết nối',
  open: 'Đã đồng bộ',
  reconnecting: 'Đang đồng bộ lại',
  closed: 'Tạm mất kết nối',
} as const

const CARD_TYPE_LABELS = {
  metric: 'Chỉ số sơ thẩm',
  checklist: 'Danh mục kiểm tra',
  options: 'Phương án đề xuất',
  timeline: 'Tiến độ xử lý',
  case_file: 'Thông tin hồ sơ',
  document: 'Tài liệu nghiệp vụ',
  approval: 'Trạng thái phê duyệt',
  form: 'Thông tin cần bổ sung',
} as const

type KnownCardType = keyof typeof CARD_TYPE_LABELS

const USER_VISIBLE_ERROR_CODES = new Set([
  'bad_username',
  'bad_password',
  'bad_email',
  'username_taken',
  'missing_fields',
  'bad_income',
  'form_already_submitted',
  'already_decided',
  'conversation_busy',
  'approval_pending',
])

const APPROVAL_FIELD_LABELS: Record<string, string> = {
  action: 'Hành động',
  loan_id: 'Khoản vay',
  loan_amount_vnd: 'Số tiền',
  amount: 'Số tiền',
  owner_id: 'Khách hàng',
  customer_id: 'Khách hàng',
  'khoản vay': 'Khoản vay',
  'số tiền': 'Số tiền',
  'khách hàng': 'Khách hàng',
  'hành động': 'Hành động',
}

const ITEM_FIELD_LABELS: Record<string, string> = {
  label: '',
  name: '',
  title: '',
  item: '',
  section: 'Mục',
  content: '',
  detail: '',
  note: 'Ghi chú',
  description: '',
  value: 'Giá trị',
  rate: 'Lãi suất',
  tenor: 'Kỳ hạn',
  fee: 'Phí',
  threshold: 'Ngưỡng',
  step: 'Bước',
  owner: 'Phụ trách',
  eta: 'Dự kiến',
  date: 'Thời điểm',
  amount: 'Số tiền',
  action: 'Hành động',
  recommendation: 'Đề xuất',
  reason: 'Căn cứ',
  status: 'Trạng thái',
  pass: 'Đạt',
  checked: 'Hoàn tất',
  selected: 'Được chọn',
  required: 'Bắt buộc',
  source: 'Nguồn',
}

export interface FrameProps {
  children: ReactNode
  className?: string
  variant?: 'customer' | 'rm'
  styleNonce?: string
}

export function Frame({ children, className = '', variant = 'customer', styleNonce }: FrameProps) {
  const classes = ['bd-embed', 'bd-frame', variant === 'rm' ? 'bd-frame--rm' : '', className]
    .filter(Boolean)
    .join(' ')
  return (
    <section className={classes} data-bank-digital-embed={variant}>
      <style nonce={styleNonce}>{bankDigitalStyles}</style>
      {children}
    </section>
  )
}

export interface HeaderProps {
  children?: ReactNode
  heading?: string
}

export function Header({ children, heading = 'Hỗ trợ hồ sơ' }: HeaderProps) {
  return (
    <header className="bd-header">
      <span>{heading}</span>
      {children ?? <Status />}
    </header>
  )
}

export function Status() {
  const { state } = useBankConversation()
  const status = state.conversation?.status
  const label = status ? STATUS_LABELS[status] : state.loading ? 'Đang tải' : 'Chưa có dữ liệu'
  return (
    <span className="bd-status" role="status">
      <span className={`bd-status__dot bd-status__dot--${state.connection}`} />
      {label} · {CONNECTION_LABELS[state.connection]}
    </span>
  )
}

export interface MessagesProps {
  emptyText?: string
  renderMessage?: (message: {
    id: string
    sender: 'user' | 'assistant' | 'system'
    content: string
    streaming: boolean
  }) => ReactNode
}

export function Messages({ emptyText = 'Chưa có hội thoại.', renderMessage }: MessagesProps) {
  const { state } = useBankConversation()
  const rows = [
    ...state.messages.map((message) => ({ ...message, streaming: false })),
    ...(state.streaming
      ? [
          {
            id: `stream_${state.streaming.turnId}`,
            sender: 'assistant' as const,
            content: state.streaming.text,
            streaming: true,
          },
        ]
      : []),
  ]
  return (
    <div className="bd-messages" aria-live="polite" aria-busy={state.loading}>
      {rows.length === 0 ? <div className="bd-empty">{state.loading ? 'Đang tải…' : emptyText}</div> : null}
      {rows.map((message) =>
        renderMessage ? (
          <div key={message.id}>{renderMessage(message)}</div>
        ) : (
          <div
            key={message.id}
            className={`bd-message bd-message--${message.sender}${message.streaming ? ' bd-stream-cursor' : ''}`}
          >
            {message.content}
          </div>
        ),
      )}
    </div>
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function primitiveLabel(value: unknown): string | null {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    if (typeof value === 'boolean') return value ? 'Có' : 'Không'
    return String(value)
  }
  return null
}

function businessPrimitiveLabel(value: unknown): string | null {
  const rendered = primitiveLabel(value)
  if (typeof value !== 'string') return rendered

  const candidate = value.trim()
  if (!candidate.startsWith('{') && !candidate.startsWith('[')) return rendered
  try {
    const parsed: unknown = JSON.parse(candidate)
    if (typeof parsed === 'object' && parsed !== null) return 'Chi tiết nghiệp vụ'
  } catch {
    // Chuỗi văn bản có dấu ngoặc vẫn là nội dung nghiệp vụ; chỉ ẩn JSON có cấu trúc hợp lệ.
  }
  return rendered
}

function approvalActionLabel(value: unknown): string | null {
  const rendered = primitiveLabel(value)
  if (rendered === null) return null
  const normalized = rendered.trim().toLowerCase()
  if (normalized === 'disburse' || normalized === 'ops_disburse' || normalized === 'giải ngân') return 'Giải ngân'
  return 'Hành động nghiệp vụ'
}

function approvalFieldLabel(value: unknown): string {
  const rendered = primitiveLabel(value)?.trim().toLowerCase() ?? ''
  return APPROVAL_FIELD_LABELS[rendered] ?? 'Thông tin'
}

function approvalValue(field: string, value: unknown): string {
  if (field === 'action') return approvalActionLabel(value) ?? 'Hành động nghiệp vụ'
  if ((field === 'loan_amount_vnd' || field === 'amount') && typeof value === 'number') {
    return `${value.toLocaleString('vi-VN')} ₫`
  }
  return primitiveLabel(value) ?? 'Chi tiết nghiệp vụ'
}

function displayApprovalItem(value: unknown): string {
  if (!isRecord(value)) return approvalActionLabel(value) ?? 'Thông tin phê duyệt'

  if ('label' in value && 'value' in value) {
    const field = primitiveLabel(value.label)?.trim().toLowerCase() ?? ''
    return `${approvalFieldLabel(value.label)}: ${approvalValue(field, value.value)}`
  }

  const parts: string[] = []
  for (const field of ['action', 'loan_id', 'loan_amount_vnd', 'amount', 'owner_id', 'customer_id']) {
    if (!(field in value)) continue
    parts.push(`${APPROVAL_FIELD_LABELS[field]}: ${approvalValue(field, value[field])}`)
  }
  return parts.length > 0 ? parts.join(' · ') : 'Thông tin phê duyệt'
}

function displayItem(value: unknown, cardType: KnownCardType): string | null {
  if (cardType === 'approval') return displayApprovalItem(value)
  const primitive = businessPrimitiveLabel(value)
  if (primitive !== null) return primitive
  if (value === null || value === undefined) return '—'
  if (Array.isArray(value)) {
    const items = value.map(businessPrimitiveLabel).filter((item): item is string => item !== null)
    return items.length > 0 ? items.join(' · ') : 'Chi tiết nghiệp vụ'
  }
  if (!isRecord(value)) return null

  const parts: string[] = []
  for (const [field, label] of Object.entries(ITEM_FIELD_LABELS)) {
    const raw = value[field]
    const rendered = field === 'source' && typeof raw === 'string'
      ? sourceLabel(raw)
      : businessPrimitiveLabel(raw)
    if (rendered === null || rendered.trim() === '') continue
    parts.push(label ? `${label}: ${rendered}` : rendered)
  }
  return parts.length > 0 ? parts.join(' · ') : 'Chi tiết nghiệp vụ'
}

function isKnownCardType(type: string): type is KnownCardType {
  return Object.hasOwn(CARD_TYPE_LABELS, type)
}

function sourceLabel(source: string): string {
  const normalized = source.toLowerCase()
  if (normalized.startsWith('credit')) return 'Tín dụng'
  if (normalized.startsWith('legal')) return 'Pháp lý'
  if (normalized.startsWith('product')) return 'Sản phẩm'
  if (normalized.startsWith('operation')) return 'Vận hành'
  if (normalized.startsWith('cic')) return 'Thông tin tín dụng'
  if (normalized.startsWith('core')) return 'Hệ thống lõi'
  return 'Nguồn nghiệp vụ'
}

function cardTimestamp(ts: string | undefined): { dateTime: string; label: string } | null {
  if (!ts) return null
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:(Z)|([+-])(\d{2}):(\d{2}))?$/.exec(ts)
  if (!match) return null
  const [, year, month, day, hour, minute, second, , , offsetHour, offsetMinute] = match
  const y = Number(year)
  const m = Number(month)
  const d = Number(day)
  const h = Number(hour)
  const min = Number(minute)
  const sec = second === undefined ? 0 : Number(second)
  const zoneHour = offsetHour === undefined ? 0 : Number(offsetHour)
  const zoneMinute = offsetMinute === undefined ? 0 : Number(offsetMinute)
  const maxDay = m >= 1 && m <= 12 ? new Date(Date.UTC(y, m, 0)).getUTCDate() : 0
  if (y < 1000 || d < 1 || d > maxDay || h > 23 || min > 59 || sec > 59 || zoneHour > 23 || zoneMinute > 59) return null
  return { dateTime: ts, label: `${year}-${month}-${day} ${hour}:${minute}` }
}

function DefaultCard({ card }: { card: Card }) {
  const updated = cardTimestamp(card.ts)
  if (!isKnownCardType(card.type)) {
    return (
      <article className="bd-card" data-card-type="unsupported">
        <div className="bd-card__type">Thông tin hồ sơ</div>
        <h3>Nội dung chưa hỗ trợ</h3>
        {updated ? <time dateTime={updated.dateTime}>Cập nhật {updated.label}</time> : null}
        <p>Vui lòng mở hồ sơ trên hệ thống ngân hàng để xem chi tiết.</p>
      </article>
    )
  }

  const cardType = card.type
  const items = (card.items ?? [])
    .map((item) => displayItem(item, cardType))
    .filter((item): item is string => item !== null)
  const sources = [...new Set((card.sources ?? []).map(sourceLabel))]
  return (
    <article className="bd-card" data-card-type={cardType}>
      <div className="bd-card__type">{CARD_TYPE_LABELS[cardType]}</div>
      <h3>{cardType === 'approval' ? CARD_TYPE_LABELS.approval : card.title ?? CARD_TYPE_LABELS[cardType]}</h3>
      {updated ? <time dateTime={updated.dateTime}>Cập nhật {updated.label}</time> : null}
      {items.length > 0 ? (
        <ul>{items.map((item, index) => <li key={`${card.id}_${index}`}>{item}</li>)}</ul>
      ) : null}
      {sources.length > 0 ? (
        <div className="bd-card__sources">Nguồn: {sources.join(' · ')}</div>
      ) : null}
    </article>
  )
}

export interface CardsProps {
  emptyText?: string
  renderCard?: (card: Card) => ReactNode
}

export function Cards({ emptyText = 'Chưa có sản phẩm công việc.', renderCard }: CardsProps) {
  const { state } = useBankConversation()
  return (
    <aside className="bd-cards" aria-label="Sản phẩm công việc">
      {state.cards.length === 0 ? <div className="bd-empty">{emptyText}</div> : null}
      {state.cards.map((card) => (
        <div key={card.id}>{renderCard ? renderCard(card) : <DefaultCard card={card} />}</div>
      ))}
    </aside>
  )
}

export interface ComposerProps {
  placeholder?: string
  submitLabel?: string
}

export function Composer({ placeholder = 'Nhập yêu cầu…', submitLabel = 'Gửi' }: ComposerProps) {
  const { state, actions } = useBankConversation()
  const [value, setValue] = useState('')
  const busy = state.sending || state.conversation?.status === 'running'

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const content = value.trim()
    if (!content || busy) return
    void actions.sendMessage(content).then(() => setValue('')).catch(() => undefined)
  }

  return (
    <form className="bd-composer" onSubmit={submit}>
      <input
        aria-label="Nội dung yêu cầu"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={placeholder}
        disabled={busy}
      />
      <button type="submit" disabled={busy || !value.trim()}>{submitLabel}</button>
    </form>
  )
}

function errorMessage(error: unknown): string {
  if (error instanceof BankDigitalApiError) {
    if (error.status === 401) return 'Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.'
    if (error.status === 403) return 'Bạn không có quyền thực hiện thao tác này.'
    if (error.body?.message && USER_VISIBLE_ERROR_CODES.has(error.body.code)) return error.body.message
    if (error.body?.message && (error.status === 400 || error.status === 409)) return error.body.message
    return 'Không thể đồng bộ hồ sơ lúc này. Vui lòng thử lại sau.'
  }
  return 'Không thể đồng bộ hồ sơ lúc này. Vui lòng thử lại sau.'
}

export function ErrorNotice() {
  const { state, actions } = useBankConversation()
  if (!state.error) return null
  return (
    <div className="bd-error" role="alert">
      {errorMessage(state.error)}
      <button type="button" onClick={actions.clearError} aria-label="Đóng thông báo lỗi">×</button>
    </div>
  )
}
