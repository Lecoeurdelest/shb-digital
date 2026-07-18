// ApprovalPanel.tsx — card approval (VỎ tự sinh từ wrapper phanh §4.4/§6). Nút Duyệt/Từ chối +
// ô lý do → onDecide(approvalId, decision, reason) → POST /api/approvals/{id}/decide (id phiếu VỎ-inject).
// Phiếu quyết rồi → KHÔNG xoá card (bằng chứng §6), chuyển badge trạng thái. D-40 happy-path.
// Shape (T3-1 §E): type='approval', data {action, items:[{label,value}], options}. Phiếu-id: field
// vỏ-inject trên card (approval_id / phieu_id / id) — đọc defensive nhiều tên (chờ backend chốt).
import { useState } from 'react';
import type { Card } from '../../types';
import { cardItems, cardField, itemField, renderValue } from './cardUtil';
import './ApprovalPanel.css';

// decision value CHỐT theo backend T3-2: "approved" | "rejected" (KHÔNG "approve"/"reject" → 400).
export type ApprovalDecision = 'approved' | 'rejected';
export type DecideFn = (approvalId: string, decision: ApprovalDecision, reason: string) => void;

// phiếu-id vỏ-inject: CHỐT `card.approval_id` = approvals.id (backend T3-1, tách rõ khỏi card.id).
// POST /api/approvals/{approval_id}/decide.
function approvalId(card: Card): string | null {
  const id = cardField<string>(card, 'approval_id');
  return typeof id === 'string' && id ? id : null;
}

// trạng thái phiếu: pending | approved | rejected | used (từ card.status hoặc card.state vỏ set).
function approvalStatus(card: Card): string {
  const s = cardField<string>(card, 'status') ?? cardField<string>(card, 'state') ?? 'pending';
  return String(s);
}

// canDecide (D-56): chỉ NGÂN HÀNG (admin) thấy nút ✓/✗. Khách (customer) thấy phiếu pending dạng
// "⏳ Đang chờ ngân hàng phê duyệt" — không quyết được (backend cũng 403 nếu cố). Default true để
// giữ backward (test/chỗ cũ chưa truyền role = hành vi admin như trước D-56).
export function ApprovalPanel({ card, onDecide, canDecide = true }: { card: Card; onDecide?: DecideFn; canDecide?: boolean }) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const items = cardItems(card);
  const status = approvalStatus(card);
  const id = approvalId(card);
  const action = renderValue(cardField(card, 'action') ?? 'Hành động cần duyệt');
  const pending = status === 'pending';

  const decide = (decision: ApprovalDecision) => {
    if (!onDecide || !id || busy) return;
    setBusy(true);
    onDecide(id, decision, reason.trim());
    // busy giữ tới khi SSE approval.decided cập nhật card → re-render sang trạng thái đã-quyết.
  };

  return (
    <div className="approval">
      <div className="approval__head">
        <span className="approval__icon" aria-hidden="true">🔒</span>
        <span className="approval__action">{action}</span>
        <ApprovalBadge status={status} />
      </div>

      {items.length > 0 && (
        <div className="approval__items">
          {items.map((it, i) => (
            <div key={i} className="approval__item">
              <span className="approval__label">{renderValue(itemField(it, 'label') ?? itemField(it, 'name'))}</span>
              <span className="approval__value">{renderValue(itemField(it, 'value'))}</span>
            </div>
          ))}
        </div>
      )}

      {pending && !canDecide ? (
        // khách hàng: phiếu chờ ngân hàng — không có nút quyết (D-56)
        <div className="approval__waiting" data-testid="approval-waiting">
          ⏳ Đang chờ ngân hàng phê duyệt
        </div>
      ) : pending ? (
        <div className="approval__actions">
          <textarea
            className="approval__reason"
            placeholder="Lý do (bắt buộc khi Từ chối — khách sẽ nhận được)…"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            aria-label="Lý do quyết định"
            disabled={busy}
          />
          <div className="approval__btns">
            <button
              type="button"
              className="btn btn--ok approval__btn"
              onClick={() => decide('approved')}
              disabled={busy || !id || !onDecide}
              data-testid="approval-approve"
            >
              {busy ? 'Đang gửi…' : '✓ Duyệt'}
            </button>
            <button
              type="button"
              className="btn btn--danger approval__btn"
              onClick={() => decide('rejected')}
              disabled={busy || !id || !onDecide || !reason.trim()}
              data-testid="approval-reject"
              title={!reason.trim() ? 'Nhập lý do từ chối trước' : undefined}
            >
              ✗ Từ chối
            </button>
          </div>
          {!id && <div className="approval__warn">Thiếu mã phiếu — không thể quyết (chờ vỏ inject id).</div>}
        </div>
      ) : (
        <div className="approval__resolved">
          {decidedText(card, status)}
        </div>
      )}
    </div>
  );
}

function ApprovalBadge({ status }: { status: string }) {
  const map: Record<string, { cls: string; label: string }> = {
    pending: { cls: 'badge--warn', label: 'CHỜ DUYỆT' },
    approved: { cls: 'badge--pass', label: '✓ ĐÃ DUYỆT' },
    used: { cls: 'badge--pass', label: '✓ ĐÃ DÙNG' },
    rejected: { cls: 'badge--fail', label: '✗ TỪ CHỐI' },
  };
  const m = map[status] ?? { cls: 'badge--warn', label: status.toUpperCase() };
  return <span className={`badge ${m.cls} approval__badge`}>{m.label}</span>;
}

// dòng mô tả sau khi quyết (bằng chứng — §6). decided_by/reason vỏ set trên card nếu có.
function decidedText(card: Card, status: string): string {
  const by = cardField<string>(card, 'decided_by');
  const reason = cardField<string>(card, 'reason');
  const base =
    status === 'rejected'
      ? 'Phiếu bị từ chối — Main dừng hành động, RM được thông báo.'
      : 'Phiếu đã duyệt — hành động thực thi, biên nhận đã lưu.';
  const who = by ? ` Bởi: ${by}.` : '';
  const why = reason ? ` Lý do: ${reason}.` : '';
  return base + who + why;
}
