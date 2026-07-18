// ControlTower.tsx — màn admin (deliverable #4 · SPEC §12/§13). 4 khối: approval queue (duyệt tại
// chỗ) · audit view (filter) · cost meter (tasks.cost per-turn) · trạng thái agent (conv/tasks).
// Data: GET /api/approvals?pending · GET /api/audit?filters · GET /api/conversations. Admin (D-19).
// Look-and-feel tham khảo design/Digital Expert Guild.dc.html Tower (D-13).
import { useCallback, useEffect, useState } from 'react';
import { conversationApi } from '../api';
import { ApiRequestError } from '../api/client';
import { useApprovalBadge } from '../hooks/useApprovalBadge';
import { ThemeToggle } from './ThemeToggle';
import { StatsOverview } from './stats/StatsOverview';
import { AssessmentsView } from './stats/AssessmentsView';
import { roleLabel } from '../roles';
import type { ApprovalRow, AuditRow, CompareResult, CompareSide, Conversation } from '../types';
import './ControlTower.css';

type Tab = 'overview' | 'queue' | 'assessments' | 'audit' | 'agents' | 'compare';

const TAB_LABEL: Record<Tab, string> = {
  overview: 'Tổng quan',
  queue: 'Hàng chờ duyệt',
  assessments: 'Hồ sơ + lý do AI',
  audit: 'Nhật ký tool',
  agents: 'Trạng thái đội',
  compare: 'So sánh 1 vs đội',
};
const TAB_ORDER: Tab[] = ['overview', 'queue', 'assessments', 'audit', 'agents', 'compare'];

export function ControlTower({ onBack }: { onBack: () => void }) {
  const [tab, setTab] = useState<Tab>('overview'); // T13-2: Tổng quan là tab ĐẦU, default
  // ControlTower chỉ render cho admin (App gate) → poll badge phiếu-bay luôn bật. Số nổi trên tab queue.
  const pending = useApprovalBadge(true);
  return (
    <div className="ct">
      <header className="ct__head">
        <button type="button" className="ct__back" onClick={onBack}>← Workspace</button>
        <span className="ct__title">🗼 Control Tower</span>
        <span className="ct__sub">Giám sát · phê duyệt · nhật ký — quản lý</span>
        <ThemeToggle />
        <div className="ct__tabs">
          {TAB_ORDER.map((t) => (
            <button
              key={t}
              type="button"
              className={`ct__tab${tab === t ? ' ct__tab--active' : ''}`}
              onClick={() => setTab(t)}
            >
              {TAB_LABEL[t]}
              {t === 'queue' && pending > 0 && (
                <span className="ct__tab-badge" data-testid="ct-queue-badge">{pending}</span>
              )}
            </button>
          ))}
        </div>
      </header>

      <div className="ct__body" data-scroll>
        {tab === 'overview' && <StatsOverview />}
        {tab === 'queue' && <ApprovalQueue />}
        {tab === 'assessments' && <AssessmentsView />}
        {tab === 'audit' && <AuditView />}
        {tab === 'agents' && <AgentStatus />}
        {tab === 'compare' && <CompareView />}
      </div>
    </div>
  );
}

// ── Khối 1: Approval queue — list phiếu pending + duyệt tại chỗ ──
function ApprovalQueue() {
  const [rows, setRows] = useState<ApprovalRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  // DF-B-07: từ chối 2 bước — bấm "✗ Từ chối" → expand ô lý do (BẮT BUỘC). Duyệt vẫn 1 click.
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const load = useCallback(() => {
    conversationApi
      .listApprovals('pending')
      .then((r) => { setRows(r); setError(null); })
      .catch((e: unknown) => setError(e instanceof ApiRequestError ? e.body?.message ?? 'Lỗi tải hàng chờ' : 'Lỗi tải hàng chờ'));
  }, []);

  useEffect(() => { load(); }, [load]);

  // gửi quyết định (reason: duyệt='' optional; từ chối = lý do bắt buộc từ ô expand).
  const submitDecision = (row: ApprovalRow, decision: 'approved' | 'rejected', reason: string) => {
    setBusyId(row.id);
    conversationApi
      .decideApproval(row.id, decision, reason)
      .then(() => { setRows((prev) => prev.filter((r) => r.id !== row.id)); setRejectingId(null); setRejectReason(''); })
      .catch((e: unknown) => {
        if (e instanceof ApiRequestError && e.status === 409) { setRows((prev) => prev.filter((r) => r.id !== row.id)); setRejectingId(null); setRejectReason(''); }
        else setError('Quyết phiếu thất bại');
      })
      .finally(() => setBusyId(null));
  };

  // bấm "✗ Từ chối" → mở ô lý do cho phiếu này (collapse phiếu khác đang mở). Chưa gửi.
  const openReject = (row: ApprovalRow) => { setRejectingId(row.id); setRejectReason(''); setError(null); };
  const cancelReject = () => { setRejectingId(null); setRejectReason(''); };

  return (
    <div className="ct__section">
      <div className="ct__section-head">
        <span className="ct__section-title">Hàng chờ phê duyệt ({rows.length})</span>
        <button type="button" className="ct__refresh" onClick={load}>⟳ Tải lại</button>
      </div>
      {error && <div className="ct__error">{error}</div>}
      {rows.length === 0 ? (
        <div className="ct__empty" data-testid="queue-empty">Không có phiếu nào chờ duyệt.</div>
      ) : (
        <div className="ct__rows">
          {rows.slice(0, 50).map((row) => {
            const d = row.display ?? null;
            // DF-B-01: tên khách (fallback owner_id → shortId conv) · tiền VNĐ · loan · lane-chip.
            // display vắng (BE chưa deploy) → fallback shortId+JSON như cũ (không vỡ, backward).
            const who = d?.customer_name || d?.owner_id || shortId(row.conv_id);
            const rejecting = rejectingId === row.id;
            return (
              <div key={row.id} className="ct__appr-wrap" data-testid={`queue-row-${row.id}`}>
                <div className="ct__appr-row">
                  <span className="ct__appr-action">🔒 {row.action}</span>
                  {d?.lane && <span className={`asmt__lane ${laneClass(d.lane)}`}>{String(d.lane).toUpperCase()}</span>}
                  <span className="ct__appr-who">{who}</span>
                  {d?.amount_vnd != null && <span className="ct__appr-amount">{fmtApprovalVnd(d.amount_vnd)}</span>}
                  {d?.loan_id && <span className="ct__appr-loan">{d.loan_id}</span>}
                  <span className="ct__appr-payload" title={summarize(row.payload)}>{d ? '' : summarize(row.payload)}</span>
                  <div className="ct__appr-btns">
                    {/* Duyệt: 1 click (reason optional — không thêm friction). Từ chối: mở ô lý do (bắt buộc). */}
                    <button type="button" className="btn btn--ok ct__appr-btn" onClick={() => submitDecision(row, 'approved', '')} disabled={busyId === row.id}>✓ Duyệt</button>
                    <button type="button" className="btn btn--danger ct__appr-btn" onClick={() => openReject(row)} disabled={busyId === row.id} data-testid={`reject-open-${row.id}`}>✗ Từ chối</button>
                  </div>
                </div>
                {rejecting && (
                  <div className="ct__reject" data-testid={`reject-panel-${row.id}`}>
                    <textarea
                      className="ct__reject-reason"
                      placeholder="Lý do từ chối (khách sẽ nhận được)…"
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      rows={2}
                      aria-label="Lý do từ chối"
                      autoFocus
                      disabled={busyId === row.id}
                    />
                    <div className="ct__reject-btns">
                      <button type="button" className="btn btn--ghost ct__appr-btn" onClick={cancelReject} disabled={busyId === row.id}>Huỷ</button>
                      <button
                        type="button"
                        className="btn btn--danger ct__appr-btn"
                        onClick={() => submitDecision(row, 'rejected', rejectReason.trim())}
                        disabled={busyId === row.id || !rejectReason.trim()}
                        data-testid={`reject-confirm-${row.id}`}
                      >
                        {busyId === row.id ? 'Đang gửi…' : 'Xác nhận từ chối'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          {rows.length > 50 && <div className="ct__more">… và {rows.length - 50} phiếu nữa (hiển thị 50 đầu)</div>}
        </div>
      )}
    </div>
  );
}

// ── Khối 2: Audit view — filter tool_calls ──
function AuditView() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [convId, setConvId] = useState('');
  const [tool, setTool] = useState('');
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const filters: Record<string, string> = {};
    if (convId.trim()) filters.conv_id = convId.trim();
    if (tool.trim()) filters.tool = tool.trim();
    conversationApi
      .auditFiltered(filters)
      .then((r) => { setRows(r); setError(null); })
      .catch(() => setError('Lỗi tải nhật ký'));
  }, [convId, tool]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="ct__section">
      <div className="ct__section-head">
        <span className="ct__section-title">Nhật ký tool-call ({rows.length})</span>
        <input className="ct__filter" placeholder="Lọc theo mã ca…" value={convId} onChange={(e) => setConvId(e.target.value)} aria-label="Lọc theo mã ca" />
        <input className="ct__filter" placeholder="Lọc tool…" value={tool} onChange={(e) => setTool(e.target.value)} aria-label="Lọc tool" />
      </div>
      {error && <div className="ct__error">{error}</div>}
      {rows.length === 0 ? (
        <div className="ct__empty">Không có tool-call (thử lọc theo mã của một ca có hoạt động).</div>
      ) : (
        <table className="ct__audit">
          <thead><tr><th>Thời điểm</th><th>Actor</th><th>Tool</th><th>Input</th></tr></thead>
          <tbody>
            {rows.slice(0, 100).map((r) => (
              <tr key={r.id}>
                <td className="ct__audit-ts">{fmtTs(r.ts)}</td>
                <td className="ct__audit-actor">{r.actor === 'main' ? 'Main' : roleLabel(r.actor)}</td>
                <td><code className="ct__audit-tool">{r.tool}</code></td>
                <td className="ct__audit-in">{summarize(r.input)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── Khối 3+4: Trạng thái đội + cost meter (từ conversations + tasks) ──
function AgentStatus() {
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    conversationApi
      .listConversations()
      .then((c) => { setConvs(c); setError(null); })
      .catch(() => setError('Lỗi tải danh sách ca'));
  }, []);

  const byStatus = convs.reduce<Record<string, number>>((acc, c) => {
    acc[c.status] = (acc[c.status] ?? 0) + 1;
    return acc;
  }, {});
  // DF-B-03: "1 Lỗi" đếm CA (conversation) status='failed' → drill-down = list chính các ca đó
  // (tiêu đề + mã ca) ngay dưới số đếm. Cán bộ thấy lỗi → biết CA NÀO. Dùng convs đã load, KHÔNG
  // thêm API. (Role thuộc TASK — không có list-tasks API; xem note báo cáo. Không xây route mới.)
  const failedConvs = convs.filter((c) => c.status === 'failed');

  return (
    <div className="ct__section">
      <div className="ct__section-title">Trạng thái đội — {convs.length} ca</div>
      {error && <div className="ct__error">{error}</div>}
      <div className="ct__stat-grid">
        {(['running', 'waiting_approval', 'done', 'failed', 'idle'] as const).map((s) => (
          <div key={s} className={`ct__stat ct__stat--${s}`}>
            <div className="ct__stat-num">{byStatus[s] ?? 0}</div>
            <div className="ct__stat-label">{STATUS_LABEL[s]}</div>
          </div>
        ))}
      </div>
      {failedConvs.length > 0 && (
        <div className="ct__failed" data-testid="failed-list">
          <div className="ct__failed-title">⚠ Ca đang lỗi ({failedConvs.length})</div>
          <ul className="ct__failed-rows">
            {failedConvs.slice(0, 20).map((c) => (
              <li key={c.id} className="ct__failed-row" data-testid={`failed-row-${c.id}`}>
                <span className="ct__failed-name">{c.title || '(ca chưa đặt tên)'}</span>
                <code className="ct__failed-id">{shortId(c.id)}</code>
              </li>
            ))}
          </ul>
          {failedConvs.length > 20 && <div className="ct__more">… và {failedConvs.length - 20} ca lỗi nữa</div>}
        </div>
      )}
      <div className="ct__note">
        {/* DF-B-04: bỏ jargon dev (tasks.cost/SDK/D-48/per-tool). Sự thật: chi phí đo theo TỪNG LƯỢT
            trao đổi (per-turn) — GIỮ đúng, không đổi thành "gộp toàn phiên". Wording người-thường. */}
        💰 Chi phí: ước tính theo từng lượt trao đổi của mỗi ca. Mở một ca ở Workspace để xem chi phí của lượt đó.
      </div>
    </div>
  );
}

const STATUS_LABEL: Record<string, string> = {
  running: 'Đang chạy', waiting_approval: 'Chờ duyệt', done: 'Hoàn tất', failed: 'Lỗi', idle: 'Sẵn sàng',
};

// ── Deliverable #5: compare single-agent vs multi-agent (2 cột) ──
function CompareView() {
  const [question, setQuestion] = useState('Khách C001 vay 500 triệu được không?');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<CompareResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = () => {
    if (running || !question.trim()) return;
    setRunning(true);
    setError(null);
    setResult(null);
    conversationApi
      .runCompare(question.trim())
      .then((r) => setResult(r))
      .catch(() => setError('So sánh thất bại — thử lại (chạy 2 chế độ mất ~90s).'))
      .finally(() => setRunning(false));
  };

  return (
    <div className="ct__section">
      <div className="ct__section-title">So sánh: 1 LLM trần vs cả ĐỘI (deliverable #5)</div>
      <div className="ct__cmp-input">
        <input
          className="ct__cmp-q"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Câu hỏi thẩm định…"
          aria-label="Câu hỏi so sánh"
          disabled={running}
        />
        <button type="button" className="btn btn--primary ct__cmp-run" onClick={run} disabled={running} data-testid="compare-run">
          {running ? 'Đang chạy 2 chế độ…' : '▶ Chạy so sánh'}
        </button>
      </div>
      {running && <div className="ct__cmp-loading">⏳ Đang chạy SINGLE + MULTI song song — mất ~90s (model chạy thật, kiên nhẫn)…</div>}
      {error && <div className="ct__error">{error}</div>}
      {result && (
        <div className="ct__cmp-cols">
          <CompareColumn title="1 LLM TRẦN (single)" side={result.single} accent="single" />
          <CompareColumn title="CẢ ĐỘI (multi-agent)" side={result.multi} accent="multi" />
        </div>
      )}
    </div>
  );
}

function CompareColumn({ title, side, accent }: { title: string; side: CompareSide | null | undefined; accent: 'single' | 'multi' }) {
  if (!side) {
    return (
      <div className={`ct__cmp-col ct__cmp-col--${accent}`}>
        <div className="ct__cmp-col-title">{title}</div>
        <div className="ct__cmp-partial">Không có kết quả (chế độ này timeout / lỗi — partial).</div>
      </div>
    );
  }
  return (
    <div className={`ct__cmp-col ct__cmp-col--${accent}`}>
      <div className="ct__cmp-col-title">{title}</div>
      <div className="ct__cmp-metrics">
        {side.duration_s != null && <span className="ct__cmp-metric">⏱ {side.duration_s}s</span>}
        {side.tool_calls != null && <span className="ct__cmp-metric">🔧 {side.tool_calls} tool</span>}
        {side.cards != null && <span className="ct__cmp-metric">▦ {side.cards} card</span>}
        {side.cost != null && <span className="ct__cmp-metric">💰 {summarize(side.cost)}</span>}
      </div>
      <div className="ct__cmp-text">{side.text ?? '(không có nội dung)'}</div>
      {side.conv_id && <div className="ct__cmp-link">Ca thật: <code>{shortId(side.conv_id)}</code> (mở ở Workspace để xem trace đầy đủ)</div>}
    </div>
  );
}

function shortId(id: string): string {
  return id.length > 14 ? `${id.slice(0, 10)}…` : id;
}
function summarize(obj: unknown): string {
  if (obj == null) return '';
  try { return JSON.stringify(obj).slice(0, 90); } catch { return ''; }
}
function fmtTs(ts: string): string {
  return ts ? ts.slice(0, 19).replace('T', ' ') : '';
}
// DF-B-01: lane → class chip (tái dùng .lane--* của AssessmentsView, không chế mới). lane lạ → idle.
function laneClass(lane: string): string {
  const m: Record<string, string> = { green: 'lane--green', yellow: 'lane--yellow', red: 'lane--red' };
  return m[String(lane).toLowerCase()] ?? 'lane--idle';
}
// DF-B-01: số tiền → "800.000.000 ₫" (định dạng VN, dấu chấm ngăn nghìn).
function fmtApprovalVnd(n: number): string {
  return `${n.toLocaleString('vi-VN')} ₫`;
}
