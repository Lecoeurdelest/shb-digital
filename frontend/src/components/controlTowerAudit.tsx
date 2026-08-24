import type { AuditRow } from '../types';
import { roleLabel } from '../roles';
import { fmtApprovalVnd, shortId } from './controlTowerFormat';

const TOOL_LABELS: Record<string, string> = {
  disburse: 'Chuẩn bị giải ngân',
  credit_assess: 'Đánh giá tín dụng',
  present: 'Lập bản trình bày',
  calc: 'Tính toán chỉ tiêu',
  first: 'Bước xử lý đầu',
  second: 'Bước xử lý tiếp theo',
};

export function AuditFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="ct__audit-fact">
      <span className="ct__audit-fact-label">{label}</span>
      <span className="ct__audit-fact-value">{value}</span>
    </div>
  );
}

export function auditActionLabel(row: AuditRow): string {
  const label = TOOL_LABELS[row.tool] ?? 'Ghi nhận hoạt động xử lý';
  return `${auditActorLabel(row.actor)} · ${label}`;
}

export function auditActorLabel(actor: string): string {
  if (actor === 'main' || actor === 'planner') return 'Điều phối';
  if (actor === 'operations') return 'Vận hành';
  return roleLabel(actor);
}

export function auditBusinessDetail(row: AuditRow): string {
  const input = row.input ?? {};
  const parts: string[] = [];
  const ownerId = stringValue(input.owner_id ?? input.customer_id ?? input.cif);
  const loanId = stringValue(input.loan_id ?? input.loan);
  const amount = numberValue(input.amount_vnd ?? input.amount ?? input.loan_amount_vnd);

  if (ownerId) parts.push(`Khách ${ownerId}`);
  if (loanId) parts.push(`Khoản vay ${loanId}`);
  if (amount != null) parts.push(`Số tiền ${fmtApprovalVnd(amount)}`);

  if (parts.length > 0) return parts.join(' · ');
  return 'Đã ghi nhận hoạt động trong phiên xử lý.';
}

export function auditInputSummary(row: AuditRow): string {
  const input = asRecord(row.input);
  if (!input) return 'Không có tham số đầu vào.';

  const parts: string[] = [];
  const ownerId = stringValue(input.owner_id ?? input.customer_id ?? input.cif);
  const loanId = stringValue(input.loan_id ?? input.loan);
  const role = stringValue(input.role);
  const action = stringValue(input.action);
  const title = stringValue(input.title);
  const query = stringValue(input.query ?? input.keyword ?? input.q);
  const amount = numberValue(input.amount_vnd ?? input.amount ?? input.loan_amount_vnd);

  if (ownerId) parts.push(`khách ${ownerId}`);
  if (loanId) parts.push(`khoản vay ${loanId}`);
  if (amount != null) parts.push(fmtApprovalVnd(amount));
  if (role) parts.push(`chuyên gia ${auditActorLabel(role)}`);
  if (action) parts.push(`hành động ${actionLabel(action)}`);
  if (title) parts.push(title);
  if (query) parts.push(`tìm "${query}"`);

  if (parts.length > 0) return parts.join(' · ');
  const count = Object.keys(input).length;
  return count > 0 ? `${count} tham số đầu vào đã được ghi nhận.` : 'Không có tham số đầu vào.';
}

export function auditOutputSummary(row: AuditRow): string {
  const output: unknown = row.output;
  if (output == null) return 'Chưa có kết quả trả về.';
  if (typeof output === 'string') return output.trim() ? output.trim().slice(0, 120) : 'Kết quả rỗng.';
  if (typeof output === 'number' || typeof output === 'boolean') return String(output);

  const out = asRecord(output);
  if (!out) return 'Kết quả đã được ghi nhận.';

  const error = asRecord(out.error);
  const item = asRecord(out.item);
  const receipt = asRecord(out.receipt);
  const parts: string[] = [];

  const message = stringValue(out.message ?? out.summary ?? out.title ?? error?.message);
  const status = stringValue(out.status ?? item?.status ?? receipt?.status);
  const lane = stringValue(out.lane ?? item?.lane);
  const decision = stringValue(out.decision ?? item?.decision);
  const approvalId = stringValue(out.approval_id);
  const assessmentId = stringValue(out.assessment_id ?? item?.assessment_id ?? item?.id);
  const receiptId = stringValue(out.receipt_id ?? receipt?.id ?? receipt?.receipt_id);
  const reason = stringValue(out.reason ?? item?.reason ?? error?.hint);

  if (message) parts.push(message);
  if (status) parts.push(`trạng thái ${status}`);
  if (lane) parts.push(`lane ${lane.toUpperCase()}`);
  if (decision) parts.push(`khuyến nghị ${decision}`);
  if (approvalId) parts.push(`phiếu ${shortId(approvalId)}`);
  if (assessmentId) parts.push(`thẩm định ${shortId(assessmentId)}`);
  if (receiptId) parts.push(`biên nhận ${shortId(receiptId)}`);
  if (reason) parts.push(reason);

  if (parts.length > 0) return parts.join(' · ');
  const keys = Object.keys(out).length;
  return keys > 0 ? `${keys} trường kết quả đã được lưu.` : 'Kết quả rỗng.';
}

export function auditCostSummary(row: AuditRow): string | null {
  const cost = asRecord(row.cost);
  if (!cost) return null;
  const parts: string[] = [];
  const usd = numberValue(cost.cost_usd ?? cost.usd ?? cost.total_cost_usd);
  const duration = numberValue(cost.duration_ms);
  const totalTokens = numberValue(cost.total_tokens);
  const inputTokens = numberValue(cost.input_tokens);
  const outputTokens = numberValue(cost.output_tokens);

  if (usd != null) parts.push(`$${usd.toFixed(4)}`);
  if (duration != null) parts.push(`${Math.round(duration)}ms`);
  if (totalTokens != null) parts.push(`${totalTokens.toLocaleString('vi-VN')} token`);
  else if (inputTokens != null || outputTokens != null) {
    parts.push(`${(inputTokens ?? 0).toLocaleString('vi-VN')} vào / ${(outputTokens ?? 0).toLocaleString('vi-VN')} ra`);
  }
  return parts.length > 0 ? parts.join(' · ') : null;
}

function actionLabel(action: string): string {
  return TOOL_LABELS[action] ?? action;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function stringValue(value: unknown): string {
  return typeof value === 'string' && value.trim() ? value.trim() : '';
}

function numberValue(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) return Number(value);
  return null;
}
